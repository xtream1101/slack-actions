import re  # NOQA: F401
import logging
from slack_actions import slack_controller, app  # NOQA: F401

logging.basicConfig(level=logging.DEBUG,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

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

# Import commands after the logging and slack_controller setup, this way the logging format and level are applied to
# the imported commands and all decorators on functions and static methods have access to SLACK_BOT_TOKEN at load time

# Commands can be imported 3 different ways:
# 1. by importing an entire module of commands (where the commands are top-level functions)
import command_module  # NOQA: E402

# 2. by importing a command class from a given module (where the commands are methods of the imported class)
from command_class import CommandClass  # NOQA: E402
from static_command_class import StaticCommandClass  # NOQA: E402
from ui_elements import UIElements  # NOQA: E402

# 3. by importing a specific command from a module (where the command is a top-level function)
from other_commands import bar  # NOQA: E402
# Order of the commands in the channel matter, the first match it finds it will stop
# The order of the channels do not matter though
commands = {'__direct_message__': [],
            '__all__': [CommandClass(), UIElements()],  # if the class contains commands that are _not_ static methods,
                                                        # then you must initialize an object of that class
                                                        # before passing it to slack_controller.add_commands
            'general': [StaticCommandClass],  # if the class only contains commands as static methods, then you
                                              # should pass the class itself
            'bot-test': [command_module, bar]  # entire modules and functions can also be passed as-is
            }

slack_controller.add_commands(commands)


if __name__ == '__main__':
    logger.critical("\nRun listener by doing (replace `run` with this filename):\n\tgunicorn -b 0.0.0.0:5000 run:app\n")
