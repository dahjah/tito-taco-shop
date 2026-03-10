from django.shortcuts import render
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
import requests, json
from .models import Team
from django.http import HttpResponse, JsonResponse
from integration.clients import get_client


def index(request):
    client_id = settings.SLACK_CLIENT_ID
    return render(request, 'slack_landing.html', {'client_id': client_id})


def slack_oauth(request):
    code = request.GET['code']
    
    params = { 
        'code': code,
        'client_id': settings.SLACK_CLIENT_ID,
        'client_secret': settings.SLACK_CLIENT_SECRET
    }
    url = 'https://slack.com/api/oauth.access'
    json_response = requests.get(url, params)
    data = json.loads(json_response.text)
    Team.objects.create(
        name=data['team_name'], 
        team_id=data['team_id'],
        bot_user_id=data['bot']['bot_user_id'],     
        bot_access_token=data['bot']['bot_access_token'],
        chat_type="slack"
    )
    return HttpResponse('Bot added to your Slack team!')

@csrf_exempt
def slack_event(request):
    if request.method == 'POST':
        payload = json.loads(request.body)
        if 'challenge' in payload:
            return JsonResponse({'challenge': payload['challenge']})
        team_id = payload.get('team_id')
        if team_id:
            team = Team.objects.filter(team_id=team_id, chat_type='slack').first()
            if team:
                client = get_client(team)
                if client.validate_token(request):
                    parsed = client.parse_event(payload)
                    if parsed:
                        text, sender, channel = parsed
                        client.handle_taco_message(text, sender, team, channel)
        return HttpResponse(status=200)
    return HttpResponse(status=405)

@csrf_exempt
def slack_command(request):
    if request.method == 'POST':
        team_id = request.POST.get('team_id')
        if team_id:
            team = Team.objects.filter(team_id=team_id, chat_type='slack').first()
            if team:
                client = get_client(team)
                if client.validate_token(request):
                    parsed = client.parse_slash_command(request.POST)
                    if parsed:
                        text, sender = parsed
                        response_text = client.handle_slash_command(text, sender, team)
                        if response_text:
                            return JsonResponse({"response_type": "ephemeral", "text": response_text})
        return HttpResponse(status=200)
    return HttpResponse(status=405)

@csrf_exempt
def mattermost_slash(request):
    if request.method == 'POST':
        team_id = request.POST.get('team_id') # Usually the MM server identifier or team string
        # Typically the plugin will send some identifying token we can look up
        bot_token = request.POST.get('token')
        if bot_token:
            team = Team.objects.filter(bot_access_token=bot_token, chat_type='mattermost').first()
            if team:
                client = get_client(team)
                if client.validate_token(request):
                    parsed = client.parse_slash_command(request.POST)
                    if parsed:
                        text, sender = parsed
                        response_text = client.handle_slash_command(text, sender, team)
                        if response_text:
                            return JsonResponse({"response_type": "ephemeral", "text": response_text})
        return HttpResponse(status=200)
    return HttpResponse(status=405)

@csrf_exempt
def mattermost_register(request):
    if request.method == 'POST':
        try:
            payload = json.loads(request.body)
            team_id = payload.get('team_id')
            bot_token = payload.get('bot_token')
            bot_user_id = payload.get('bot_user_id')
            site_url = payload.get('site_url')
            team_name = payload.get('team_name', 'Mattermost Team')
            
            if team_id and bot_token and site_url:
                Team.objects.update_or_create(
                    team_id=team_id,
                    chat_type='mattermost',
                    defaults={
                        'name': team_name,
                        'bot_access_token': bot_token,
                        'bot_user_id': bot_user_id,
                        'details': {'backend_url': site_url}
                    }
                )
                return JsonResponse({'status': 'registered'})
        except json.JSONDecodeError:
            pass
    return HttpResponse(status=400)