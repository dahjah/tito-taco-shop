from django.core.management.base import BaseCommand
from integration.models import Team
from integration.clients import get_client
from threading import Thread
import time

class Command(BaseCommand):
    help = 'Starts WebSocket listeners for all teams that support streaming'

    def handle(self, *args, **options):
        active_teams = set()
        self.stdout.write("Starting streaming listener manager...")
        
        try:
            while True:
                # Check for any new teams that have appeared in the DB
                for team in Team.objects.all():
                    if team.id not in active_teams:
                        try:
                            client = get_client(team)
                            if client.supports_streaming():
                                self.stdout.write(f"Starting listener for {team.chat_type} team: {team.name}")
                                thread = Thread(target=client.connect, daemon=True)
                                thread.start()
                                active_teams.add(team.id)
                        except Exception as e:
                            self.stderr.write(f"Failed to start listener for team {team.name}: {e}")
                            
                # Sleep for 10 seconds before checking again
                time.sleep(10)
        except KeyboardInterrupt:
            self.stdout.write("Shutting down listeners...")
