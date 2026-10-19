from django.db import models
from django.contrib.postgres.fields import ArrayField
from .managers import DiscordUserOAuth2Manager


class User(models.Model):
    objects = DiscordUserOAuth2Manager()

    id = models.BigIntegerField(primary_key=True)
    discord_tag = models.CharField(max_length=100)
    avatar = models.CharField(max_length=100)
    public_flags = models.IntegerField()
    flags = models.IntegerField()
    locale = models.CharField(max_length=100)
    mfa_enabled = models.BooleanField()
    last_login = models.DateTimeField(null=True)

    is_staff = models.BooleanField(default=False)

    notifications_enabled = models.BooleanField(default=True)
    
    stripeCustomerId = models.CharField(max_length=100, null=True)

    @property
    def is_authenticated(self):
        return True

    @property
    def is_anonymous(self):
        return False

    @property
    def is_active(self):
        return True

    def has_module_perms(self, app_label):
        return True

    def has_perm(self, perm, obj=None):
        return True