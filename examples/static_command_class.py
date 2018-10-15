from slack_actions.slack_controller import slack_controller


class StaticCommandClass:

    # note: the static method decorator must precede the trigger and help_message decorators
    @staticmethod
    @slack_controller.trigger(['message'], {'text': 'fooA'})
    @slack_controller.help_message(author_name="trigger:message", color="#7575a3", text="Type:\n> fooA")
    def message_a(cls, output, full_event):
        message_data = {'text': 'fn: message_a',
                        # Respond in the thread if thats where the message was triggered from
                        'thread_ts': full_event['event'].get('thread_ts'),
                        }
        return message_data

    @staticmethod
    @slack_controller.trigger(['message.file_share'], {'files.filetype': "csv"})
    @slack_controller.help_message(author_name="trigger:file upload", color="#ff4000", text="upload a csv file")
    def upload_csv(cls, output, full_event):
        link = full_event['event']['files'][0]['url_private_download']
        file_id = full_event['event']['files'][0]['id']
        file_ = slack_controller.download(link, f'/tmp/{file_id}.csv')
        message_data = {'text': 'fn: upload_csv. Downloaded to the server at {}'.format(file_),
                        # Respond in the thread if thats where the file was uploaded to
                        'thread_ts': full_event['event'].get('thread_ts'),
                        }
        return message_data

    @staticmethod
    @slack_controller.trigger(['reaction_added'], {'reaction': '(.+)'})
    @slack_controller.help_message(author_name="trigger:adding a reaction", color="#8000ff",
                                   text="Add a reaction and {} will react the same".format(slack_controller.BOT_NAME))
    def add_reaction(cls, output, full_event):
        message_data = {'method': 'reactions.add',
                        'name': output['reaction'][0],
                        # Adds the reaction to the correct message
                        'timestamp': full_event['event']['item']['ts'],
                        }
        return message_data
