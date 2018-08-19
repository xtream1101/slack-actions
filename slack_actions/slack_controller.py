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
                self.triggers[event_type][func].append({'pattern': parse_using, 'args': args, 'kwargs': kwargs})
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

    def parse_event_orig(self, full_data, callback, triggers):
        for trigger in triggers:
            output = {}

            for key, regex_pattern in trigger['pattern'].items():
                key_parts = key.split('.')
                input_str = full_data['event']
                for part in key_parts:
                    input_str = input_str[part]
                    if part in ['files']:  # Need to add an index on these
                        input_str = input_str[0]

                # Check the regex agains this field
                result = re.search(regex_pattern, input_str)
                if result is not None:
                    if len(result.groupdict().keys()) != 0:
                        output[key] = result.groupdict()
                    else:
                        output[key] = result.groups()
                else:
                    # If any of the results do not match something, then move on
                    output = {}
                    break

            if output:
                return callback(output, full_data, *trigger['args'], **trigger['kwargs'])


class SlackController:

    def __init__(self, parser):
        self.parser = parser
        self.channel_to_callbacks = defaultdict(list)  # Filled in by the user

        # Defaults for the help message
        self.help_message_regex = None  # The user can set their own, or it will default to whats in the setup()

    def add_commands(self, channel_commands):
        # Get all trigger functions to check the callbacks
        all_trigger_fns = []
        for fns in self.parser.triggers.values():
            all_trigger_fns.extend(list(fns.keys()))

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
                    all_class_methods = inspect.getmembers(command_class, predicate=inspect.ismethod)
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
        self.BOT_USER_ID = self.slack_client.api_call('bots.info', bot=self.BOT_ID)['bot']['user_id']
        self.BOT_NAME = '<@{}>'.format(self.BOT_USER_ID)

        if self.help_message_regex is None:
            self.help_message_regex = re.compile('^(?:{bot_name} )?help$'.format(bot_name=self.BOT_NAME),
                                                 flags=re.IGNORECASE)

    def help_trigger(self, full_data, event_type):
        if event_type != 'message' or not re.match(self.help_message_regex, full_data['event']['event']['text']):
            return False

        all_channel_actions = self.get_all_channel_actions(full_data['channel']['name'])
        help_message = self.help(all_channel_actions, self.slack_client, full_event=full_data)
        slack_response = self.slack_client.api_call(**help_message)
        if slack_response['ok'] is False:
            error_message = "Slack Web API Response: {error} {content}"\
                            .format(error=slack_response['error'], content=slack_response.get('needed', ''))
            logger.error(error_message)

        return True

    def help(self, all_channel_actions, slack_client, full_event):
        """Default help response

        Args:
            callbacks (list): list of the callbacks
            full_event (dict): All of the data from the slack client
            slack_client (SlackClient): Api to send message directly to the slack api

        Returns:
            dict/None: dict of dat to send to the slack api
                       the keys `channel` & `as_user` & `method` are added before posting on return

        """
        message_data = {'channel': full_event['channel']['id'],
                        'method': 'chat.postEphemeral',
                        'user': full_event['user']['id'],
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
        conversations = {}
        for conversation in self.slack_client.api_call('conversations.list').get('channels', []):
            conversations[conversation['name']] = conversation
            conversations[conversation['id']] = conversation
        return conversations

    def _get_user_list(self):
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
        # Get all commands in channel
        all_channel_callbacks = self.channel_to_callbacks.get(channel_name, [])
        # All commands that are in ALL channels. Make the list unique.
        # If not, if a command is in __all__ and another channel it will display the help twice
        #   (also loop through twice when checking commands)
        for callback in self.channel_to_callbacks.get('__all__', []):
            if callback not in all_channel_callbacks:
                all_channel_callbacks.append(callback)

        return all_channel_callbacks

    def get_all_channel_event_actions(self, channel_name, event_type):
        channel_actions = []
        all_channel_callbacks = self.get_all_channel_callbacks(channel_name)
        all_event_actions = self.parser.triggers[event_type]

        for callback in all_channel_callbacks:
            if callback in all_event_actions:
                triggers = all_event_actions[callback]
                channel_actions.append({'callback': callback, 'triggers': triggers})

        return channel_actions

    def get_all_channel_actions(self, channel_name):
        channel_actions = []
        all_channel_callbacks = self.get_all_channel_callbacks(channel_name)
        all_actions = {}
        for triggers in self.parser.triggers.values():
            all_actions.update(triggers)

        for callback in all_channel_callbacks:
            if callback in all_actions:
                triggers = all_actions[callback]
                channel_actions.append({'callback': callback, 'triggers': triggers})

        return channel_actions

    def process_event(self, full_data, event_type):
        try:
            all_channel_event_actions = self.get_all_channel_event_actions(full_data['channel']['name'], event_type)
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
                                    .format(error=slack_response['error'], content=slack_response.get('needed', ''))
                    logger.error(error_message)

        except Exception:
            logger.exception("Broke trying to trigger a command")


parser = Parser()
slack_controller = SlackController(parser)
