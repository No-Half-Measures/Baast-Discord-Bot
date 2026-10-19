import sys
from asyncio import TimeoutError
from loguru import logger

from asgiref.sync import sync_to_async

from app.models import Config, Templates, Option_Presets

from hikari import ActionRowComponent, Emoji, undefined
from lightbulb import Context



async def GetTemplateActionRow(ctx: Context) -> ActionRowComponent:
    config: Config = await sync_to_async(Config.objects.get)(guild=ctx.get_guild().id)

    defaults = await sync_to_async(Templates.objects.filter)(gid = 1)
    guildsTmpts = []
    
    if config.is_premium:
        guildsTmpts = await sync_to_async(Templates.objects.filter)(gid = config.id)
    
    templates_list = await sync_to_async(list)(guildsTmpts | defaults)

    split_templates = [
        templates_list[i:i + 20] for i in range(0, len(templates_list), 20)
    ]  # Split the list into chunks of size 20
    

    for i, s in enumerate(split_templates, 1):
        selectMenu = ctx.app.rest.build_message_action_row().add_text_menu('get_Template', placeholder="Select a Template", min_values=1, max_values=1)

        for t in s:
            selectMenu.add_option(t.name, str(t.id), emoji=Emoji.parse(t.emoji) if t.emoji else undefined.UNDEFINED)
            
        return selectMenu
    return None

async def GetOptionsActionRow(ctx: Context, template: Templates, config: Config) -> ActionRowComponent:
    options_list: list[Option_Presets] = await sync_to_async(template.get_options)() # NEED a guild filter so people don't get other peopls options

    split_options = [
        options_list[i:i + 20] for i in range(0, len(options_list), 20)
    ]  # Split the list into chunks of size 20
    
    for i, s in enumerate(split_options, 1):
        selectMenu = ctx.app.rest.build_message_action_row().add_text_menu('get_signup_set', placeholder="Select a Sign-up set", min_values=1, max_values=1)

        for t in s:
            description = ''
            
            if t.len > 3 and not config.is_premium:
                #description = 'This server is not premium and this is a premium option.'
                pass
            else:
                for dic in t.options:
                    description += f"{dic['label']}, "
                description[0:100] # crop the description to 100 characters
                                    
                selectMenu.add_option(t.name, str(t.id), description=description)
            
        return selectMenu
    return None