import sys, asyncio, arrow
from datetime import timedelta
from asgiref.sync import sync_to_async
from importlib import import_module
from typing import Sequence

from channels.consumer import AsyncConsumer
from hikari.impl import ContainerComponentBuilder, MediaGalleryComponentBuilder, MediaGalleryItemBuilder, TextDisplayComponentBuilder, SeparatorComponentBuilder, SectionComponentBuilder, LinkButtonBuilder
import lightbulb

from hikari import (LazyIterator, Locale, Embed, GuildTextChannel, NotFoundError, ForbiddenError, Member, OwnGuild, RESTGuild, Role, GuildPrivateThread, MessageFlag, SpacingType,
                    Message, Permissions, PartialCommand, GuildCommandPermissions, CommandPermission, CommandPermissionType, errors)
from hikari.events import StartingEvent

from loguru import logger

from app.models import Events, Events_Links, Config, Templates, Preset_Roles, Attendance
from bot.exceptions import BotNotRunning
from bot.bot.modules.events.classes.calendar import Calendar
from bot.bot.modules.events.classes.sheet import Sheet
from bot.bot.utils.enums import SignupOption
from bot.bot.utils.event_utils import RebuildEventEmbed, BuildComponents, roles_to_string, update_event_thread, update_other_events_messages
from bot.bot.utils.util import has_permissions
from bot.bot.utils.thread_helpers import ThreadHasUser
from cache.helpers import save_discord_meta_models, _safe_get_cache_view

from bot.datatypes import DjangoDiscordPlugin
from bot.bot.app import Baast

background_tasks = set()
cache = None

