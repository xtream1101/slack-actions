import re
import logging
from slack_actions import slack_controller, app

logging.basicConfig(level=logging.DEBUG,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Import commands after the logging setup, this way the logging format and level are applied to the imported commands
from example import Example
from ui_elements import UIElements
from other_commands import bar

# Token set by the env var SLACK_BOT_TOKEN
slack_controller.setup()

# Custom help trigger (Uncomment to test)
# If using the bot name, then this must be after the setup()
# help_pattern = '^(?:{} )?help me$'.format(slack_controller.BOT_NAME)
# slack_controller.help_message_regex = re.compile(help_pattern, flags=re.IGNORECASE)

# Custom help action (Uncomment to test)
# Save the original since we do not want to change what it does, just add another step to it
# help_orig = slack_controller.help_action
# def custom_help_action(all_channel_actions, full_data):
#     # Run the original fn the way it is (using the message attachements)
#     # If you want your help messages to not use attachements then you do not need to call the original
#     #   and your help decorators could have custom keyword args.
#     help_orig(all_channel_actions, full_data)

#     # Also add a reaction to the help message so others know they have been helped
#     message_data = {'channel': full_data['sa_channel']['id'],
#                     'method': 'reactions.add',
#                     'name': 'thumbsup',
#                     'timestamp': full_data['event']['event_ts']
#                     }
#     slack_response = slack_controller.slack_client.api_call(**message_data)
#     if slack_response['ok'] is False:
#         error_message = "Failed to add help reaction. Slack Web API Response: {error} {content}"\
#                         .format(error=slack_response['error'],
#                                 content=slack_response.get('needed', ''))
#         logger.error(error_message)
# slack_controller.help_action = custom_help_action

# Order of the commands in the channel matter, the first match it finds it will stop
# The order of the channels do not matter though
commands = {'__direct_message__': [],
            '__all__': [Example(), bar, UIElements()],
            'general': [],
            }
slack_controller.add_commands(commands)


if __name__ == '__main__':
    logger.critical("\nRun listener by doing (replace `run` with this filename):\n\tgunicorn -b 0.0.0.0:5000 run:app\n")
