from slack_sdk.socket_mode import SocketModeClient
from slack_sdk.web import WebClient
from slack_sdk.socket_mode.response import SocketModeResponse
from slack_sdk.socket_mode.request import SocketModeRequest
from integration.models import TeamUser, Team
from integration.clients.base import BaseClient
from ledger.models import TacoLedger, TacoBank
from django.conf import settings
from django.db.models import Sum
from datetime import datetime
import functools
import re

EMOJI = f":{settings.EMOJI_NAME}"

class Client(BaseClient):
    def __init__(self, team_id=None, team_name=None, bot_token=None, team=None):
        if team:
            self.team = team
            self.team_id = team.team_id
            self.team_name = team.name
            bot_token = team.bot_access_token
        else:
            self.team = None
            self.team_id = team_id
            self.team_name = team_name
        self.web_client = WebClient(token=bot_token)
        self.app_token = getattr(settings, 'SLACK_APP_TOKEN', None)

    def get_users(self, exclude_bots=True, include_deleted=False):
        res = self.client.users_list()
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
        recipients = re.findall(r'<@([^>]*)>', text)
        return recipients

    def send_message(self, channel_id, text):
        self.web_client.chat_postMessage(
            channel=channel_id,
            as_user=True,
            text=text
        )

    def award_message(self, sender, receiver, amount):
        self.send_message(
            receiver,
            f"Congratulations! You have received {amount} " +
            f"taco{'s' if amount > 1 else ''} from " +
            f"<@{sender}>!"
        )

    def confirmation_message(self, sender, receiver, amount, remaining):
        self.send_message(
            sender,
            f"You have sent {amount} " +
            f"taco{'s' if amount > 1 else ''} to " +
            f"<@{receiver}>! You have {remaining} " +
            f"taco{'s' if remaining > 1 else ''} remaining to give today."
        )

    def overdraft(self, sender, recipients, remaining, amount):
        self.send_message(
            sender,
            f"I regret to inform you that your taco transaction of " +
            f"{amount} taco{'s' if amount > 1 else ''} to " +
            ", ".join([f"<@{i}>" for i in recipients]) +
            f" is impossible as you have {remaining} left to give today, " +
            "and the bank of Tito does not have good overdraft fees. " +
            "Please try again."
        )

    def validate_token(self, request):
        # Implement Slack signing secret validation here if desired
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

    def format_balance(self, sender_id, team):
        given_today = TacoLedger.objects.filter(
            giver=sender_id, team=team,
            timestamp__date=datetime.now().date()
        ).aggregate(Sum('amount')).get('amount__sum', 0) or 0
        remaining = max(0, settings.TACO_DAILY_LIMIT - given_today)
        user = TeamUser.objects.filter(team=team, user_team_id=sender_id).first()
        if user:
            bank = TacoBank.objects.filter(user=user.user).first()
            if bank:
                return f"You have {remaining} tacos left to give today. Your current balance is {bank.total_tacos} tacos."
        return f"You have {remaining} tacos left to give today. You haven't received any tacos yet."

    def format_leaderboard(self, team):
        # Quick and dirty stub, implement actual leaderboard logic later if needed
        return "Leaderboard coming soon!"

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
        import time
        while True:
            time.sleep(10)

    def order_information(self, sender, receiver, item, size):
        self.send_message(
            receiver,
            f"New Tito Taco Shop order has been placed by <@{sender}>. They have purchased {item}. {'In Size: '+size if size else ''} Please arrange for them to receive this item. Thank you!"
        )

    def receipt(self, sender, item, cost, remaining):
        self.send_message(
            sender,
            f"You have purchased {item} for {cost} " +
            f"taco{'s' if cost > 1 else ''}." +
            f"You have {remaining} " +
            f"taco{'s' if remaining > 1 else ''} remaining in your balance."
        )
