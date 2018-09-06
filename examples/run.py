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

# Order of the commands in the channel matter, the first match it finds it will stop
# The order of the channels do not matter though
commands = {'__direct_message__': [],
            '__all__': [Example(), bar, UIElements()],
            'general': [],
            }
slack_controller.add_commands(commands)


if __name__ == '__main__':
    logger.critical("\nRun listener by doing (replace `run` with this filename):\n\tgunicorn -b 0.0.0.0:5000 run:app\n")
