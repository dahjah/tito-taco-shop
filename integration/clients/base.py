import re
from datetime import date
from django.conf import settings
from django.db.models import Sum


class BaseClient():
    EMOJI = 'taco'

    def handle_taco_message(self, text, sender, team, channel_id):
        recipients = re.findall(r'<@([^>]*)>', text)
        while sender in recipients:
            recipients.remove(sender)
        multi_tacos = re.findall(f'(?<={self.EMOJI}-)(\d+)(?=:)', text)
        num_tacos = text.count(f':{self.EMOJI}:') + sum(map(int, multi_tacos))
        if not recipients or not num_tacos:
            return
        if text.count(f':{self.EMOJI}:') > 1 and '\n' in text:
            for line in text.split('\n'):
                self.handle_taco_message(line, sender, team, channel_id)
            return
        from ledger.models import TacoLedger
        from ledger.tasks import get_or_create_team_user
        given_today = TacoLedger.objects.filter(
            giver=sender, team=team,
            timestamp__date=date.today()
        ).aggregate(Sum('amount')).get('amount__sum', 0) or 0
        tacos_remaining = settings.TACO_DAILY_LIMIT - (given_today + (num_tacos * len(recipients)))
        notif_settings = getattr(settings, 'NOTIFICATION_SETTINGS', {})
        if tacos_remaining >= 0:
            for recipient in set(recipients):
                get_or_create_team_user(team, recipient)
                TacoLedger.objects.create(
                    receiver=recipient,
                    giver=sender,
                    amount=num_tacos,
                    team=team
                )
                if notif_settings.get('SEND_AWARD_MESSAGE', True):
                    self.award_message(sender, recipient, num_tacos)
                if notif_settings.get('SEND_RECEIPT_CONFIRMATION', True):
                    self.confirmation_message(sender, recipient,
                                              num_tacos, tacos_remaining)
        else:
            self.overdraft(sender, recipients, tacos_remaining, num_tacos)

    def award_message(self, sender, receiver, amount):
        raise NotImplementedError

    def confirmation_message(self, sender, receiver, amount, remaining):
        raise NotImplementedError

    def overdraft(self, sender, recipients, remaining, amount):
        raise NotImplementedError

    def order_information(self, sender, receiver, item, size):
        raise NotImplementedError

    def receipt(self, sender, item, cost, remaining):
        raise NotImplementedError

    def handle_slash_command(self, text, sender_id, team):
        cmd = text.strip().lower()
        if cmd == 'leaderboard':
            return self.format_leaderboard(team)
        return self.format_balance(sender_id, team)

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
