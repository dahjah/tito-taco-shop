from django.test import TestCase, override_settings
from django.contrib.auth import get_user_model
from integration.models import Team, TeamUser
from integration.clients.base import BaseClient
from integration.clients.slack import Client as SlackClient
from ledger.models import TacoLedger
from unittest.mock import patch, MagicMock
import re

User = get_user_model()

class DummyClient(BaseClient):
    def __init__(self):
        self.awards = []
        self.confirmations = []
        self.overdrafts = []

    def award_message(self, sender, receiver, amount):
        self.awards.append((sender, receiver, amount))

    def confirmation_message(self, sender, receiver, amount, remaining):
        self.confirmations.append((sender, receiver, amount, remaining))

    def overdraft(self, sender, recipients, remaining, amount):
        self.overdrafts.append((sender, recipients, remaining, amount))

    def extract_mentions(self, text):
        return re.findall(r'<@([^>]*)>', text)

    # stubs
    def order_information(self, sender, receiver, item, size): pass
    def receipt(self, sender, item, cost, remaining): pass
    def send_message(self, channel_id, text): pass
    def validate_token(self, request): return True
    def parse_event(self, payload): return None
    def parse_slash_command(self, payload): return None
    def connect(self): pass


@override_settings(TACO_DAILY_LIMIT=5, NOTIFICATION_SETTINGS={'SEND_AWARD_MESSAGE': True, 'SEND_RECEIPT_CONFIRMATION': True})
class BaseClientTests(TestCase):
    def setUp(self):
        self.team = Team.objects.create(name="Test Team", team_id="T1", bot_user_id="U1", chat_type="slack")
        self.client = DummyClient()

    def test_basic_award(self):
        self.client.handle_taco_message("<@user2> :taco:", "user1", self.team, "C1")
        self.assertEqual(TacoLedger.objects.count(), 1)
        ledger = TacoLedger.objects.first()
        self.assertEqual(ledger.giver, "user1")
        self.assertEqual(ledger.receiver, "user2")
        self.assertEqual(ledger.amount, 1)
        self.assertEqual(ledger.team, self.team)
        self.assertEqual(len(self.client.awards), 1)
        self.assertEqual(len(self.client.confirmations), 1)

    def test_multi_taco_award(self):
        self.client.handle_taco_message("<@user2> :taco-3:", "user1", self.team, "C1")
        ledger = TacoLedger.objects.first()
        self.assertEqual(ledger.amount, 3)
        self.assertEqual(self.client.awards[0][2], 3)

    def test_self_taco(self):
        self.client.handle_taco_message("<@user1> :taco:", "user1", self.team, "C1")
        self.assertEqual(TacoLedger.objects.count(), 0)
        self.assertEqual(len(self.client.awards), 0)

    def test_overdraft(self):
        self.client.handle_taco_message("<@user2> :taco-6:", "user1", self.team, "C1")
        self.assertEqual(TacoLedger.objects.count(), 0)
        self.assertEqual(len(self.client.overdrafts), 1)
        # Should overdraft when 5 limit, 6 requested
        self.assertEqual(self.client.overdrafts[0][2], -1) # remaining
        self.assertEqual(self.client.overdrafts[0][3], 6) # requested amount

    def test_multiple_recipients(self):
        self.client.handle_taco_message("<@user2> <@user3> :taco:", "user1", self.team, "C1")
        self.assertEqual(TacoLedger.objects.count(), 2)

    def test_team_isolation(self):
        team2 = Team.objects.create(name="Team 2", team_id="T2", bot_user_id="U1", chat_type="slack")
        self.client.handle_taco_message("<@user2> :taco-5:", "user1", self.team, "C1")
        self.assertEqual(TacoLedger.objects.filter(team=self.team).count(), 1)
        
        # User 1 should have fresh 5 tacos on Team 2
        self.client.handle_taco_message("<@user2> :taco-5:", "user1", team2, "C1")
        self.assertEqual(TacoLedger.objects.filter(team=team2).count(), 1)
        self.assertEqual(len(self.client.overdrafts), 0)


class SlackClientTests(TestCase):
    def setUp(self):
        self.team = Team.objects.create(
            name="Slack Team", 
            team_id="SLACK_T1", 
            bot_user_id="B1", 
            bot_access_token="xoxb-test",
            chat_type="slack"
        )
        self.client = SlackClient(team=self.team)
        self.client.web_client = MagicMock()

    def test_get_users(self):
        # The client.web_client is a MagicMock
        mock_web = self.client.web_client
        mock_web.users_list.return_value = {
            'members': [
                {'id': 'U1', 'is_bot': False, 'deleted': False, 'profile': {'email': 'u1@test.com'}},
                {'id': 'B1', 'is_bot': True, 'deleted': False, 'profile': {'email': 'bot@test.com'}},
                {'id': 'D1', 'is_bot': False, 'deleted': True, 'profile': {'email': 'd1@test.com'}},
            ]
        }
        
        # Test default filtering (exclude bots and deleted)
        users = self.client.get_users()
        self.assertEqual(len(users), 1)
        self.assertEqual(users[0]['id'], 'U1')
        
        # Test include bots
        users = self.client.get_users(exclude_bots=False)
        self.assertEqual(len(users), 2)
        
        # Verify the mock was called (this ensures we aren't using self.client.users_list which would throw AttributeError)
        mock_web.users_list.assert_called()

    def test_log_users(self):
        mock_web = self.client.web_client
        mock_web.users_list.return_value = {
            'members': [
                {'id': 'U1', 'is_bot': False, 'deleted': False, 'profile': {'email': 'u1@test.com'}},
                {'id': 'U2', 'is_bot': False, 'deleted': False, 'profile': {'email': 'u2@test.com'}},
            ]
        }
        
        # Ensure TeamUser and User models work together
        self.client.log_users()
        
        self.assertEqual(TeamUser.objects.count(), 2)
        u1 = TeamUser.objects.get(user_team_id='U1')
        self.assertEqual(u1.email, 'u1@test.com')
        self.assertEqual(u1.team, self.team)
