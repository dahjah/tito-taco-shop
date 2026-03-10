from integration.models import TeamUser, Team
from integration.clients.base import BaseClient
from mattermostdriver import Driver
import asyncio
import json
import re


class Client(BaseClient):
    def __init__(self, team):
        self.team = team
        self.team_id = team.team_id
        self.team_name = team.name
        
        # Init driver for API calls and WebSocket
        self.driver = Driver({
            'url': team.details.get('backend_url', '').replace('https://', '').replace('http://', ''),
            'token': team.bot_access_token,
            'scheme': 'https' if team.details.get('backend_url', '').startswith('https') else 'http',
            'port': 443 if team.details.get('backend_url', '').startswith('https') else 80,
            'verify': True
        })

    def extract_mentions(self, text):
        usernames = re.findall(r'@([a-zA-Z0-9_\-\.]+)', text)
        recipients = []
        for username in usernames:

            user_list = self.driver.users.get_users(params={'usernames': username})
            if user_list:
                recipients.append(user_list[0]['id'])
        return recipients

    def send_message(self, channel_id, text):
        self.driver.login()
        self.driver.posts.create_post({
            'channel_id': channel_id,
            'message': text
        })


    def validate_token(self, request):
        if request.POST.get('token') == self.team.bot_access_token:
            return True
        return False

    def parse_event(self, payload):
        # We don't use this directly since WebSocket parses its own
        return None

    def parse_slash_command(self, payload):
        command = payload.get('command', '')
        if command == '/taco':
            text = payload.get('text', '')
            sender = payload.get('user_id', '')
            return (text, sender)
        return None


    def connect(self):
        print(f"Connecting to Mattermost WebSocket for team {self.team_name}")
        self.driver.login()
        # mattermostdriver uses asyncio for websockets
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        self.driver.init_websocket(self._ws_handler)

    async def _ws_handler(self, message):
        try:
            msg = json.loads(message)
            if msg.get('event') == 'posted':
                post = json.loads(msg['data']['post'])
                text = post.get('message', '')
                sender = post.get('user_id', '')
                channel = post.get('channel_id', '')
                # Don't listen to our own bot
                bot_user = self.driver.users.get_user('me')
                if sender != bot_user['id']:
                    if self.team:
                        self.handle_taco_message(text, sender, self.team, channel)
        except Exception:
            pass
