import os
import re
import copy
import inspect
import logging
from collections import defaultdict
from slackclient import SlackClient

logger = logging.getLogger(__name__)


class Parser:

    def __init__(self):
        self.triggers = defaultdict(lambda: defaultdict(list))
        self.helpers = defaultdict(list)

    def trigger(self, *args, **kwargs):
        event_types = args[0]
        if isinstance(event_types, str):
            event_types = [event_types]

        return self._register_trigger(event_types, args[1], *args[2:], **kwargs)

    def _register_trigger(self, event_types, regex_parsers, *args, flags=0, **kwargs):
        def wrapper(func):
            parse_using = {}
            for key, regex_str in regex_parsers.items():
                parse_using[key] = re.compile(regex_str, flags)

            for event_type in event_types:
                self.triggers[event_type][func].append({'pattern': parse_using,
                                                        'args': args,
                                                        'kwargs': kwargs})
                logger.info("Registered {event_type} listener for {func_name} to regex `{parse_using}`"
                            .format(event_type=event_type,
                                    class_name='',  # func.__self__.__class__.__name__,  # TODO: fix for fns
                                    func_name=func.__name__,
                                    parse_using=parse_using))
            return func

        return wrapper

    def help(self, **kwargs):
        def wrapper(func):
            self.helpers[func].append(dict(kwargs))
            logger.info("Registered helper for {func_name}"
                        .format(class_name='',  # func.__self__.__class__.__name__,  # TODO: fix for fns
                                func_name=func.__name__))
            return func

        return wrapper

    def parse_event(self, full_data, callback, triggers):
        """Run the callback that matches the trigger

        Find the first trigger that matches and run that callback

        Arguments:
            full_data {dict} -- The event from the slack api as well as user and channel data
            callback {function} -- The function to be triggered if a triggered is matched
            triggers {list} -- All the triggers to try and match against

        Returns:
            dict -- The response to send to the slack api
        """
        for trigger in triggers:
            output = {}
            num_patts = len(trigger['pattern'])

            for key, regex_pattern in trigger['pattern'].items():
                key_parts = key.split('.')
                if full_data['event']['type'] == 'event_callback':
                    input_str = copy.deepcopy(full_data['event']['event'])
                else:
                    input_str = copy.deepcopy(full_data['event'])

                for part in key_parts:
                    if isinstance(input_str, list):
                        # check if current key is an index, if so use it, otherwise default to 0
                        try:
                            idx = int(part)
                            input_str = input_str[idx]
                            continue  # Move on to the next part
                        except ValueError:
                            # Default to the first item and then use the next key
                            input_str = input_str[0]

                    input_str = input_str[part]

                # Check the regex agains this field
                result = re.search(regex_pattern, input_str)

                if result is None:
                    # No match was found, lets move on!
                    break

                if len(result.groupdict().keys()) != 0:
                    output[key] = result.groupdict()
                else:
                    output[key] = result.groups()

            # All patterns match, fire callback
            if len(output) == num_patts:
                return callback(output, full_data, *trigger['args'], **trigger['kwargs'])


