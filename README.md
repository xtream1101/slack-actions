# Slackbot
Create custom actions based on slack events

This project is to make it simple to have a single slackbot that can have different commands in different slack channels. This is done by having functions or classes that get added to a channel, and each function/method has a regex trigger that it is listening for in the channel it is in. If the trigger and channel match, then it will run that function.


## How to use
First you need to create a Slack App to get a Workspace Token. With slack apps you need to give it permissions for each thing you want it to listen to or things it can do. Remember that each time to edit the permissions you will need to update (re-add) the App to your team for the new/updated permissions to take affect.
Since slack apps work by hitting an api endpoint, you will need an public facing endpoint to test with. You can use [ngrok](https://ngrok.com/) or anything similar for development.

To install, either run the `setup.py install`
or install via pip (**recommended**): `pip install slack_actions`

Basic Example (`run.py`):
```python
import re
import logging
from slack_actions import slack_controller, app

logger = logging.getLogger(__name__)

# This is going to listen for a message with the text foobar in it, case insensitive.
@slack_controller.parser.trigger(['message'], {'text': 'foobar'}, flags=re.IGNORECASE)
@slack_controller.parser.help(author_name="trigger:message", color="#3366ff", text="Type:\n> foobar")
def foobar(output, full_event):
    message_data = {'text': 'fn: foobar was triggered'}
    return message_data


# The token can also be set by an env var `SLACK_BOT_TOKEN`, which will be used first if it exists
auth_token = 'xoxa-app-token-here'
# or it can be set in the script like so
slack_controller.setup(slack_bot_token=auth_token)

# Order of the commands in the channel list matter, the first match it finds it will stop
# The order of the channels do not matter though
commands = {'__direct_message__': [],  # For direct messages between a user and the bot
            '__all__': [foobar],  # Any channel that the bot is in
            'general': [],  # Only in the channel named __general__
            }
slack_controller.add_commands(commands)


if __name__ == '__main__':
    logger.critical("\nRun listener by doing (replace `run` with this filename):\n\tgunicorn -b 0.0.0.0:5000 run:app \n")
```
_You can find more examples in the `examples/` directory._
To run this basic example, type: `gunicorn -b 0.0.0.0:5000 run:app`, this will start the api web server that slack can post to.

In any channel, you can type the message `help` and the slack bot should return all the help messages for the commands in that channel.

## How the decorators work:

Each function has a `trigger` and a `help` decorator from the `slack_controller`.

### `slack_controller.parser.trigger`
This is used to tell the function when to run. There are 2 positional arguments and 1 keyword argument:
`@slack_controller.parser.trigger(['message'], {'text': 'foobar'}, flags=re.IGNORECASE)`
- **_event_types_**: These are the name of the [Slack event types](https://api.slack.com/events) sent by slack in the api call, it should be formatted as `event_type.sub_type`. It can be a single event type or a list of them (depending on the regex passed in too some may not play well together)
- **_regex_parsers_**: This is a dictionary with its keys being fields in the Slack api data under the `event` key. The value is the regex that it needs to match in order to run the function. Nested keys can be formatted like so `actions.value`. If the next nested item is a list and not another dictionary then you can just jump to the next dict's keys or specify the index of the item you want. By default if no index is passed in it will use the first item in the list. For example, both of these will get the first item in the list: `actions.0.value`, `actions.value`.
- **_flags_**: Keyword argument that gets passed to pythons `re.compile` function

### `slack_controller.parser.help`
This is used when the user types `help` in a channel to let them know what commands they have available to use. The named arguments map to the keys in the [Slack message attachements](https://api.slack.com/docs/message-attachments). The examples in this repo all follow a similar formatting, but they can be any combination of argumenst to fit the functions help message needs.
`@slack_controller.parser.help(author_name="trigger:message", color="#3366ff", text="Type:\n> foobar")`
