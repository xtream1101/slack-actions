from slack_actions.slack_controller import slack_controller


class UIElements:

    def __init__(self):
        # Dropdown menu
        self.menu = slack_controller.trigger(['message'], {'text': 'test menu'})(self.menu)
        self.menu = slack_controller.help_message(author_name="trigger:message",
                                                  color="#ffee55",
                                                  text="Type:\n> test menu")(self.menu)

        self.menu_action = slack_controller.trigger('interactive_message',
                                                    {'callback_id': 'game_selection',
                                                     'actions.selected_options.value': '(.*)'})(self.menu_action)

        # Buttons
        self.button = slack_controller.trigger(['message'], {'text': 'test button'})(self.button)
        self.button = slack_controller.help_message(author_name="trigger:message",
                                                    color="#ffee55",
                                                    text="Type:\n> test button")(self.button)

        self.button_action = slack_controller.trigger('interactive_message',
                                                      {'callback_id': 'wopr_game',
                                                       'actions.0.value': '(.*)'})(self.button_action)

    def menu(self, output, full_event):
        message_data = {
            "text": "Would you like to play a game?",
            "response_type": "in_channel",
            "attachments": [
                {
                    "text": "Choose a game to play",
                    "fallback": "If you could read this message, you'd be choosing something fun to do right now.",
                    "color": "#3AA3E3",
                    "attachment_type": "default",
                    "callback_id": "game_selection",
                    "actions": [
                        {
                            "name": "games_list",
                            "text": "Pick a game...",
                            "type": "select",
                            "options": [
                                {
                                    "text": "Hearts",
                                    "value": "hearts"
                                },
                                {
                                    "text": "Bridge",
                                    "value": "bridge"
                                },
                                {
                                    "text": "Checkers",
                                    "value": "checkers"
                                },
                                {
                                    "text": "Chess",
                                    "value": "chess"
                                },
                                {
                                    "text": "Poker",
                                    "value": "poker"
                                },
                                {
                                    "text": "Falken's Maze",
                                    "value": "maze"
                                },
                                {
                                    "text": "Global Thermonuclear War",
                                    "value": "war"
                                }
                            ]
                        }
                    ]
                }
            ]
        }
        return message_data

    def menu_action(self, output, full_event):
        message_data = {'method': 'chat.update',
                        'ts': full_event['event']['message_ts'],
                        'channel': full_event['channel']['id'],
                        'text': f"thanks for playing {output['actions.selected_options.value'][0]}!",
                        'attachments': []}
        slack_controller.slack_client.api_call(**message_data)

        user = f"<@{full_event['user']['id']}>"
        return {'text': f'I updated the message above with your answer {user}'}

    def button(self, output, full_event):
        message_data = {
            "text": "Would you like to play a game?",
            "attachments": [
                {
                    "text": "Choose a game to play",
                    "fallback": "You are unable to choose a game",
                    "callback_id": "wopr_game",
                    "color": "#3AA3E3",
                    "attachment_type": "default",
                    "actions": [
                        {
                            "name": "game",
                            "text": "Chess",
                            "type": "button",
                            "value": "chess"
                        },
                        {
                            "name": "game",
                            "text": "Falken's Maze",
                            "type": "button",
                            "value": "maze"
                        },
                        {
                            "name": "game",
                            "text": "Thermonuclear War",
                            "style": "danger",
                            "type": "button",
                            "value": "war",
                            "confirm": {
                                "title": "Are you sure?",
                                "text": "This sounds dangerous, are you really really sure?",
                                "ok_text": "Yes",
                                "dismiss_text": "No"
                            }
                        }
                    ]
                }
            ]
        }
        return message_data

    def button_action(self, output, full_event):
        user = f"<@{full_event['user']['id']}>"
        return {'text': f"{user}, you choose {output['actions.0.value'][0]}"}
