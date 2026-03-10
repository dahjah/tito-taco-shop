from django.db import models
from django.contrib.auth import get_user_model
User = get_user_model()

# Create your models here.


class Team(models.Model):
    TEAM_TYPES = [("slack", "Slack"),
                  ("discord", "Discord"),
                  ("mattermost", "Mattermost")]
    name = models.CharField(max_length=200)
    team_id = models.CharField(max_length=20)
    bot_user_id = models.CharField(max_length=20)
    bot_access_token = models.CharField(max_length=100)
    details = models.JSONField(default=dict, blank=True)
    chat_type = models.CharField(max_length=25, choices=TEAM_TYPES)

    def __str__(self):
        return f"{self.chat_type}-{self.team_id}: {self.name}"


class TeamUser(models.Model):
    team = models.ForeignKey(Team, on_delete=models.CASCADE)
    user_team_id = models.CharField(max_length=255)
    email = models.CharField(max_length=255)
    details = models.JSONField()

    def __str__(self):
        return f"{self.team.chat_type}:{self.team.name}-{self.email}"