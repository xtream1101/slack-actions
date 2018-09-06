from slack_actions.slack_controller import slack_controller


class Example:

    def __init__(self):
        # TODO: Make it so these can be directly on the class methods
        self.message_a = slack_controller.parser.trigger(['message'], {'text': 'fooA'})(self.message_a)
        self.message_a = slack_controller.parser.help(author_name="trigger:message",
                                                      color="#3366ff",
                                                      text="Type:\n> fooA")(self.message_a)

        self.upload_csv = slack_controller.parser.trigger(['message.file_share'],
                                                          {'files.filetype': "csv"})(self.upload_csv)
        self.upload_csv = slack_controller.parser.help(author_name="trigger:file upload",
                                                       color="#3366ff",
                                                       text="upload a csv file")(self.upload_csv)

        self.add_reaction = slack_controller.parser.trigger(['reaction_added'], {'reaction': '(.+)'})(self.add_reaction)
        self.add_reaction = slack_controller.parser.help(author_name="trigger:adding a reaction",
                                                         color="#3366ff",
                                                         text="Add a reaction and {} will react the same"
                                                              .format(slack_controller.BOT_NAME))(self.add_reaction)

    def message_a(self, output, full_event):
        message_data = {'text': 'fn: message_a',
                        # Respond in the thread if thats where the message was triggered from
                        'thread_ts': full_event['event']['event'].get('thread_ts'),
                        }
        return message_data

    def upload_csv(self, output, full_event):
        message_data = {'text': 'fn: upload_csv',
                        # Respond in the thread if thats where the file was uploaded to
                        'thread_ts': full_event['event']['event'].get('thread_ts'),
                        }
        return message_data

    def add_reaction(self, output, full_event):
        message_data = {'method': 'reactions.add',
                        'name': output['reaction'][0],
                        # Respond in the thread if thats where the file was uploaded to
                        'timestamp': full_event['event']['event']['item']['ts'],
                        }
        return message_data
