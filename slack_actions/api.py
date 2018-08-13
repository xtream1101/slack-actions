import re
import json
import falcon
import logging
import requests
from pprint import pprint
import urllib.parse
from slack_actions.slack_controller import slack_controller


logger = logging.getLogger(__name__)


class Event(object):
    def on_post(self, req, resp):
        """Handles POST requests sent from the slack events"""
        resp.status = falcon.HTTP_200
        stream = req.stream.read().decode('utf-8')
        try:
            event = json.loads(stream)
        except json.decoder.JSONDecodeError:
            event = json.loads(urllib.parse.unquote(stream).replace('payload=', ''))

        if event.get('type') == 'url_verification':
            # Used when adding the url to the App config in slack
            resp.media = {'challenge': event['challenge']}
            return

        # By the end, should always have the keys:
        full_data = {'event': event['event'],  # The original event message from slack
                     'user': None,  # All the user info pulled from the slack api of the uer who triggered the event
                     'channel': None,  # The channel/dm info from the slack api on wher the event happened
                     }

        # 1. Get the user, channel, and file (if needed) from the event
        try:
            if event['event'].get('bot_id') == slack_controller.BOT_ID:
                # Do not let the bot interact with itself, but still allow other bots to trigger it
                return

            logger.debug("Original slack event:\n" + str(json.dumps(event)))

            try:
                event_type = event['event']['type']
                if 'subtype' in event['event']:
                    event_type += '.' + event['event']['subtype']

            except KeyError:
                event_type = event['type']

            # Add more event types as needed to get the correct information
            if event_type in ['file_shared', 'file_created']:
                # Really should use message.file_share instead since it has all the file info already in it
                full_data['user'] = slack_controller.get_user(event['event']['user_id'])
                file_data = slack_controller.get_file(event['event']['file_id'])  # Need this for the channel id
                full_data['channel'] = slack_controller.get_channel(file_data['channels'][0])

            elif event_type in ['interactive_message']:
                full_data['user'] = slack_controller.get_user(event['user']['id'])
                full_data['channel'] = slack_controller.get_channel(event['channel']['id'])

            else:
                full_data['user'] = slack_controller.get_user(event['event']['user'])
                full_data['channel'] = slack_controller.get_channel(event['event']['channel'])

        except Exception:
            logger.exception("Broke generating `full_data`")

        # all_channel_commands = slack_controller.get_all_channel_commands(full_data['channel']['name'])
        all_channel_actions = slack_controller.get_all_channel_actions(full_data['channel']['name'], event_type)

        # 2 - Check if its the help message
        # TODO: Make func in slack_controller
        if event_type == 'message':
            if re.match(slack_controller.help_message_regex, event['event']['text']):
                help_message = slack_controller.help(all_channel_actions, slack_controller.slack_client, full_event=full_data)
                slack_response = slack_controller.slack_client.api_call(**help_message)
                if slack_response['ok'] is False:
                    error_message = "Slack Web API Response: {error} {content}"\
                                    .format(error=slack_response['error'], content=slack_response.get('needed', ''))
                    logger.error(error_message)
                # If the help message was triggered, do nothing else
                return

        # 3. Check the commands that are listening to see which needs to be triggered
        # TODO: Make func in slack_controller
        try:
            # Default response
            response = {'channel': full_data['channel']['id'],
                        'method': 'chat.postMessage',
                        }

            # all_channel_actions = slack_controller.get_all_channel_actions(full_data['channel']['name'], event_type)
            callback_output = None
            # Loop over all triggers for a given command
            for action in all_channel_actions:
                from pprint import pprint
                # pprint(action)
                callback_output = slack_controller.parser.parse_event(full_data, action['callback'], action['triggers'])
                if callback_output is not None:
                    break

            if callback_output is not None:
                # Found a trigger that worked
                response.update(callback_output)
                slack_response = slack_controller.slack_client.api_call(**response)
                if slack_response['ok'] is False:
                    error_message = "Slack Web API Response: {error} {content}"\
                                    .format(error=slack_response['error'], content=slack_response.get('needed', ''))
                    logger.error(error_message)

        except Exception:
            logger.exception("Broke trying to trigger a command")


app = falcon.API()

event = Event()
# Everything gets posted to this single endpoint
app.add_route('/slack/event', event)