class SlackController:

    def __init__(self, parser):
        self.parser = parser
        self.channel_to_callbacks = defaultdict(list)  # Filled in by the user

        # Defaults for the help message
        self.help_message_regex = None  # The user can set their own, or it will default to whats in the setup()

    def add_commands(self, channel_commands):
        """Add the commands to a channel

        Arguments:
            channel_commands {dict} -- Keys are the channel name and the value is a list of callbacks
        """
        # Get all trigger functions to match against the callbacks
        all_trigger_fns = []
        for fns in self.parser.triggers.values():
            all_trigger_fns.extend(list(fns.keys()))

        # Add the callbacks to the correct channel
        for channel, commands in channel_commands.items():
            channel_callbacks = []
            for command in commands:
                if isinstance(command, type) is False and hasattr(command, '__call__') is True:
                    # Just a function
                    if command in all_trigger_fns:
                        # Make sure the command passed has a triggers
                        channel_callbacks.append(command)
                    else:
                        logger.warning("In add_commands: Command {cmd_name} has no trigger"
                                       .format(cmd_name=command.__name__))
                else:
                    command_class = command
                    if isinstance(command, type) is True:
                        # An uninitialized class
                        logger.warning("In add_commands: Adding an uninitialized class {cls_name}. Initializing..."
                                       .format(cls_name=command_class.__name__))
                        command_class = command_class()

                    # Get all methods from class to see what is in triggers
                    all_class_methods = inspect.getmembers(command_class,
                                                           predicate=inspect.ismethod)
                    for method in all_class_methods:
                        if method[1] in all_trigger_fns:
                            channel_callbacks.append(method[1])

            self.channel_to_callbacks[channel].extend(channel_callbacks)

    def setup(self, slack_bot_token=None):
        # Do not have this in __init__ because this is not needed when running tests
        # TODO: Should the OS var overide the one passed in?????
        self.SLACK_BOT_TOKEN = slack_bot_token
        if self.SLACK_BOT_TOKEN is None:
            self.SLACK_BOT_TOKEN = os.environ.get('SLACK_BOT_TOKEN')

        if self.SLACK_BOT_TOKEN is None:
            raise ValueError("Missing SLACK_callbacksBOT_TOKEN")

        self.slack_client = SlackClient(self.SLACK_BOT_TOKEN)
        self.channels = self._get_conversation_list()  # Includes groups and channels
        self.users = self._get_user_list()

        self.BOT_ID = self.slack_client.api_call('users.profile.get')['profile']['bot_id']
        self.BOT_USER_ID = self.slack_client.api_call('bots.info',
                                                      bot=self.BOT_ID)['bot']['user_id']
        self.BOT_NAME = '<@{}>'.format(self.BOT_USER_ID)

        if self.help_message_regex is None:
            self.help_message_regex = re.compile('^(?:{bot_name} )?help$'.format(bot_name=self.BOT_NAME),
                                                 flags=re.IGNORECASE)

    def help_trigger(self, full_data, event_type):
        """Check if the help message should be triggered

        If the help message is triggered, the do not let any other command get triggered

        Arguments:
            full_data {dict} -- The event from the slack api as well as user and channel data
            event_type {str} -- Event type of the event that was sent by slack

        Returns:
            bool -- False if the help message should not be triggered, True if it was
        """
        if event_type != 'message' or not re.match(self.help_message_regex,
                                                   full_data['event']['event']['text']):
            return False

        all_channel_actions = self.get_all_channel_actions(full_data['channel']['name'])
        help_message = self.help(all_channel_actions, full_data)
        slack_response = self.slack_client.api_call(**help_message)
        if slack_response['ok'] is False:
            error_message = "Slack Web API Response: {error} {content}"\
                            .format(error=slack_response['error'],
                                    content=slack_response.get('needed', ''))
            logger.error(error_message)

        return True

    def help(self, all_channel_actions, full_data):
        """Get all of the help commands form the channel

        Arguments:
            all_channel_actions {list} -- All of the commands in the channel
            full_data {dict} -- The event from the slack api as well as user and channel data

        Returns:
            dict -- The response to send to the slack api
        """
        message_data = {'channel': full_data['channel']['id'],
                        'method': 'chat.postEphemeral',
                        'user': full_data['user']['id'],
                        'text': 'Here are all the commands available in this channel',
                        'attachments': [],
                        }

        attachment_defaults = {'mrkdwn_in': ['text', 'pretext'],
                               }

        for action in all_channel_actions:
            for helper in self.parser.helpers.get(action['callback'], []):
                helper_attacment = attachment_defaults.copy()
                helper_attacment.update(helper)
                message_data['attachments'].append(helper_attacment)

        return message_data

    def _get_conversation_list(self):
        """Get all channel data and save by name and id

        Returns:
            dict -- All channel data, accessible by name or id
        """
        conversations = {}
        for conversation in self.slack_client.api_call('conversations.list').get('channels', []):
            conversations[conversation['name']] = conversation
            conversations[conversation['id']] = conversation
        return conversations

    def _get_user_list(self):
        """Get all user data and save by name and id

        Returns:
            dict -- All user data, accessible by name or id
        """
        users = {}
        for user in self.slack_client.api_call('users.list').get('members', []):
            users[user['name']] = user
            users[user['id']] = user
        return users

    def get_user(self, key):
        """Get the user data

        TODO: If the user does not exist, refresh from the api.
              Store in a real cache so it does not need to hit on every reload

        Arguments:
            key {str} -- Either the name or id of the user

        Returns:
            dict -- The data about the user from the slack api
        """
        return self.users.get(key)

    def get_channel(self, key):
        """Get the channel data

        TODO: If the channel does not exist, refresh from the api.
              Store in a real cache so it does not need to hit on every reload

        Arguments:
            key {str} -- Either the name or id of the channel

        Returns:
            dict -- The data about the channel from the slack api
        """
        return self.channels.get(key)

    def get_all_channel_callbacks(self, channel_name):
        """Get all the callbacks in the given channel

        Arguments:
            channel_name {str} -- Name of the channel to get the callbacks from

        Returns:
            list -- list of all of the callbacks in the given channel
        """
        all_channel_callbacks = self.channel_to_callbacks.get(channel_name, [])
        # All callbacks that are in ALL channels. Make the list unique.
        # If not, if a command is in __all__ and another channel it will display the help twice
        for callback in self.channel_to_callbacks.get('__all__', []):
            if callback not in all_channel_callbacks:
                all_channel_callbacks.append(callback)

        return all_channel_callbacks

    def get_all_channel_actions(self, channel_name, event_type=None):
        """Get all actions for the given channel, filter by an event_type if passed in

        event_type is only not passed in when the help message is triggered.
        This is because for the help message we need all the help messages form all event_types

        Arguments:
            channel_name {str} -- Name of the channel to look for actions in

        Keyword Arguments:
            event_type {str} -- Event type of the event that was sent by slack

        Returns:
            list -- list of the channel actions based on the inputs
        """
        channel_actions = []

        if event_type is not None:
            actions = self.parser.triggers[event_type]
        else:
            actions = {}
            for triggers in self.parser.triggers.values():
                actions.update(triggers)

        all_channel_callbacks = self.get_all_channel_callbacks(channel_name)
        for callback in all_channel_callbacks:
            if callback in actions:
                triggers = actions[callback]
                channel_actions.append({'callback': callback, 'triggers': triggers})

        return channel_actions

    def process_event(self, full_data, event_type):
        """See if there are any commands for the event_type that will be triggered

        Arguments:
            full_data {dict} -- The event from the slack api as well as user and channel data
            event_type {str} -- Event type of the event that was sent by slack
        """
        try:
            all_channel_event_actions = self.get_all_channel_actions(full_data['channel']['name'],
                                                                     event_type=event_type)
            # Default response
            response = {'channel': full_data['channel']['id'],
                        'method': 'chat.postMessage',
                        }

            callback_output = None
            # Loop over all triggers for a given command
            for action in all_channel_event_actions:
                callback_output = self.parser.parse_event(full_data, action['callback'], action['triggers'])
                if callback_output is not None:
                    break

            if callback_output is not None:
                # Found a trigger that worked
                response.update(callback_output)
                slack_response = self.slack_client.api_call(**response)
                if slack_response['ok'] is False:
                    error_message = "Slack Web API Response: {error} {content}"\
                                    .format(error=slack_response['error'],
                                            content=slack_response.get('needed', ''))
                    logger.error(error_message)

        except Exception:
            logger.exception("Broke trying to trigger a command")


parser = Parser()
slack_controller = SlackController(parser)
