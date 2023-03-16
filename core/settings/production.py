"""
Django production settings for core project
"""
import os
import dj_database_url
import json
from google.oauth2 import service_account

DEBUG = True if (os.environ.get("DEBUG", "true").lower() == "true") else False

SLACK_CLIENT_ID = os.environ.get('SLACK_CLIENT_ID')
SLACK_CLIENT_SECRET = os.environ.get('SLACK_CLIENT_SECRET')
SLACK_SCOPE = os.environ.get('SLACK_SCOPE')
ORDER_CHANNEL = os.environ.get('ORDER_CHANNEL')

SLACK_PIPELINES = os.environ.get('SLACK_PIPELINES') # json.loads?

TACO_DAILY_LIMIT = os.environ.get('taco_daily_limit')

# Google Cloud Storage
DEFAULT_FILE_STORAGE = os.environ.get('DEFAULT_FILE_STORAGE')
GS_BUCKET_NAME = os.environ.get('GS_BUCKET_NAME')
STATICFILES_STORAGE = os.environ.get('STATICFILES_STORAGE')
TITO_GCS_CREDS = os.environ.get("GOOGLE_CREDENTIALS")
GS_CREDENTIALS = service_account.Credentials.from_service_account_info(TITO_GCS_CREDS)


# Databases
DEFAULT_CONNECTION = dj_database_url.parse(os.environ.get('DATABASE_URL'))
DATABASES = {'default': DEFAULT_CONNECTION}


NOTIFICATION_SETTINGS = json.loads(os.environ.get('NOTIFICATION_SETTINGS'))

EMOJI_NAME = os.environ.get('EMOJI_NAME')


TEAM_NAME = os.environ.get("TEAM_NAME")
TEAM_ID = os.environ.get("TEAM_ID")
SLACK_BOT_TOKEN = os.environ.get("SLACK_BOT_TOKEN")
SLACK_BOT_ID = os.environ.get("SLACK_BOT_ID")
