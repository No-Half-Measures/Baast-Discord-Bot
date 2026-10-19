import asyncio
import uuid
from asgiref.sync import sync_to_async
from django.conf import settings

from hikari import ComponentInteraction, InteractionCreateEvent, MessageFlag
from hikari.impl import ContainerComponentBuilder, SectionComponentBuilder, ThumbnailComponentBuilder, TextDisplayComponentBuilder
import lightbulb

from cache.models import DiscordGuild
from cache.helpers import save_discord_meta_models

from bot.bot.modals.feedback_modal import FeedbackModal

from loguru import logger

from django.conf import settings
SALT = getattr(settings, 'HASH_SALT', None)

loader = lightbulb.Loader()


def GetUser(users, index):
    return users[index]

@loader.listener(InteractionCreateEvent)
async def feedback_interaction(evt: InteractionCreateEvent, client: lightbulb.Client) -> None:
    if type(evt.interaction) is not ComponentInteraction:
        return
    if evt.interaction.custom_id != "leave_feedback":
        return
    
    interaction: ComponentInteraction = evt.interaction
    if interaction.user == None:
        logger.warning(f'Interaction Event contains a `None` User for message {interaction.message.id}')
        return
    
    modal = FeedbackModal()
    c_id: str = str(uuid.uuid4())
    
    await interaction.create_modal_response("Share your Feedback", c_id, components=modal)
    
    try:
        await modal.attach(client, c_id, timeout=300)
    except asyncio.TimeoutError:
        return
        
    feedback = modal.feedback
    
    if feedback == None or feedback == "":
        return
    
    try:
        guilds = await sync_to_async(DiscordGuild.objects.filter)(discord_owner_user=interaction.user.id, has_app=False)
    except DiscordGuild.DoesNotExist:
        return
    
    names = [guild.discord_name async for guild in guilds]
    ids = [guild.discord_id async for guild in guilds]
    
    #
    # Post feedback to Baast Discord Server
    #
    FeedbackComponents = [
        ContainerComponentBuilder(
                components=[
                    TextDisplayComponentBuilder(content=f"Guild: {ids} /n {names}"),
                    TextDisplayComponentBuilder(content=f"User: <@{interaction.user.id}>"),
                    TextDisplayComponentBuilder(content=f"Feedback: {feedback}"),
                ]
        ),
    ]
    
    try:
        await interaction.app.rest.create_message(1515344614553419898, components=FeedbackComponents, flags=MessageFlag.IS_COMPONENTS_V2)
    except Exception as e:
        return
    