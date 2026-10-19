from django.db import models
from django.contrib.postgres.fields import ArrayField

def meta_fields():
    return models.DateTimeField(auto_now_add=True), models.DateTimeField(auto_now=True)


class DiscordGuild(models.Model):
    created, updated = meta_fields()

    discord_id = models.BigIntegerField(primary_key=True)
    discord_name = models.CharField(max_length=100, default="NONE")
    discord_icon_url = models.TextField(null=True)
    discord_owner_user = models.BigIntegerField()
    discord_member_count = models.IntegerField()
    
    has_app = models.BooleanField(default=False)

class DiscordChannel(models.Model):
    created, updated = meta_fields()

    discord_id = models.BigIntegerField(primary_key=True)
    name = models.CharField(max_length=100, default="NONE")
    
    discord_guild = models.ForeignKey(to=DiscordGuild, on_delete=models.CASCADE, null=True)

class DiscordRole(models.Model):
    created, updated = meta_fields()

    discord_id = models.BigIntegerField(primary_key=True)
    discord_name = models.TextField()
    discord_guild = models.ForeignKey(to=DiscordGuild, on_delete=models.CASCADE, null=True)

class DiscordUser(models.Model):
    created, updated = meta_fields()

    id = models.BigIntegerField(primary_key=True)
    name = models.CharField(max_length=256)
    
    discord_guilds = ArrayField(models.BigIntegerField(null=False), default=list)
    
    @property
    def mention(self) -> str:
        return f"<@{self.id}>"
