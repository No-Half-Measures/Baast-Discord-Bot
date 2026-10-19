import os

from django.core.management import execute_from_command_line

#def run_asgi_workers(*channels):
if __name__ == '__main__':
    channels = None
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "bot.configuration.worker_settings")

    if not channels:
        channels = ('discord', )

    execute_from_command_line(('manage.py', 'runworker', *channels))