from .models import *
from user.models import User
from integration.models import TeamUser
from datetime import date
from django.conf import settings
from products.models import *

def get_or_create_team_user(team, platform_id, username=''):
    try:
        user = User.objects.get(unique_id=platform_id)
        if not user.team_user:
            team_user, _ = TeamUser.objects.get_or_create(
                team=team, user_team_id=platform_id,
                defaults={'email': user.email, 'details': {}}
            )
            user.team_user = team_user
            user.save()
    except User.DoesNotExist:
        user = User.objects.create(
            unique_id=platform_id, username=platform_id,
            first_name=username, email=f"{platform_id}@{team.name}.local"
        )
        team_user, _ = TeamUser.objects.get_or_create(
            team=team, user_team_id=platform_id,
            defaults={'email': user.email, 'details': {}}
        )
        user.team_user = team_user
        user.save()
    return user


def record_transaction(data, team=None):
    """
    Record taco transactions.
    """
    giver = data.get('giver_id')
    qs = TacoLedger.objects.filter(giver=giver, timestamp__date=date.today())
    if team:
        qs = qs.filter(team=team)
    tacos_given_today = qs.aggregate(Sum('amount')).get('amount__sum', 0) or 0
    transaction_amount = data.get('tacos')
    daily_limit = settings.TACO_DAILY_LIMIT
    if tacos_given_today >= daily_limit:
        return (False, 'Daily Limit reached')
    if tacos_given_today + transaction_amount > daily_limit:
        return (False, 'Not enough tacos to give')
    try:
        TacoLedger.objects.create(
            amount=transaction_amount,
            receiver=data.get('receiver_id'),
            giver=giver,
            team=team
        )
    except Exception as e:
        print(f'Error occurred in the Taco Ledger! {e}')
        return (False, 'Transaction Error')
    return (True, 'Transaction completed')


def purchase_item(item):
    """
    Call the chat integration.
    """
    pass


def redeem_tacos(data, team=None):
    """
    Redeem tacos by giving them to Tito.
    """
    user = User.objects.get(unique_id=data.get('user_id'))
    bank_account = TacoBank.objects.get(user=user)
    item = Product.objects.get(name=data.get('product_name'))
    if bank_account.total_tacos >= item.price:
        TacoLedger.objects.create(
            giver=data.get('user_id'),
            receiver=team.bot_user_id if team else settings.SLACK_BOT_ID,
            amount=data.get('amount'),
            team=team
        )
        purchase_item(item)
        return (True, 'Transaction complete')
    return (False, 'Not enough tacos to buy item')

