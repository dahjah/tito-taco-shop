from django.db import models
from django.db.models import Sum
from django.db.models import Q
from django.conf import settings
from user.models import User
import datetime


class TacoLedger(models.Model):
    amount = models.IntegerField()
    timestamp = models.DateTimeField(auto_now_add=True)
    receiver = models.CharField(max_length=100)
    giver = models.CharField(max_length=100)
    details = models.JSONField(blank=True, null=True, default=dict)

    def __str__(self):
        return f'{self.timestamp}: {self.giver} --> {self.receiver}, {self.amount} tacos'


class TacoBank(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['user'],
                name='Taco Shop Bank'
            )
        ]

    def __str__(self):
        return f'Bank: {self.user}, amount: {self.total_tacos}'

    @property
    def total_given(self):
        amount = TacoLedger.objects.filter(~Q(receiver=settings.SLACK_BOT_ID), giver=self.user.unique_id).aggregate(Sum('amount'))
        return amount['amount__sum'] if amount.get('amount__sum') else 0

    @property
    def total_received(self):
        amount = TacoLedger.objects.filter(receiver=self.user.unique_id).aggregate(Sum('amount'))
        return amount['amount__sum'] if amount.get('amount__sum') else 0

    @property
    def total_redeemed(self):
        amount = TacoLedger.objects.filter(giver=self.user.unique_id, receiver=settings.SLACK_BOT_ID).aggregate(Sum('amount'))
        return amount['amount__sum'] if amount.get('amount__sum') else 0

    @property
    def total_tacos(self):
        amount = (self.total_given + self.total_received) - self.total_redeemed
        return amount if amount > 0 else 0

    @property
    def total_purchases(self):
        amount = TacoLedger.objects.filter(giver=self.user.unique_id,
                                           receiver=settings.SLACK_BOT_ID,
                                           ).count()
        return amount if amount else 0

    @property
    def total_purchases_curr_month(self):
        today = datetime.datetime.now()
        amount = TacoLedger.objects.filter(giver=self.user.unique_id,
                                           receiver=settings.SLACK_BOT_ID,
                                           timestamp__year=today.year,
                                           timestamp__month=today.month
                                           ).count()
        return amount if amount else 0

    @property
    def total_purchases_today(self):
        today = datetime.datetime.now()
        amount = TacoLedger.objects.filter(giver=self.user.unique_id,
                                           receiver=settings.SLACK_BOT_ID,
                                           timestamp__year=today.year,
                                           timestamp__month=today.month,
                                           timestamp__day=today.day
                                           ).count()
        return amount if amount else 0
