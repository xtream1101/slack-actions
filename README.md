# Slackbot
Create custom actions based on slack events

[![PyPI](https://img.shields.io/pypi/v/slack_actions.svg)](https://pypi.python.org/pypi/slack_actions)
[![PyPI](https://img.shields.io/pypi/l/slack_actions.svg)](https://pypi.python.org/pypi/slack_actions)


This project is to make it simple to have a single slackbot that can have different commands in different slack channels. This is done by having functions or classes that get added to a channel, and each function/method has a regex trigger that it is listening for in the channel it is in. If the trigger and channel match, then it will run that function.


## How to use
First you need to create a Slack Workspace App. You will find your Access Token under the _OAuth & Permissions_ section.  
With Slack apps, you need to give it permissions for what you want it to do. By default it needs at least these permissions to start:
- users:read _(needed to get the users in the team)_
- users.profile:read _(needed to get the bot info and user emails)_
- conversations:read _(needed to get the list of conversations the bot is in)_

Remember that each time to edit the permissions you will need to re install the App to your team for the new/updated permissions to take affect.

Since slack apps work by hitting an api endpoint, you will need an public facing endpoint to test with. You can use [ngrok](https://ngrok.com/) or anything similar for development _(see below for custom solution)_. The endpoint that you will be hitting on the server will always be `example.com/slack/event`. This will need to be added in the _Event Subscriptions_ section of the App. Be sure to add _Workplace Events_ otherwise slack will never hit your bot with an action. To get started try adding **_message.channels_**, for each event you add you will need to add the required permission too. In this case the permission **_channels:history_** will be added.

To add the app to a channel, go into the app settings and add to any channels that you would like it to be in.

To install, either run the `setup.py install`  
or install via pip (**recommended**): `pip install slack_actions`

Basic Example (`run.py`):
```python
import re
import logging
from slack_actions import slack_controller, app

logger = logging.getLogger(__name__)

# This is going to listen for a message with the text foobar in it, case insensitive.
@slack_controller.trigger(['message'], {'text': 'foobar'}, flags=re.IGNORECASE)
@slack_controller.help_message(author_name="trigger:message", color="#3366ff", text="Type:\n> foobar")
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

### `slack_controller.trigger`
This is used to tell the function when to run. There are 2 positional arguments and 1 keyword argument:
`@slack_controller.trigger(['message'], {'text': 'foobar'}, flags=re.IGNORECASE)`
- **_event_types_**: These are the name of the [Slack event types](https://api.slack.com/events) sent by slack in the api call, it should be formatted as `event_type.sub_type`. It can be a single event type or a list of them (depending on the regex passed in too some may not play well together)
- **_regex_parsers_**: This is a dictionary with its keys being fields in the Slack api data under the `event` key. The value is the regex that it needs to match in order to run the function. Nested keys can be formatted like so `actions.value`. If the next nested item is a list and not another dictionary then you can just jump to the next dict's keys or specify the index of the item you want. By default if no index is passed in it will use the first item in the list. For example, both of these will get the first item in the list: `actions.0.value`, `actions.value`.
- **_flags_**: Keyword argument that gets passed to pythons `re.compile` function
- **_other args or kwargs_**: Any other positional arguments or keyword arguments not mentioned above will be passed to the function you are decorating

### `slack_controller.help_message`
This is used when the user types `help` in a channel to let them know what commands they have available to use. The named arguments map to the keys in the [Slack message attachements](https://api.slack.com/docs/message-attachments). The examples in this repo all follow a similar formatting, but they can be any combination of argumenst to fit the functions help message needs.
`@slack_controller.help_message(author_name="trigger:message", color="#3366ff", text="Type:\n> foobar")`


## Setting up a custom tunnel for development

To create an ssh tunnel for slack-actions development

### Server setup
1. Create a server and make sure it has ssh enabled.
2. Edit the `/etc/ssh/sshd_config` file with `sudo` and set `Gatewayports yes`

### Developing locally
1. From the client (your laptop) create a ssh tunnel by doing: `ssh -i ~/.ssh/id_rsa -NR 1337:localhost:5000 user@remote_host`
    - Port 5000 is the local port your application is running on
    - Port 1337 is the remote port and is how your application will be accessed by using the remote servers host.
    - Each user will have their own remote port they use for local development
2. Update your development slack app to point to the `remote_host:port` that you configured
3. Now everytime you want to develop the bot, just run the above ssh command found in step 1 and you are good to go
