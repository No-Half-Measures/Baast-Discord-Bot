from django.contrib.auth.backends import BaseBackend
from .models import User

from hikari import OwnUser

class DiscordAuthenticationBackend(BaseBackend):
    def authenticate(self, request, user: OwnUser) -> User:
        find_user = User.objects.filter(id=user.id)
        if len(find_user) == 0:
            print('User was not found. Saving...')
            new_user = User.objects.create_new_discord_user(user)
            return User.objects.filter(id=user.id)
        print('User was found. Returning...')
        return find_user

    def get_user(self, user_id):
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None