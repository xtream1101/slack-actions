from slack_actions.slack_controller import slack_controller


@slack_controller.trigger(['message'], {'text': 'bar'})
@slack_controller.help_message(author_name="trigger:message", color="#3366ff", text="Type:\n> bar")
def bar(output, full_event):
    # Make sure the function works the same as a class method
    message_data = {'text': 'fn: bar'}
    return message_data
