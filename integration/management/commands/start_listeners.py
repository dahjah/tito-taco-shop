from django.core.management.base import BaseCommand
from integration.models import Team
from integration.clients import get_client
from threading import Thread
import time

class Command(BaseCommand):
    help = 'Starts WebSocket listeners for all teams that support streaming'

    def handle(self, *args, **options):
        threads = []
        for team in Team.objects.all():
            try:
                client = get_client(team)
                if client.supports_streaming():
                    self.stdout.write(f"Starting listener for {team.chat_type} team: {team.name}")
                    thread = Thread(target=client.connect, daemon=True)
                    thread.start()
                    threads.append(thread)
            except Exception as e:
                self.stderr.write(f"Failed to start listener for team {team.name}: {e}")

        if not threads:
            self.stdout.write("No streaming listeners configured.")
            return

        self.stdout.write(f"Started {len(threads)} listeners. Keeping main thread alive...")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            self.stdout.write("Shutting down listeners...")
