from django.urls import path, include
from . import views

urlpatterns = [
    #path('slack', views.oauth, name='slack-oauth'),
    path('', views.index),
    path('slack/oauth/', views.slack_oauth),
    path('slack/event/', views.slack_event),
    path('slack/command/', views.slash_command),
    path('mattermost/slash/', views.slash_command),
    path('mattermost/register/', views.mattermost_register),
]