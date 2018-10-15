from slack_actions.slack_controller import slack_controller


@slack_controller.trigger(['message'], {'text': '^echo (.+)'})
@slack_controller.help_message(author_name="trigger:message", color="#ffff1a", text="Type:\n> echo [word]")
def echo(output, full_event):
    message_data = {'text': f"`{output['text'][0]}`"}
    return message_data


@slack_controller.trigger(['message'], {'text': '^recho (.+)'})
@slack_controller.help_message(author_name="trigger:message", color="#ffff1a", text="Type:\n> recho [word]")
def recho(output, full_event):
    message_data = {'text': f"`{output['text'][0][::-1]}`"}
    return message_data