class DiscordConsumer(AsyncConsumer):
    bot_task: asyncio.Task = None
    bot: Baast = None
    client: lightbulb.GatewayEnabledClient = None

    async def start_discord_bot(self, event):
        logger.debug("Received start signal")
        if self.is_bot_running():
            logger.debug("Bot is already running, doing nothing")
            return

        logger.debug("Unpacking signal for bot parameters")
        bot_path = event['bot_path']
        reconnect: bool = event['reconnect']

        # log_handler: Optional[logging.Handler] = event.get('log_handler', None)
        # log_formatter: logging.Formatter = event.get('log_formatter', None)
        # log_level: int = event.get('log_level', None)
        # root_logger: bool = event.get('root_logger', False)

        logger.debug(f"Importing '{bot_path}' ...")
        
        try:
            self.bot: Baast = Baast(version="3.0.0")
        except Exception as e:
            logger.error(f"Failed to start the bot: {e}")
            return
        
        
        localization_provider = lightbulb.DictLocalizationProvider({
            Locale.EN_US: {
                #Cache
                "extensions.cache.name": "cache",
                "extensions.cache.description": "Cache Command group.",
                "extensions.cache_update.name": "update",
                "extensions.cache_update.description": "Update the cache for a guild.",
                #Help
                "extensions.help.name": "help",
                "extensions.help.description": "Help Command on how to get started.",
                #Reminders
                "extensions.reminder.name": "reminder",
                "extensions.reminder.description": "Enable of Disable event reminders for yourself.",
                #Sheet
                "extensions.sheet.name": "sheet",
                "extensions.sheet.description": "Sheet Commands Group.",
                "extensions.sheet_adduser.name": "adduser",
                "extensions.sheet_adduser.description": "Add a user to the sheet.",
                "extensions.sheet_edituser.name": "edituser",
                "extensions.sheet_edituser.description": "Edit a user on the sheet.",
                "extensions.sheet_removeuser.name": "removeuser",
                "extensions.sheet_removeuser.description": "Remove a user from the sheet.",
                "extensions.sheet.option.permission.reader": "reader",
                "extensions.sheet.option.permission.writer": "writer",
                "extensions.sheet_url.name": "url",
                "extensions.sheet_url.description": "Get the spreadsheet url.",
                #User
                "extensions.user.name": "user",
                "extensions.user.description": "User Commands Group.",
                "extensions.user_info.name": "info",
                "extensions.user_info.description": "Get info on a user.",
                #Config
                "extensions.config.name": "config",
                "extensions.config.description": "Config Commands Group.",
                "extensions.config_edit.name": "edit",
                "extensions.config_edit.description": "Guild configuration set-up.",
                #Event
                "extensions.dev.name": "dev",
                "extensions.dev.description": "Dev Commands Group.",
                "extensions.dev.event_refresh.name": "event_refresh",
                "extensions.dev.event_refresh.description": "Refresh all events.",
                "extensions.event.name": "event",
                "extensions.event.description": "Event Commands Group.",
                "extensions.event_create.name": "create",
                "extensions.event_create.description": "Creates a new event.",
                "extensions.event_restore.name": "restore",
                "extensions.event_restore.description": "Restores a deleted event.",
                "extensions.event_info.name": "info",
                "extensions.event_info.description": "Gets an events information.",
                "extensions.event_share.name": "share",
                "extensions.event_share.description": "Share an event to another guild for joint events.",
                "extensions.event_unshare.name": "unshare",
                "extensions.event_unshare.description": "Remove a Shared event with a guild.",
                #Calendar
                "extensions.calendar.name": "calendar",
                "extensions.calendar.description": "Calendar Commands Group.",
                "extensions.calendar_private.name": "private",
                "extensions.calendar_private.description": "Set the calendar to private or public.",
                "extensions.calendar_permission.name": "permission",
                "extensions.calendar_permission.description": "Set the permissions of an email for the calendar.",
                "extensions.calendar_permission.option.permission.reader": "Reader",
                "extensions.calendar_permission.option.permission.writer": "Writer",
                "extensions.calendar_permission.option.permission.owner": "Owner",
                "extensions.calendar_enable.name": "enable",
                "extensions.calendar_enable.description": "Enable the calendar for this server.",
                "extensions.calendar_link.name": "url",
                "extensions.calendar_link.description": "Get the calendar url.",
            },
            Locale.DE: {
                #Cache
                "extensions.cache.name": "cache",
                "extensions.cache.description": "Cache-Befehlsgruppe.",
                "extensions.cache_update.name": "aktualisieren",
                "extensions.cache_update.description": "Den Cache für eine Gilde aktualisieren.",
                #Help
                "extensions.help.name": "hilfe",
                "extensions.help.description": "Hilfebefehl zum Einstieg.",
                #Reminders
                "extensions.reminder.name": "erinnerung",
                "extensions.reminder.description": "Aktivieren oder Deaktivieren von Ereigniserinnerungen für dich selbst.",
                #Sheet
                "extensions.sheet.name": "tabelle",
                "extensions.sheet.description": "Tabellen-Befehlsgruppe.",
                "extensions.sheet_adduser.name": "benutzerhinzufuegen",
                "extensions.sheet_adduser.description": "Einen Benutzer zur Tabelle hinzufügen.",
                "extensions.sheet_edituser.name": "benutzerbearbeiten",
                "extensions.sheet_edituser.description": "Einen Benutzer in der Tabelle bearbeiten.",
                "extensions.sheet_removeuser.name": "benutzerentfernen",
                "extensions.sheet_removeuser.description": "Einen Benutzer aus der Tabelle entfernen.",
                "extensions.sheet.option.permission.reader": "reader",
                "extensions.sheet.option.permission.writer": "writer",
                "extensions.sheet_url.name": "url",
                "extensions.sheet_url.description": "Die Tabellen-URL abrufen.",
                #User
                "extensions.user.name": "benutzer",
                "extensions.user.description": "Benutzerbefehlsgruppe.",
                "extensions.user_info.name": "info",
                "extensions.user_info.description": "Informationen zu einem Benutzer abrufen.",
                #Config
                "extensions.config.name": "konfiguration",
                "extensions.config.description": "Konfigurations-Befehlsgruppe.",
                "extensions.config_edit.name": "bearbeiten",
                "extensions.config_edit.description": "Gildenkonfiguration einrichten.",
                #Event
                "extensions.event.name": "ereignis",
                "extensions.event.description": "Ereignis-Befehlsgruppe.",
                "extensions.event_create.name": "erstellen",
                "extensions.event_create.description": "Erstellt ein neues Ereignis.",
                "extensions.event_restore.name": "wiederherstellen",
                "extensions.event_restore.description": "Ein gelöschtes Ereignis wiederherstellen.",
                "extensions.event_info.name": "info",
                "extensions.event_info.description": "Informationen zu einem Ereignis abrufen.",
                "extensions.event_share.name": "teilen",
                "extensions.event_share.description": "Ein Ereignis mit einer anderen Gilde für gemeinsame Events teilen.",
                "extensions.event_unshare.name": "nichtteilen",
                "extensions.event_unshare.description": "Ein gemeinsames Ereignis mit einer Gilde entfernen.",
                #Calendar
                "extensions.calendar.name": "kalender",
                "extensions.calendar.description": "Kalender-Befehlsgruppe.",
                "extensions.calendar_private.name": "privat",
                "extensions.calendar_private.description": "Den Kalender auf privat oder öffentlich setzen.",
                "extensions.calendar_permission.name": "berechtigung",
                "extensions.calendar_permission.description": "Die Berechtigungen einer E-Mail für den Kalender festlegen.",
                "extensions.calendar_permission.option.permission.reader": "reader",
                "extensions.calendar_permission.option.permission.writer": "writer",
                "extensions.calendar_permission.option.permission.owner": "owner",
                "extensions.calendar_enable.name": "aktivieren",
                "extensions.calendar_enable.description": "Den Kalender für diesen Server aktivieren.",
                "extensions.calendar_link.name": "url",
                "extensions.calendar_link.description": "Die Kalender-URL abrufen."
            },
            Locale.FR: {
                #Cache
                "extensions.cache.name": "cache",
                "extensions.cache.description": "Groupe de commandes Cache.",
                "extensions.cache_update.name": "mettreajour",
                "extensions.cache_update.description": "Mettre à jour le cache pour une guilde.",
                #Help
                "extensions.help.name": "aide",
                "extensions.help.description": "Commande d'aide pour savoir comment commencer.",
                #Reminders
                "extensions.reminder.name": "rappel",
                "extensions.reminder.description": "Activer ou désactiver les rappels d'événements pour vous-même.",
                #Sheet
                "extensions.sheet.name": "feuille",
                "extensions.sheet.description": "Groupe de commandes Feuille.",
                "extensions.sheet_adduser.name": "ajouterutilisateur",
                "extensions.sheet_adduser.description": "Ajouter un utilisateur à la feuille.",
                "extensions.sheet_edituser.name": "modifierutilisateur",
                "extensions.sheet_edituser.description": "Modifier un utilisateur dans la feuille.",
                "extensions.sheet_removeuser.name": "supprimerutilisateur",
                "extensions.sheet_removeuser.description": "Supprimer un utilisateur de la feuille.",
                "extensions.sheet.option.permission.reader": "reader",
                "extensions.sheet.option.permission.writer": "writer",
                "extensions.sheet_url.name": "url",
                "extensions.sheet_url.description": "Obtenir l'URL de la feuille.",
                #User
                "extensions.user.name": "utilisateur",
                "extensions.user.description": "Groupe de commandes Utilisateur.",
                "extensions.user_info.name": "info",
                "extensions.user_info.description": "Obtenir des informations sur un utilisateur.",
                #Config
                "extensions.config.name": "configuration",
                "extensions.config.description": "Groupe de commandes Configuration.",
                "extensions.config_edit.name": "modifier",
                "extensions.config_edit.description": "Configuration de la guilde.",
                #Event
                "extensions.event.name": "evenement",
                "extensions.event.description": "Groupe de commandes Événement.",
                "extensions.event_create.name": "creer",
                "extensions.event_create.description": "Créer un nouvel événement.",
                "extensions.event_restore.name": "restaurer",
                "extensions.event_restore.description": "Restaurer un événement supprimé.",
                "extensions.event_info.name": "info",
                "extensions.event_info.description": "Obtenir des informations sur un événement.",
                "extensions.event_share.name": "partager",
                "extensions.event_share.description": "Partager un événement avec une autre guilde pour des événements communs.",
                "extensions.event_unshare.name": "nepluspartager",
                "extensions.event_unshare.description": "Retirer un événement partagé avec une guilde.",
                #Calendar
                "extensions.calendar.name": "calendrier",
                "extensions.calendar.description": "Groupe de commandes Calendrier.",
                "extensions.calendar_private.name": "prive",
                "extensions.calendar_private.description": "Définir le calendrier comme privé ou public.",
                "extensions.calendar_permission.name": "permission",
                "extensions.calendar_permission.description": "Définir les permissions d'un e-mail pour le calendrier.",
                "extensions.calendar_permission.option.permission.reader": "reader",
                "extensions.calendar_permission.option.permission.writer": "writer",
                "extensions.calendar_permission.option.permission.owner": "owner",
                "extensions.calendar_enable.name": "activer",
                "extensions.calendar_enable.description": "Activer le calendrier pour ce serveur.",
                "extensions.calendar_link.name": "url",
                "extensions.calendar_link.description": "Obtenir l'URL du calendrier."
            },
            Locale.ES_ES: {
                #Cache
                "extensions.cache.name": "cache",
                "extensions.cache.description": "Grupo de comandos de Caché.",
                "extensions.cache_update.name": "actualizar",
                "extensions.cache_update.description": "Actualizar la caché de un servidor.",
                #Help
                "extensions.help.name": "ayuda",
                "extensions.help.description": "Comando de ayuda para comenzar.",
                #Reminders
                "extensions.reminder.name": "recordatorio",
                "extensions.reminder.description": "Activar o desactivar recordatorios de eventos para ti mismo.",
                #Sheet
                "extensions.sheet.name": "hoja",
                "extensions.sheet.description": "Grupo de comandos Hoja.",
                "extensions.sheet_adduser.name": "agregarusuario",
                "extensions.sheet_adduser.description": "Agregar un usuario a la hoja.",
                "extensions.sheet_edituser.name": "editarusuario",
                "extensions.sheet_edituser.description": "Editar un usuario en la hoja.",
                "extensions.sheet_removeuser.name": "eliminarusuario",
                "extensions.sheet_removeuser.description": "Eliminar un usuario de la hoja.",
                "extensions.sheet.option.permission.reader": "reader",
                "extensions.sheet.option.permission.writer": "writer",
                "extensions.sheet_url.name": "url",
                "extensions.sheet_url.description": "Obtener la URL de la hoja.",
                #User
                "extensions.user.name": "usuario",
                "extensions.user.description": "Grupo de comandos Usuario.",
                "extensions.user_info.name": "info",
                "extensions.user_info.description": "Obtener información de un usuario.",
                #Config
                "extensions.config.name": "configuracion",
                "extensions.config.description": "Grupo de comandos Configuración.",
                "extensions.config_edit.name": "editar",
                "extensions.config_edit.description": "Configuración del servidor.",
                #Event
                "extensions.event.name": "evento",
                "extensions.event.description": "Grupo de comandos Evento.",
                "extensions.event_create.name": "crear",
                "extensions.event_create.description": "Crear un nuevo evento.",
                "extensions.event_restore.name": "restaurar",
                "extensions.event_restore.description": "Restaurar un evento eliminado.",
                "extensions.event_info.name": "info",
                "extensions.event_info.description": "Obtener información de un evento.",
                "extensions.event_share.name": "compartir",
                "extensions.event_share.description": "Compartir un evento con otro servidor para eventos conjuntos.",
                "extensions.event_unshare.name": "dejardecompartir",
                "extensions.event_unshare.description": "Eliminar un evento compartido con un servidor.",
                #Calendar
                "extensions.calendar.name": "calendario",
                "extensions.calendar.description": "Grupo de comandos Calendario.",
                "extensions.calendar_private.name": "privado",
                "extensions.calendar_private.description": "Establecer el calendario como privado o público.",
                "extensions.calendar_permission.name": "permiso",
                "extensions.calendar_permission.description": "Establecer los permisos de un correo electrónico para el calendario.",
                "extensions.calendar_permission.option.permission.reader": "reader",
                "extensions.calendar_permission.option.permission.writer": "writer",
                "extensions.calendar_permission.option.permission.owner": "owner",
                "extensions.calendar_enable.name": "habilitar",
                "extensions.calendar_enable.description": "Habilitar el calendario para este servidor.",
                "extensions.calendar_link.name": "url",
                "extensions.calendar_link.description": "Obtener la URL del calendario."
            },
            Locale.HR: {
                #Cache
                "extensions.cache.name": "cache",
                "extensions.cache.description": "Grupa naredbi za Cache.",
                "extensions.cache_update.name": "azurirati",
                "extensions.cache_update.description": "Ažuriraj predmemoriju za ceh.",
                #Help
                "extensions.help.name": "pomoc",
                "extensions.help.description": "Naredba pomoći za početak korištenja.",
                #Reminders
                "extensions.reminder.name": "podsjetnik",
                "extensions.reminder.description": "Omogući ili onemogući podsjetnike za događaje za sebe.",
                #Sheet
                "extensions.sheet.name": "tablica",
                "extensions.sheet.description": "Grupa naredbi za Tablicu.",
                "extensions.sheet_adduser.name": "dodajkorisnika",
                "extensions.sheet_adduser.description": "Dodaj korisnika u tablicu.",
                "extensions.sheet_edituser.name": "uredikorisnika",
                "extensions.sheet_edituser.description": "Uredi korisnika u tablici.",
                "extensions.sheet_removeuser.name": "uklonikorisnika",
                "extensions.sheet_removeuser.description": "Ukloni korisnika iz tablice.",
                "extensions.sheet.option.permission.reader": "reader",
                "extensions.sheet.option.permission.writer": "writer",
                "extensions.sheet_url.name": "url",
                "extensions.sheet_url.description": "Dohvati URL tablice.",
                #User
                "extensions.user.name": "korisnik",
                "extensions.user.description": "Grupa naredbi za Korisnika.",
                "extensions.user_info.name": "info",
                "extensions.user_info.description": "Dohvati informacije o korisniku.",
                #Config
                "extensions.config.name": "konfiguracija",
                "extensions.config.description": "Grupa naredbi za Konfiguraciju.",
                "extensions.config_edit.name": "uredi",
                "extensions.config_edit.description": "Postavljanje konfiguracije ceha.",
                #Event
                "extensions.event.name": "dogadaj",
                "extensions.event.description": "Grupa naredbi za Događaje.",
                "extensions.event_create.name": "stvori",
                "extensions.event_create.description": "Stvori novi događaj.",
                "extensions.event_restore.name": "obnovi",
                "extensions.event_restore.description": "Obnovi izbrisani događaj.",
                "extensions.event_info.name": "info",
                "extensions.event_info.description": "Dohvati informacije o događaju.",
                "extensions.event_share.name": "podijeli",
                "extensions.event_share.description": "Podijeli događaj s drugim cehom za zajedničke događaje.",
                "extensions.event_unshare.name": "prestani",
                "extensions.event_unshare.description": "Ukloni zajednički događaj s cehom.",
                #Calendar
                "extensions.calendar.name": "kalendar",
                "extensions.calendar.description": "Grupa naredbi za Kalendar.",
                "extensions.calendar_private.name": "privatno",
                "extensions.calendar_private.description": "Postavi kalendar na privatno ili javno.",
                "extensions.calendar_permission.name": "dozvola",
                "extensions.calendar_permission.description": "Postavi dozvole e-pošte za kalendar.",
                "extensions.calendar_permission.option.permission.reader": "reader",
                "extensions.calendar_permission.option.permission.writer": "writer",
                "extensions.calendar_permission.option.permission.owner": "owner",
                "extensions.calendar_enable.name": "omoguci",
                "extensions.calendar_enable.description": "Omogući kalendar za ovaj poslužitelj.",
                "extensions.calendar_link.name": "url",
                "extensions.calendar_link.description": "Dohvati URL kalendara."
            }
        })
        
        try:
            self.client = lightbulb.client_from_app(self.bot, localization_provider=localization_provider)
        except Exception as e:
            logger.error(f"Failed to create the Lightbulb client: {e}")
            return
        
        
        @self.bot.listen(StartingEvent)
        async def on_starting(_: StartingEvent) -> None:
            # Presence extensions
            await self.client.load_extensions("bot.bot.modules.presence.presence")
            # Load Cache extensions
            await self.client.load_extensions("bot.bot.modules.cache.commands.cache")
            # Load Help extensions
            await self.client.load_extensions("bot.bot.modules.help.commands.help")
            # Load Member extensions
            await self.client.load_extensions("bot.bot.modules.member.commands.reminder")
            await self.client.load_extensions("bot.bot.modules.member.commands.user")
            await self.client.load_extensions("bot.bot.modules.member.listeners.member_join")
            # Load Config extensions
            await self.client.load_extensions("bot.bot.modules.config.commands.config")
            await self.client.load_extensions("bot.bot.modules.config.commands.sheet")
            await self.client.load_extensions("bot.bot.modules.config.commands.test_subscribe")
            await self.client.load_extensions("bot.bot.modules.config.listeners.guild_join")
            await self.client.load_extensions("bot.bot.modules.config.listeners.guild_leave")
            await self.client.load_extensions("bot.bot.modules.config.listeners.guild_subscribe")
            await self.client.load_extensions("bot.bot.modules.config.listeners.guild_channel_delete")
            await self.client.load_extensions("bot.bot.modules.config.listeners.feedback_interaction")
            await self.client.load_extensions("bot.bot.modules.config.tasks.task_guild_cleanup")
            # Load Event extensions
            await self.client.load_extensions("bot.bot.modules.events.commands.dev")
            await self.client.load_extensions("bot.bot.modules.events.commands.event")
            await self.client.load_extensions("bot.bot.modules.events.listeners.message_delete")
            await self.client.load_extensions("bot.bot.modules.events.listeners.member_delete")
            await self.client.load_extensions("bot.bot.modules.events.listeners.checkin_interaction")
            await self.client.load_extensions("bot.bot.modules.events.listeners.signup_interaction")
            await self.client.load_extensions("bot.bot.modules.events.listeners.manager_interaction")
            await self.client.load_extensions("bot.bot.modules.events.tasks.task_cancelation")
            await self.client.load_extensions("bot.bot.modules.events.tasks.task_checkin")
            await self.client.load_extensions("bot.bot.modules.events.tasks.task_event_expired")
            await self.client.load_extensions("bot.bot.modules.events.tasks.task_marked_events")
            await self.client.load_extensions("bot.bot.modules.events.tasks.task_thread_keepalive")
            await self.client.load_extensions("bot.bot.modules.events.tasks.task_reminders")
            # Load Calendat extensions
            await self.client.load_extensions("bot.bot.modules.calendar.commands.calendar")
            # Load Third Party Status extensions
            await self.client.load_extensions("bot.bot.modules.third_party_status.update_stats")
            
            # Start the bot - make sure commands are synced properly
            await self.client.start()
        
        
        
        # try:
        #     self.bot.subscribe(StartingEvent, self.client.start)
        # except Exception as e:
        #     logger.error(f"Failed to subscribe to the starting event: {e}")
        #     return
        
        async def runner(bot: Baast):
            async with bot:
                await bot.start()

        logger.debug("Loading plugins")
        plugin_paths = event.get('plugins', [])
        
        DjangoDiscordPlugin.bot_proxy = self.bot
        
        for plugin_path in plugin_paths:
            module = import_module(plugin_path)
            plugin = getattr(module, 'plugin')
            if not plugin:
                logger.error(f"Improperly configured plugin module found {plugin_path}. Where is the `plugin` attribute?")

            try:
                await module.setup(self.bot)
            except AttributeError:
                pass
            except TypeError:
                logger.error(f"{plugin_path}.setup should be an async function!")
                raise
            else:
                logger.debug(f"Plugin {plugin_path} successfully loaded")

        logger.debug("Creating bot loop")
        bot_coro = await runner(self.bot)

        # logger.debug("Running bot")
        # self.bot_task = asyncio.create_task(bot_coro)
        # await asyncio.sleep(1)
        
        # logger.debug("Adding background_tasks")
        # # Add task to the set. This creates a strong reference.
        # background_tasks.add(self.bot_task)

        # logger.debug("Calling add_done_callback")
        # # To prevent keeping references to finished tasks forever,
        # # make each task remove its own reference from the set after
        # # completion:
        # self.bot_task.add_done_callback(background_tasks.discard)
        # logger.debug("Done")

    def is_bot_running(self):
        if not self.bot:
            return False
        
        return self.bot.ready

    async def send_message(self, event: dict):
        if not self.is_bot_running():
            raise ValueError("Bot is not running!")
        
        event.pop('type')
        channel: int = event.pop('channel')
        content: str = event.pop('content', None)

        chnl = self.bot.cache.get_guild_channel(channel)
        await chnl.send(
            content=content,
            **event,
        )
    
    async def send_guild_log(self, event: dict):
        if not self.is_bot_running():
            raise ValueError("Bot is not running!")
        event.pop('type')
        channel: int = event.pop('channel')
        title: str = event.pop('title', None)
        description: str = event.pop('description', None)

        try:
            chnl: GuildTextChannel = await self.bot.rest.fetch_channel(channel)
            await chnl.send(
                embed=Embed(
                    title=title,
                    description=f"{description} 🌐",
                    ),
                **event,
            )
        except Exception as e:
            logger.error(f"Failed to send guild log: {e}")
    
    async def get_guild(self, event: dict):
        if not self.is_bot_running():
            raise ValueError("Bot is not running!")
        
        event.pop('type')
        response_channel: str = event.pop('response_channel')
        guild_id: int = event.pop('id')
        
        success = True
        
        try:
            guildd = self.bot.cache.get_guild(guild_id)
        except Exception as e:
            logger.error(f"Failed to fetch guild: {guild_id}\n {e}")
            success = False
            
        if guildd == None:
            try:
                guildd = await self.bot.rest.fetch_guild(guild_id)
            except (NotFoundError, ForbiddenError):
                success = False
            except Exception as e:
                logger.error(f"Failed to fetch guild: {guild_id}\n {e}")
                success = False
        
        if success:
            await save_discord_meta_models(guildd)
        
        await self.channel_layer.send(
            response_channel,
            {
                "type": "response_message",
                "success": success
            }
        )
    
    async def get_guild_channels(self, event: dict):
        if not self.is_bot_running():
            raise ValueError("Bot is not running!")
        event.pop('type')
        guild_id: int = event.pop('id')

        try:
            guildd = await self.bot.rest.fetch_guild(guild_id)
        except NotFoundError:
            logger.warning(f"Guild not found: {guild_id}")
            return
        
        channels = _safe_get_cache_view(guildd.get_channels, f"guild {guild_id} channels")
        for channel in channels:
            try:
                await save_discord_meta_models(await self.bot.rest.fetch_channel(channel), guildd)
            except Exception as e:
                logger.error(f"Failed to save guild channel: {e}")
    
    async def get_guild_roles(self, event: dict):
        if not self.is_bot_running():
            raise ValueError("Bot is not running!")
        event.pop('type')
        guild_id: int = event.pop('id')

        try:
            guildd = await self.bot.rest.fetch_guild(guild_id)
        except NotFoundError:
            logger.warning(f"Guild not found: {guild_id}")
            return
        
        for role in await guildd.fetch_roles():
            await save_discord_meta_models(role, guildd)
    
    async def get_user(self, event: dict):
        if not self.is_bot_running():
            raise ValueError("Bot is not running!")
        event.pop('type')
        guild_id: int = event.pop('g_id')
        user_id: int = event.pop('u_id')

        try:
            user: Member = await self.bot.rest.fetch_member(guild_id, user_id)
        except NotFoundError:
            logger.warning(f"User not found: {guild_id}-{user_id}")
            return
        
        await save_discord_meta_models(user)
    
    async def post_event(self, _event: dict):
        if not self.is_bot_running():
            raise ValueError("Bot is not running!")
        
        _event.pop('type')
        id: int = _event.pop('id')
        author_id: int = _event.pop('user_id')
        mention_ids: list[int] = _event.pop('mentions', [])
        log: bool = _event.pop('log', True)
        
        is_restoration: bool = _event.pop('is_restoration', False)
        restore_signups: bool = _event.pop('restore_signups', False)

        try:
            event: Events = await sync_to_async(Events.objects.get)(id=id)
        except Events.DoesNotExist:
            logger.error(f"consumers.post_event:: HTTP App Requested to post an event that does not exist: {id}")
        else:
            config: Config = await sync_to_async(event.Config)()
            template: Templates = await sync_to_async(event.GetTemplate)()
            optionPreset = await sync_to_async(event.GetOptionPreset)()
            
            try:
                guild: RESTGuild = await self.bot.rest.fetch_guild(config.guild)
            except Exception as e:
                logger.error(f"Failed to fetch guild: {config.guild}\n {e}")
                return
            
            try:
                guild: RESTGuild = await self.bot.rest.fetch_guild(config.guild)
            except Exception as e:
                logger.error(f"Failed to fetch guild: {config.guild}\n {e}")
                return
            
            try:
                author = await self.bot.rest.fetch_member(config.guild, author_id)
            except Exception as e:
                logger.error(f"Failed to fetch member: {config.guild}-{author_id}\n {e}")
                return
            
            try:
                channel: GuildTextChannel = await self.bot.rest.fetch_channel(event.channel)
            except Exception as e:
                logger.error(f"Failed to fetch channel: {event.channel}\n {e}")
                return
            
            
            
            try:
                embeds:Embed = await RebuildEventEmbed(self.bot.rest, event, await sync_to_async(event.GetAttendance)())
            except Exception as e:
                logger.error(e)
                return
            
            
            try:
                componentRow = await BuildComponents(self.bot.rest, config, optionPreset, event.date_arrow)
            except Exception as e:
                logger.error(e)
                return
            
            mentions: list[Role] = []
            for id in mention_ids:
                try:
                    role = guild.get_role(id)
                except:
                    logger.warning(f"consumers.post_event:: Could not find role: {id} in guild: {guild.id} for event: {event.id}")
                else:
                    if role != None:
                        mentions.append(role)
            
            mentionStr, everyone = roles_to_string(mentions)

            try:
                message = await channel.send(content=mentionStr, embeds=embeds, components=componentRow, role_mentions=mentions, mentions_everyone=everyone)
                thread: GuildPrivateThread = await self.bot.rest.create_message_thread(channel, message, f"{arrow.get(event.event_date).format('DD-MM-YYYY')} - {event.title}", 
                                                                                    auto_archive_duration=timedelta(hours=24*7))
            except:
                logger.error(sys.exc_info())
            else:  
                event.message = int(message.id)
                event.thread = int(thread.id)
                
                ##Sheet
                sheets = None
                if config.is_premium and template != None:
                    try:
                        sheets: Sheet = Sheet(config, guild.name)
                    except:
                        logger.error(sys.exc_info())
                    else:
                        try:
                            await sheets.CreateSheet(event, message.make_link(guild))
                        except:
                            logger.error(sys.exc_info())
                        else:
                            event.worksheet_id = sheets.sheet.id
                ##Calendar
                if config.calendar_enabled and config.is_premium:     
                    try:
                        cal: Calendar = Calendar()
                    except:
                        logger.error(sys.exc_info())
                    else:
                        if config.calendar_id == None:
                            try:
                                await sync_to_async(cal.create_calendar)(guild, config)
                            except:
                                logger.error(sys.exc_info())
                                
                        try:
                            await sync_to_async(cal.create_event)(event, config)
                        except:
                            logger.error(sys.exc_info())
                ##
                
                await event.asave()
                
                roleset = await sync_to_async(event.GetRoleset)()
                if roleset != None:
                    for i, option in enumerate(optionPreset.options):
                        attendance: Attendance = await sync_to_async(event.GetAttendance)()
                    
                        signups = attendance.get_signup_option_list(SignupOption(i))
                        
                        for attendee in signups:
                            try:
                                await self.bot.rest.add_role_to_member(guild, int(attendee), roleset.roles[i]["role_id"])
                            except errors.ForbiddenError:
                                logger.warning(f'Bot does not have permission to add role {roleset.roles[i]["role_id"]} to {attendee} in guild {guild.id}')
            
                #LOG
                if config.log_channel != 0 and log:
                    try:
                        log_chl: GuildTextChannel = await self.bot.rest.fetch_channel(config.log_channel)
                        await log_chl.send(embed=Embed(description=(f"{author.mention} created event [{event.title}]({message.make_link(guild)}) on <t:{int(event.event_date.timestamp())}:F> 🌐" 
                                                                    if not is_restoration else 
                                                                    f"{author.mention} restored event [{event.title}]({message.make_link(guild)}) on <t:{int(event.event_date.timestamp())}:F> 🌐")))
                    except Exception as e:
                        logger.error(f"Failed to send log: {e}")
        
    async def update_event(self, event: dict):
        if not self.is_bot_running():
            raise ValueError("Bot is not running!")
        
        event.pop('type')
        id: int = event.pop('id')
        user_id: int = event.pop('user_id')
        edits: list[int] = event.pop('edits')
        log: bool = event.pop('log', True)

        edits_str = ""
        for edit in edits:
            if edit == 1:
                edits_str += "Title, "
            elif edit == 2:
                edits_str += "Description, "
            elif edit == 3:
                edits_str += "Date, "
            elif edit == 4:
                edits_str += "Capacity, "
        
        edits_str = edits_str[:-2]
        
        try:
            event: Events = await sync_to_async(Events.objects.get)(id=id)
        except Events.DoesNotExist:
            return
        else:
            config: Config = await sync_to_async(event.Config)()
            
            try:
                guild: RESTGuild = await self.bot.rest.fetch_guild(config.guild)
                message: Message = await self.bot.rest.fetch_message(event.channel, event.message)
            except Exception as e:
                logger.error(f"Failed to fetch guild: {config.guild}\n {e}")
                return
            
            eventEmbeds = await RebuildEventEmbed(self.bot.rest, event, await sync_to_async(event.GetAttendance)())
            await message.edit(embeds=eventEmbeds, components=await BuildComponents(self.bot.rest, config, event.option_preset, event.date_arrow))
            
            await update_event_thread(self.bot.rest, event)
            
            await update_other_events_messages(self.bot.rest, event, guild)
            
            #LOG
            if config.log_channel and log:
                try:
                    log_chl: GuildTextChannel = await self.bot.rest.fetch_channel(config.log_channel)
                    await log_chl.send(embed=Embed(description=f"🌐 <@{user_id}> edited the event {edits_str} [{event.title}]({message.make_link(guild)})"))
                except Exception as e:
                    logger.error(f"Failed to send log: {e}")
                    
            if event.thread != None:
                try:
                    event_thread: GuildPrivateThread = await self.bot.rest.fetch_channel(event.thread)
                    await event_thread.send(embed=Embed(description=f"🌐 The event {edits_str} was updated."))
                except Exception as e:
                    logger.error(f"Failed to send thread log: {e}")
            
                
    async def delete_event(self, event: dict):
        if not self.is_bot_running():
            raise ValueError("Bot is not running!")
        
        event.pop('type')
        id: int = event.pop('id')
        user_id: int = event.pop('user_id')
        log: bool = event.pop('log', True)

        try:
            event: Events = await sync_to_async(Events.objects.get)(id=id)
        except Events.DoesNotExist:
            pass
        else:
            config: Config = await sync_to_async(event.Config)()
             
            try:
                await self.bot.rest.delete_message(event.channel, event.message)
            except:
                pass
            
            #LOG
            if config.log_channel and log:
                try:
                    log_chl: GuildTextChannel = await self.bot.rest.fetch_channel(config.log_channel)
                    await log_chl.send(embed=Embed(description=f"<@{user_id}> removed Event **{event.title}** happening <t:{int(event.event_date.timestamp())}:F> 🌐"))
                except Exception as e:
                    logger.error(f"Failed to send log: {e}")
    
    async def remove_user_from_event(self, event: dict):
        if not self.is_bot_running():
            raise ValueError("Bot is not running!")
        
        event.pop('type')
        id: int = event.pop('id')
        is_linked: bool = event.pop('is_linked')
        user_id: int = int(event.pop('user_id'))
        mngr_id: int = event.pop('mngr_id')
        signup_index: int = int(event.pop('signup_index'))
        
        event: Events = None
        event_linked: Events_Links = None
        if is_linked == False:
            try:
                event: Events = await sync_to_async(Events.objects.get)(id=id)
            except Events.DoesNotExist:
                return logger.error(f'{id}:{sys._getframe()}:{sys.exc_info()}')
            except:
                logger.error(sys.exc_info())
        else:
            try:
                event_linked: Events_Links = await sync_to_async(Events_Links.objects.get)(id=id)
            except Events_Links.DoesNotExist:
                return logger.error(f'{id}:{sys._getframe()}:{sys.exc_info()}')
            except:
                logger.error(sys.exc_info())
            else:
                event = await sync_to_async(event_linked.Event)()
        
        try:
            config: Config = await sync_to_async((event if is_linked == False else event_linked).Config)()
        except:
            logger.error(f'{sys._getframe()}:{sys.exc_info()}')
        
        try:
            user = await self.bot.rest.fetch_member(config.guild, user_id)
            guild: RESTGuild = await self.bot.rest.fetch_guild(config.guild)
            message: Message = await self.bot.rest.fetch_message((event if is_linked == False else event_linked).channel, (event if is_linked == False else event_linked).message)
            threadMembers = await self.bot.rest.fetch_thread_members((event if is_linked == False else event_linked).thread)
        except:
            logger.error(f'{sys._getframe()}:{sys.exc_info()}')
        
        
        try:
            roleset: Preset_Roles = await sync_to_async(event.GetRoleset)()
        except:
            logger.error(f'{sys._getframe()}:{sys.exc_info()}')
        
        if roleset:
            try:
                await self.bot.rest.remove_role_from_member(guild, user_id, roleset.roles[signup_index]["role_id"])
            except errors.ForbiddenError:
                logger.warning(f'Bot does not have permission to remove role {roleset.roles[signup_index]["role_id"]} from {user_id} in guild {guild.id}')
        
        
        try:
            if await ThreadHasUser(threadMembers, user):
                await self.bot.rest.remove_thread_member((event if is_linked == False else event_linked).thread, user)
        except:
            logger.error(f'{sys._getframe()}:{sys.exc_info()}')
        
        #LOG
        if config.log_channel:
            try:
                log_chl: GuildTextChannel = await self.bot.rest.fetch_channel(config.log_channel)
                await log_chl.send(embed=Embed(description=f"{user.mention} removed <@{mngr_id}> signup for event [{event.title}]({message.make_link(guild)}) 🌐")) #on <t:{int(arrDate.to('utc').datetime.timestamp())}:F>
            except Exception as e:
                logger.error(f"Failed to send log: {e}")
                
    # Deprecated After 2.0.0
    async def post_announcement(self, event: dict):
        if not self.is_bot_running():
            raise ValueError("Bot is not running!")
        
        event.pop('type')
        title: str = event.pop('title')
        description: int = event.pop('description')
        admin_id: int = event.pop('admin_id')
        is_test: bool = event.pop('is_test', True)
        push_to_news: bool = event.pop('push_to_news', False)
        push_to_logs: bool = event.pop('push_to_logs', False)
        
        
        comps = [ContainerComponentBuilder(
                    components=[
                        MediaGalleryComponentBuilder(
                            items=[
                                MediaGalleryItemBuilder(
                                    media="https://cdn.discordapp.com/attachments/1167472862555287612/1382736509932667010/baast_discord_header.png?ex=684c3d39&is=684aebb9&hm=0c771b2701a9c7745dffe37e3083b022e4b9db06a47f1ac38e23b7c8bef5ee29&",
                                ),
                            ]
                        ),
                        TextDisplayComponentBuilder(content=f"# **{title}**"),
                        SeparatorComponentBuilder(divider=True, spacing=SpacingType.SMALL,),
                        TextDisplayComponentBuilder(content=description),
                        SectionComponentBuilder(
                            accessory=LinkButtonBuilder(
                                url="https://baast.app/",
                                label="Read More",
                            ),
                            components=[
                                TextDisplayComponentBuilder(content="-# ."),
                            ]
                        ),
                    ]
                )]
        
        if is_test:
            channel: GuildTextChannel = await self.bot.rest.fetch_channel("839886394775437399")
            await channel.send(components=comps, flags=MessageFlag.IS_COMPONENTS_V2)
        else:
            if push_to_news == True:
                try:
                    channel: GuildTextChannel = await self.bot.rest.fetch_channel("928620891041067028")
                    await channel.send(components=comps, flags=MessageFlag.IS_COMPONENTS_V2)
                except:
                    pass
                
            if push_to_logs == True:
                guilds: LazyIterator[OwnGuild] = await self.bot.rest.fetch_my_guilds()
                async for guild in guilds:
                    try:
                        conf: Config = await sync_to_async(Config.objects.get)(guild=guild.id)
                    except Config.DoesNotExist:
                        continue
                    
                    if conf.log_channel != 0:
                        try:
                            channel: GuildTextChannel = await self.bot.rest.fetch_channel(conf.log_channel)
                            await channel.send(components=comps, flags=MessageFlag.IS_COMPONENTS_V2)
                        except:
                            continue
                        
    async def post_blog_post(self, event: dict):
        if not self.is_bot_running():
            raise BotNotRunning("Bot is not running!")
        
        event.pop('type')
        url: str = event.pop('url')
        title: str = event.pop('title')
        description: str = event.pop('description')
        
        comps = [ContainerComponentBuilder(
                    components=[
                        MediaGalleryComponentBuilder(
                            items=[
                                MediaGalleryItemBuilder(
                                    media="https://cdn.discordapp.com/attachments/1167472862555287612/1382736509932667010/baast_discord_header.png?ex=684c3d39&is=684aebb9&hm=0c771b2701a9c7745dffe37e3083b022e4b9db06a47f1ac38e23b7c8bef5ee29&",
                                ),
                            ]
                        ),
                        TextDisplayComponentBuilder(content=f"# **[{title}]({url})**"),
                        SeparatorComponentBuilder(divider=True, spacing=SpacingType.SMALL,),
                        TextDisplayComponentBuilder(content=description),
                        SectionComponentBuilder(
                            accessory=LinkButtonBuilder(
                                url=url,
                                label="Read More",
                            ),
                            components=[
                                TextDisplayComponentBuilder(content="-# ."),
                            ]
                        ),
                    ]
                )]
        
        is_test = True
        if is_test:
            try:
                channel: GuildTextChannel = await self.bot.rest.fetch_channel("1382730535171915776") #"839886394775437399"
                message = await channel.send(components=comps, flags=MessageFlag.IS_COMPONENTS_V2 )
                await self.bot.rest.crosspost_message(channel, message)
            except:
                logger.error(sys.exc_info())
                pass
        else:
            try:
                channel: GuildTextChannel = await self.bot.rest.fetch_channel("928620891041067028")
                message = await channel.send(components=comps, flags=MessageFlag.IS_COMPONENTS_V2)
                await self.bot.rest.crosspost_message(channel, message)
            except:
                pass
                        
    async def is_event_manager(self, event: dict):
        if not self.is_bot_running():
            raise ValueError("Bot is not running!")
        
        event.pop('type')
        response_channel: str = event.pop('response_channel')
        guild_id: str = event.pop('guild_id')
        user_id: str = event.pop('user_id')
        section: str = event.pop('section')
        
        has_access: bool = False
        
        command_perms = {}
        
        try:
            guild: RESTGuild = await self.bot.rest.fetch_guild(guild_id)
        except:
            pass
        else:
            try:
                user: Member = await self.bot.rest.fetch_member(guild_id, user_id)
            except:
                pass
            else:
                if has_permissions(user, Permissions.ADMINISTRATOR) or guild.owner_id == user.id:
                    has_access = True
                else:
                    try:
                        cmds: Sequence[PartialCommand] = await self.bot.rest.fetch_application_commands(guild.get_my_member().id, guild)
                    except:
                        logger.warning(sys.exc_info())
                    else:
                        try:
                            member: Member = await self.bot.rest.fetch_member(guild, user)
                        except NotFoundError:
                            logger.info(f'NotFoundError {user.name}')
                        else:
                            roles: Sequence[Role] = member.get_roles()
                            # Convert to list to avoid any potential iteration issues
                            roles_list = list(roles) if not isinstance(roles, list) else roles
                            
                            for c in cmds:
                                if c.name == section:
                                    try:
                                        gcp: GuildCommandPermissions = await c.fetch_guild_permissions(guild)
                                    except NotFoundError:
                                        logger.info(f'NotFoundError {c.name}')
                                        #has_access = True
                                        continue
                                    except:
                                        logger.warning(sys.exc_info())
                                        continue
                                    else:
                                        perms: Sequence[CommandPermission] = gcp.permissions
                                        for perm in perms:
                                            if perm.type == CommandPermissionType.USER and perm.id == user.id:
                                                has_access = perm.has_access
                                                command_perms[c.name] = has_access
                                                break
                                            elif perm.type == CommandPermissionType.ROLE:
                                                for role in roles_list:
                                                    if perm.id == role.id:
                                                        has_access = perm.has_access
                                                        command_perms[c.name] = has_access
                                                        break
                                                else:
                                                    continue
                                                break
        
        #print(f"{guild_id}:{command_perms}")
        await self.channel_layer.send(
            response_channel,
            {
                "type": "response_message",
                "has_access": has_access
            }
        )
        
    async def assign_plus_role(self, event: dict):
        if not self.is_bot_running():
            raise BotNotRunning("Bot is not running!")
        
        event.pop('type')
        member_id: str = event.pop('member_id')
        assign: bool = bool(int(event.pop('assign')))
        
        if assign:
            try:
                await self.bot.rest.add_role_to_member(MAIN_GUILD_ID, member_id, 941685137018609674)
            except:
                return
        else:
            try:
                await self.bot.rest.remove_role_from_member(MAIN_GUILD_ID, member_id, 941685137018609674)
            except:
                return
            
            
      