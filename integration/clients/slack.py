from integration.models import TeamUser, Team
from integration.clients.base import BaseClient
import re

from django.conf import settings
from slack_sdk.socket_mode import SocketModeClient
from slack_sdk.web import WebClient
from slack_sdk.socket_mode.response import SocketModeResponse
from slack_sdk.socket_mode.request import SocketModeRequest
import time

EMOJI = f":{settings.EMOJI_NAME}"

class Client(BaseClient):
    def __init__(self, team):
        self.team = team
        self.team_id = team.team_id
        self.team_name = team.name
        self.web_client = WebClient(token=team.bot_access_token)
        self.app_token = getattr(settings, 'SLACK_APP_TOKEN', None)

    def get_users(self, exclude_bots=True, include_deleted=False):
        res = self.web_client.users_list()
        users = res['members']
        if not exclude_bots and include_deleted:
            return users
        elif not exclude_bots and not include_deleted:
            return [user for user in res['members'] if not user['deleted']]
        return [user for user in res['members'] if not user['is_bot']
                and not user['deleted']]

    def log_users(self, users=None):
        if not users:
            users = self.get_users()
        team = Team.objects.get(team_id=self.team_id)
        for user in users:
            if not user['profile'].get('email'):
                continue
            TeamUser.objects\
                .update_or_create(team=team,
                                  user_team_id=user['id'],
                                  defaults={"email": user['profile']['email'],
                                            "details": user})

    def extract_mentions(self, text):
        return re.findall(r'<@([^>]*)>', text)

    def send_message(self, channel_id, text):
        self.web_client.chat_postMessage(
            channel=channel_id,
            as_user=True,
            text=text
        )

    def validate_token(self, request):
        return True

    def parse_event(self, payload):
        if 'event' in payload:
            event = payload['event']
            if event.get('type') == 'message' and not event.get('bot_id'):
                text = event.get('text', '')
                sender = event.get('user', '')
                channel = event.get('channel', '')
                if text and sender:
                    # Backward compatibility for text leaderboard trigger
                    if '@tito leaderboard' in text.lower():
                        self.send_message(channel, self.format_leaderboard(self.team))
                        return None
                    return (text, sender, channel)
        return None

    def process_socket_mode_req(self, client: SocketModeClient, req: SocketModeRequest):
        if req.type == "events_api":
            response = SocketModeResponse(envelope_id=req.envelope_id)
            client.send_socket_mode_response(response)
            parsed = self.parse_event(req.payload)
            if parsed and self.team:
                text, sender, channel = parsed
                self.handle_taco_message(text, sender, self.team, channel)
        elif req.type == "slash_commands":
            response = SocketModeResponse(envelope_id=req.envelope_id)
            client.send_socket_mode_response(response)
            payload = req.payload
            command = payload.get("command", "")
            if command == "/taco" and self.team:
                text = payload.get("text", "")
                sender = payload.get("user_id", "")
                channel = payload.get("channel_id", "")
                response_text = self.handle_slash_command(text, sender, self.team)
                if response_text:
                    self.send_message(channel, response_text)

    def parse_slash_command(self, payload):
        command = payload.get("command", "")
        if command == "/taco":
            text = payload.get("text", "")
            sender = payload.get("user_id", "")
            return (text, sender)
        return None


    def connect(self):
        print(f"Connecting to Slack Socket Mode for team {self.team_name}")
        if not self.app_token:
            print("ERROR: SLACK_APP_TOKEN not found in settings. Socket Mode requires an app-level token.")
            return
        socket_client = SocketModeClient(
            app_token=self.app_token,
            web_client=self.web_client
        )
        socket_client.socket_mode_request_listeners.append(self.process_socket_mode_req)
        socket_client.connect()
        while True:
            time.sleep(10)

