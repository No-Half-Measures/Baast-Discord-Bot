"""
Management command to start the Discord connection pool health monitor.
Usage: python manage.py start_health_monitor
"""

import asyncio
import signal
import sys
from django.core.management.base import BaseCommand

from discord.health_monitor import start_health_monitoring, stop_health_monitoring

class Command(BaseCommand):
    help = 'Start the Discord connection pool health monitor'

    def add_arguments(self, parser):
        parser.add_argument(
            '--interval',
            type=int,
            default=30,
            help='Health check interval in seconds (default: 30)',
        )
        parser.add_argument(
            '--daemon',
            action='store_true',
            help='Run as daemon process',
        )

    def handle(self, *args, **options):
        interval = options['interval']
        daemon = options['daemon']
        
        self.stdout.write(f"Starting Discord connection pool health monitor...")
        self.stdout.write(f"Health check interval: {interval} seconds")
        
        if daemon:
            self.stdout.write("Running as daemon process")
        
        # Set up signal handlers for graceful shutdown
        def signal_handler(signum, frame):
            self.stdout.write("\nReceived shutdown signal, stopping health monitor...")
            asyncio.create_task(stop_health_monitoring())
            sys.exit(0)
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        # Run the health monitor
        try:
            asyncio.run(self._run_health_monitor(interval))
        except KeyboardInterrupt:
            self.stdout.write("\nHealth monitor stopped by user")
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Health monitor error: {e}"))
            sys.exit(1)

    async def _run_health_monitor(self, interval):
        """Run the health monitor with the specified interval."""
        # Update the interval in settings if needed
        from django.conf import settings
        settings.DISCORD_HEALTH_CHECK_INTERVAL = interval
        
        # Start the health monitor
        await start_health_monitoring()
        
        # Keep running until interrupted
        try:
            while True:
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            await stop_health_monitoring()
