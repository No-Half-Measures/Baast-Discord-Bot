import uvicorn
import os

from django.core.management import execute_from_command_line

if __name__ == '__main__':
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "bot.configuration.http_settings")
   
    import django
    django.setup()

    address: str = "0.0.0.0"
    port: int = 8000
    uvicorn.run("baast.asgi:application", host=address, port=port)
