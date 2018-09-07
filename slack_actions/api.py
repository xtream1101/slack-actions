import json
import falcon
import logging
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
        full_data = {'event': event,  # The original event message from slack
                     'user': None,  # All the user info pulled from the slack api of the uer who triggered the event
                     'channel': None,  # The channel/dm info from the slack api on wher the event happened
                     }

        # 1. Get the user, channel, and file (if needed) from the event
        try:
            if ((event.get('type') == 'interactive_message' and event['user']['id'] == slack_controller.BOT_ID) or
                    event.get('event', {}).get('bot_id') == slack_controller.BOT_ID):
                # Do not let the bot interact with itself, but still allow other bots to trigger it
                return

            logger.debug("Original slack event:\n" + str(json.dumps(event)))

            try:
                # Get the event type
                event_type = event['event']['type']
                if 'subtype' in event['event']:
                    event_type += '.' + event['event']['subtype']
            except KeyError:
                # Prob some interactive or something else
                event_type = event['type']

            # Add more event types as needed to get the correct information
            if event_type in ['file_shared', 'file_created']:
                # Really should use message.file_share instead since it has all the file info already in it
                full_data['user'] = slack_controller.get_user(event['event']['user_id'])
                # Need this for the channel id
                file_data = slack_controller.slack_client.api_call('files.info', file=event['event']['file_id'])
                full_data['channel'] = slack_controller.get_channel(file_data['file']['channels'][0])

            elif event_type in ['interactive_message']:
                full_data['user'] = slack_controller.get_user(event['user']['id'])
                full_data['channel'] = slack_controller.get_channel(event['channel']['id'])

            elif event_type in ['message.message_changed']:
                full_data['user'] = slack_controller.get_user(event['event']['message']['user'])
                full_data['channel'] = slack_controller.get_channel(event['event']['channel'])

            elif event_type in ['message.message_deleted']:
                full_data['user'] = slack_controller.get_user(event['event']['previous_message']['user'])
                full_data['channel'] = slack_controller.get_channel(event['event']['channel'])

            elif event_type in ['reaction_added']:
                full_data['user'] = slack_controller.get_user(event['event']['user'])
                full_data['channel'] = slack_controller.get_channel(event['event']['item']['channel'])

            else:
                full_data['user'] = slack_controller.get_user(event['event']['user'])
                full_data['channel'] = slack_controller.get_channel(event['event']['channel'])

        except Exception:
            logger.exception("Broke generating `full_data`")

        # 2 - Check if its the help message, if so do nothing else
        if slack_controller.help_check(full_data, event_type):
            return

        # 3. Check the commands that are listening to see which needs to be triggered
        slack_controller.process_event(full_data, event_type)


app = falcon.API()

event = Event()
# Everything gets posted to this single endpoint
app.add_route('/slack/event', event)
