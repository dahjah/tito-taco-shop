import re
from datetime import date
from django.conf import settings
from django.db.models import Sum


class BaseClient():
    EMOJI = 'taco'

    def handle_taco_message(self, text, sender, team, channel_id):
        recipients = self.extract_mentions(text)
        while sender in recipients:
            recipients.remove(sender)
        
        # Match :taco: or :taco-N:
        multi_tacos = re.findall(f':{self.EMOJI}-(\d+):', text)
        num_tacos = text.count(f':{self.EMOJI}:') + sum(map(int, multi_tacos))
        
        if not recipients or not num_tacos:
            return
            
        if text.count(f':{self.EMOJI}:') > 1 and '\n' in text:
            for line in text.split('\n'):
                self.handle_taco_message(line, sender, team, channel_id)
            return
            
        from ledger.models import TacoLedger, TacoBank
        from ledger.tasks import get_or_create_team_user
        
        given_today = TacoLedger.objects.filter(
            giver=sender, team=team,
            timestamp__date=date.today()
        ).aggregate(Sum('amount')).get('amount__sum', 0) or 0
        
        tacos_per_recipient = num_tacos
        total_requested = tacos_per_recipient * len(recipients)
        tacos_remaining = settings.TACO_DAILY_LIMIT - (given_today + total_requested)
        
        notif_settings = getattr(settings, 'NOTIFICATION_SETTINGS', {})
        
        if tacos_remaining >= 0:
            for recipient in set(recipients):
                get_or_create_team_user(team, recipient)
                TacoLedger.objects.create(
                    receiver=recipient,
                    giver=sender,
                    amount=tacos_per_recipient,
                    team=team
                )
                if notif_settings.get('SEND_AWARD_MESSAGE', True):
                    self.award_message(sender, recipient, tacos_per_recipient)
            
            if notif_settings.get('SEND_RECEIPT_CONFIRMATION', True):
                self.confirmation_message(sender, list(set(recipients))[0] if len(set(recipients)) == 1 else "multiple users", 
                                          total_requested, tacos_remaining)
        else:
            self.overdraft(sender, recipients, tacos_remaining, total_requested)

    def award_message(self, sender, receiver, amount):
        self.send_message(
            receiver,
            f"Congratulations! You have received {amount} " +
            f"{self.EMOJI}{'s' if amount > 1 else ''} from " +
            f"{self.mention_format(sender)}!"
        )

    def confirmation_message(self, sender, receiver, amount, remaining):
        receiver_display = self.mention_format(receiver) if receiver != "multiple users" else receiver
        self.send_message(
            sender,
            f"You have sent {amount} " +
            f"{self.EMOJI}{'s' if amount > 1 else ''} to " +
            f"{receiver_display}! You have {remaining} " +
            f"{self.EMOJI}{'s' if remaining > 1 else ''} remaining to give today."
        )

    def overdraft(self, sender, recipients, remaining, amount):
        self.send_message(
            sender,
            f"I regret to inform you that your taco transaction of " +
            f"{amount} {self.EMOJI}{'s' if amount > 1 else ''} to " +
            ", ".join([self.mention_format(i) for i in recipients]) +
            f" is impossible as you have {remaining} left to give today, " +
            "and the bank of Tito does not have good overdraft fees. " +
            "Please try again."
        )

    def order_information(self, sender, receiver, item, size):
        self.send_message(
            receiver,
            f"New Tito Taco Shop order has been placed by {self.mention_format(sender)}. They have purchased {item}. {'In Size: '+size if size else ''} Please arrange for them to receive this item. Thank you!"
        )

    def receipt(self, sender, item, cost, remaining):
        self.send_message(
            sender,
            f"You have purchased {item} for {cost} " +
            f"{self.EMOJI}{'s' if cost > 1 else ''}. " +
            f"You have {remaining} " +
            f"{self.EMOJI}{'s' if remaining > 1 else ''} remaining in your balance."
        )

    def handle_slash_command(self, text, sender_id, team):
        cmd = text.strip().lower()
        if cmd == 'leaderboard':
            return self.format_leaderboard(team)
        return self.format_balance(sender_id, team)

    def format_balance(self, sender_id, team):
        from ledger.models import TacoLedger, TacoBank
        from integration.models import TeamUser
        
        given_today = TacoLedger.objects.filter(
            giver=sender_id, team=team,
            timestamp__date=date.today()
        ).aggregate(Sum('amount')).get('amount__sum', 0) or 0
        remaining = max(0, settings.TACO_DAILY_LIMIT - given_today)
        user = TeamUser.objects.filter(team=team, user_team_id=sender_id).first()
        if user:
            bank = TacoBank.objects.filter(user=user.user).first()
            if bank:
                return f"You have {remaining} {self.EMOJI}s left to give today. Your current balance is {bank.total_tacos} {self.EMOJI}s."
        return f"You have {remaining} {self.EMOJI}s left to give today. You haven't received any {self.EMOJI}s yet."

    def format_leaderboard(self, team):
        return "Leaderboard coming soon!"

    def mention_format(self, user_id):
        return f"<@{user_id}>"

    def supports_streaming(self):
        return True

    def extract_mentions(self, text):
        raise NotImplementedError

    def send_message(self, channel_id, text):
        raise NotImplementedError

    def validate_token(self, request):
        raise NotImplementedError

    def parse_event(self, payload):
        raise NotImplementedError

    def parse_slash_command(self, payload):
        raise NotImplementedError

    def connect(self):
        raise NotImplementedError
