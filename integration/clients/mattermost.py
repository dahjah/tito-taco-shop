from integration.models import TeamUser, Team
from integration.clients.base import BaseClient
from ledger.models import TacoLedger, TacoBank
from django.conf import settings
from django.db.models import Sum
from datetime import date
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

    def format_balance(self, sender_id, team):
        given_today = TacoLedger.objects.filter(
            giver=sender_id, team=team,
            timestamp__date=date.today()
        ).aggregate(Sum('amount')).get('amount__sum', 0) or 0
        remaining = max(0, settings.TACO_DAILY_LIMIT - given_today)
        user = TeamUser.objects.filter(team=team, user_team_id=sender_id).first()
        if user:
            bank = TacoBank.objects.filter(user=user.user).first()
            if bank:
                return f"You have {remaining} tacos left to give today. Your current balance is {bank.total_tacos} tacos."
        return f"You have {remaining} tacos left to give today. You haven't received any tacos yet."

    def format_leaderboard(self, team):
        return "Leaderboard coming soon!"

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
        except Exception as e:
            print(f"Mattermost WS error: {e}")

    def connect(self):
        print(f"Connecting to Mattermost WebSocket for team {self.team_name}")
        self.driver.login()
        # mattermostdriver uses asyncio for websockets
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        self.driver.init_websocket(self._ws_handler)
        
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
