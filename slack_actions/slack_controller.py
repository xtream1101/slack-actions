import os
import re
import copy
import urllib
import inspect
import pathlib
import logging
from collections import defaultdict
from slackclient import SlackClient

logger = logging.getLogger(__name__)


class SlackApiError(Exception):
    pass


class SlackController:

    def __init__(self):
        self.triggers = defaultdict(lambda: defaultdict(list))
        self.helpers = defaultdict(list)
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
        for fns in self.triggers.values():
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
        self.SLACK_BOT_TOKEN = os.environ.get('SLACK_BOT_TOKEN')
        if self.SLACK_BOT_TOKEN is None:
            self.SLACK_BOT_TOKEN = slack_bot_token

        if not self.SLACK_BOT_TOKEN:
            raise ValueError("Missing SLACK_BOT_TOKEN")

        self.slack_client = SlackClient(self.SLACK_BOT_TOKEN)
        self.channels = self._get_conversation_list()  # Includes groups and channels
        self.users = self._get_user_list()

        self.BOT_ID = self._get_bot_id()
        self.BOT_USER_ID = self._get_bot_user_id(self.BOT_ID)
        self.BOT_NAME = '<@{}>'.format(self.BOT_USER_ID)

        if self.help_message_regex is None:
            self.help_message_regex = re.compile('^(?:{bot_name} )?help$'.format(bot_name=self.BOT_NAME),
                                                 flags=re.IGNORECASE)

    def _get_bot_id(self):
        slack_response = self.slack_client.api_call('users.profile.get')
        if slack_response['ok'] is False:
            error_message = "{error} {content}".format(error=slack_response['error'],
                                                       content=slack_response.get('needed', ''))
            raise SlackApiError(error_message)
        else:
            return slack_response['profile']['bot_id']

    def _get_bot_user_id(self, bot_id):
        slack_response = self.slack_client.api_call('bots.info', bot=bot_id)
        if slack_response['ok'] is False:
            error_message = "{error} {content}".format(error=slack_response['error'],
                                                       content=slack_response.get('needed', ''))
            raise SlackApiError(error_message)

        return slack_response['bot']['user_id']

    def help_check(self, full_data, event_type):
        """Check if the help message should be triggered

        If the help message is triggered, the do not let any other command get triggered

        Arguments:
            full_data {dict} -- The event from the slack api as well as user and channel data
            event_type {str} -- Event type of the event that was sent by slack

        Returns:
            bool -- False if the help message should not be triggered, True if it was
        """
        if event_type != 'message' or not re.match(self.help_message_regex,
                                                   full_data['event']['text']):
            return False

        all_channel_actions = self.get_all_channel_actions(full_data['sa_channel'].get('name', '__direct_message__'))
        self.help_action(all_channel_actions, full_data)

    def help_action(self, all_channel_actions, full_data):
        """Get all of the help commands form the channel

        Arguments:
            all_channel_actions {list} -- All of the commands in the channel
            full_data {dict} -- The event from the slack api as well as user and channel data

        Returns:
            dict -- The response to send to the slack api
        """
        message_data = {'channel': full_data['sa_channel']['id'],
                        'method': 'chat.postEphemeral',
                        'user': full_data['sa_user']['id'],
                        'text': 'Here are all the commands available in this channel',
                        'attachments': [],
                        }

        attachment_defaults = {'mrkdwn_in': ['text', 'pretext'],
                               }

        for action in all_channel_actions:
            for helper in self.helpers.get(action['callback'], []):
                helper_attacment = attachment_defaults.copy()
                helper_attacment.update(helper)
                message_data['attachments'].append(helper_attacment)

        # Post to slack
        slack_response = self.slack_client.api_call(**message_data)
        if slack_response['ok'] is False:
            error_message = "Slack Web API Response: {error} {content} {response_metadata}"\
                            .format(error=slack_response['error'],
                                    content=slack_response.get('needed', ''),
                                    metadata=slack_response.get('response_metadata', ''))
            logger.error(error_message)

    def _get_conversation_list(self):
        """Get all channel data and save by name and id

        Returns:
            dict -- All channel data, accessible by name or id
        """
        conversations = {}
        raw_conversation_list = []
        # Get all pages
        next_cursor = 'start'
        while next_cursor:
            if next_cursor == 'start':  # To get the first page
                next_cursor = None
            slack_response = self.slack_client.api_call('conversations.list',
                                                        limit=1000,
                                                        cursor=next_cursor,
                                                        types='public_channel,private_channel,mpim,im')
            if slack_response['ok'] is False:
                error_message = "{error} {content}".format(error=slack_response['error'],
                                                           content=slack_response.get('needed', ''))
                raise SlackApiError(error_message)
            raw_conversation_list.extend(slack_response['channels'])
            # See if ther is another page
            next_cursor = slack_response['response_metadata'].get('next_cursor')

        for conversation in raw_conversation_list:
            try:
                conversations[conversation['name']] = conversation
            except KeyError:
                pass
            conversations[conversation['id']] = conversation

        return conversations

    def _get_user_list(self):
        """Get all user data and save by name and id

        Returns:
            dict -- All user data, accessible by name or id
        """
        users = {}
        raw_user_list = []
        next_cursor = 'start'
        while next_cursor:
            if next_cursor == 'start':  # To get the first page
                next_cursor = None
            slack_response = self.slack_client.api_call('users.list', limit=1000, cursor=next_cursor)
            if slack_response['ok'] is False:
                error_message = "{error} {content}".format(error=slack_response['error'],
                                                           content=slack_response.get('needed', ''))
                raise SlackApiError(error_message)
            raw_user_list.extend(slack_response['members'])
            # See if ther is another page
            next_cursor = slack_response['response_metadata'].get('next_cursor')

        for user in raw_user_list:
            users[user['name']] = user
            users[user['id']] = user

        return users

    def get_user(self, key):
        """Get the user data

        Try and get the user from self.users, if it can't then refresh the user list and try again

        Arguments:
            key {str} -- Either the name or id of the user

        Returns:
            dict/None -- The data about the user from the slack api
        """
        for _ in range(2):
            user = self.users.get(key)
            if user is None:
                # Update user list from slack api and try and get the user again
                self.users = self._get_user_list()
            else:
                # We found the user, so no need to loop again
                break

        return user

    def get_channel(self, key):
        """Get the channel data

        Try and get the channel from self.channels, if it can't then refresh the channel list and try again

        Arguments:
            key {str} -- Either the name or id of the channel

        Returns:
            dict/None -- The data about the channel from the slack api
        """
        for _ in range(2):
            channel = self.channels.get(key)
            if channel is None:
                # Update channel list from slack api and try and get the channel again
                self.channels = self._get_conversation_list()
            else:
                # We found the channel, so no need to loop again
                break

        if not channel:
            logger.warning('The app does not have access to the channel {}'.format(key))

        return channel

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
            actions = self.triggers[event_type]
        else:
            actions = {}
            for triggers in self.triggers.values():
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
        if not full_data['sa_channel']:
            # Does not have access to channel
            return

        try:
            all_channel_event_actions = self.get_all_channel_actions(full_data['sa_channel'].get('name', '__direct_message__'),
                                                                     event_type=event_type)
            # Default response
            response = {'channel': full_data['sa_channel']['id'],
                        'method': 'chat.postMessage',
                        }

            callback_output = None
            # Loop over all triggers for a given command
            for action in all_channel_event_actions:
                callback_output = self.parse_event(full_data, action['callback'], action['triggers'])
                if callback_output is not None:
                    break

            if callback_output is not None:
                # Found a trigger that worked
                response.update(callback_output)
                slack_response = self.slack_client.api_call(**response)
                if slack_response['ok'] is False:
                    error_message = "Slack Web API Response: {error} {content} {metadata}"\
                                    .format(error=slack_response['error'],
                                            content=slack_response.get('needed', ''),
                                            metadata=slack_response.get('response_metadata', ''))
                    logger.error(error_message)

        except Exception:
            logger.exception("Broke trying to trigger a command")

    ###
    # Used to register the triggers
    ###
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
                try:
                    cls_name = func.__self__.__class__.__name__ + '.'
                except AttributeError:
                    cls_name = ''

                logger.info("Registered {event_type} listener for {cls_name}{func_name} to regex `{parse_using}`"
                            .format(event_type=event_type,
                                    cls_name=cls_name,
                                    func_name=func.__name__,
                                    parse_using=parse_using))
            return func

        return wrapper

    def help_message(self, **kwargs):
        def wrapper(func):
            self.helpers[func].append(dict(kwargs))
            try:
                cls_name = func.__self__.__class__.__name__ + '.'
            except AttributeError:
                cls_name = ''
            logger.info("Registered helper for {cls_name}{func_name}"
                        .format(cls_name=cls_name,
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
                if full_data['type'] == 'event_callback':
                    input_str = copy.deepcopy(full_data['event'])
                else:
                    input_str = copy.deepcopy(full_data)

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

    def download(self, url, file_):
        """
        file_ is either a string (filename & path) to save the data to, or an in-memory object
        """
        rdata = None

        try:
            request = urllib.request.Request(url)
            request.add_header('Authorization', 'Bearer {}'.format(self.SLACK_BOT_TOKEN))
            # urllib downloads files a bit faster then requests does
            with urllib.request.urlopen(request) as response:
                data = response.read()
                if isinstance(file_, str):
                    # If a file path, then make sure the dirs are created
                    file_path = os.path.dirname(os.path.abspath(file_))
                    pathlib.Path(file_path).mkdir(parents=True, exist_ok=True)

                    with open(file_, 'wb') as out_file:
                        out_file.write(data)

                    rdata = file_

                else:
                    file_.write(data)
                    file_.seek(0)

                    rdata = file_

        except urllib.error.HTTPError as e:
            logger.error("Download Http Error `{}` on {}".format(e.code, url))

        except Exception:
            logger.exception("Download Error on {}".format(url))

        return rdata


slack_controller = SlackController()
