from django.utils import timezone
from django.contrib.auth import models
from hikari import OwnUser

class DiscordUserOAuth2Manager(models.UserManager):
    def create_new_discord_user(self, user: OwnUser):
        new_user = self.create(
            id=user.id,
            avatar=user.avatar_hash if user.avatar_hash != None else 'none',
            public_flags=user.flags,
            flags=user.flags,
            locale=user.locale,
            mfa_enabled=user.is_mfa_enabled,
            discord_tag=f'{user.username}',
            last_login=timezone.now()
        )
        return new_user