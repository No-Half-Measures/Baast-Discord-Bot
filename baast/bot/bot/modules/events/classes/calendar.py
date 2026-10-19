import sys

from google.oauth2 import service_account
from googleapiclient.errors import HttpError
from googleapiclient.discovery import build

import arrow

from hikari import OwnGuild

from app.models import Events, Events_Links, Config

from bot.bot.utils.util import discord_markdown_to_html

from django.conf import settings

from discord.views import ConvertTimeFromDBToValues
GOOGLE_SERVICE_ACCOUNT_FILE = getattr(settings, 'GOOGLE_SERVICE_ACCOUNT_FILE')
# Calendar ID (usually your email address)
CALENDAR_ID = 'baast-events@baast-337223.iam.gserviceaccount.com'#'your_calendar_id@group.calendar.google.com'

# If modifying these SCOPES, delete the file token.json.
SCOPES = ['https://www.googleapis.com/auth/calendar']

from loguru import logger


class Calendar():
    credentials: service_account.Credentials = None
    service = None
    
    def __init__(self):
        try:
            credentials = service_account.Credentials.from_service_account_file(GOOGLE_SERVICE_ACCOUNT_FILE, scopes=SCOPES)
        except Exception as e:
            logger.error(f'{sys._getframe()}:{sys.exc_info()}')
            raise e
        
        try:
            self.service = build('calendar', 'v3', credentials=credentials)
        except Exception as e:
            logger.error(f'{sys._getframe()}:{sys.exc_info()}')
            raise e
        
    def get_calendar_link(self, config: Config) -> str:
        base_url = "https://calendar.google.com/calendar/embed?src="
        calendar_link = f"{base_url}{config.calendar_id}"
        return calendar_link
    
    def create_calendar(self, guild: OwnGuild, config: Config):
        calendar = {
            'summary': f'{guild.name} Calendar',
            'description': f'A calendar created via Baast to sync events from {guild.name}',
            'timeZone': 'UTC'
        }
        created_calendar = self.service.calendars().insert(body=calendar).execute()
        logger.info('Calendar created: %s' % (created_calendar['id']))
        
        config.calendar_id = created_calendar['id']
        config.save()
        
        self.update_public_access_rule(config)
        
    def find_public_access_rule(self, config: Config):
        try:
            acl = self.service.acl().list(calendarId=config.calendar_id).execute()
            for rule in acl['items']:
                if rule['scope']['type'] == 'default':
                    return rule['id']
                
        except HttpError as error:
            logger.error('An error occurred: %s' % error)
        
    def update_public_access_rule(self, config: Config, role: str = 'reader'):
        rule = {
            'scope': {
                'type': 'default',
            },
            'role': role # 'reader' to view all event details, 'freeBusyReader' to only see free/busy times
        }

        try:
            created_rule = self.service.acl().insert(calendarId=config.calendar_id, body=rule).execute()
            # logger.info('Public access rule created: %s' % (created_rule.get('id')))
        except HttpError as error:
            logger.error('An error occurred: %s' % error)
    
    def make_calendar_private(self, config: Config):
        rule_id = self.find_public_access_rule(config)
        
        if rule_id:
            try:
                self.service.acl().delete(calendarId=config.calendar_id, ruleId=rule_id).execute()
            except HttpError as error:
                logger.error('An error occurred: %s' % error)
    
    def check_calendar_exists(self, calendar_id: str):
        if not calendar_id:
            return False
        
        try:
            calendar = self.service.calendars().get(calendarId=calendar_id).execute()
            logger.info('Calendar exists: %s' % (calendar.get('summary')))
            return True
        except HttpError as error:
            if error.resp.status == 404:
                logger.info('Calendar not found.')
                return False
            else:
                logger.info('An error occurred: %s' % error)
                raise
        except:
            logger.error(f'{sys._getframe()}:{sys.exc_info()}')

    
    def create_event(self, event: Events, config: Config, linkedEvent: Events_Links = None):
        try:
            endTime = ConvertTimeFromDBToValues(config.autoclean_t)
            endTimeDate: arrow.Arrow = arrow.get(event.event_date).to('utc').shift(hours=+endTime[0], minutes=+endTime[1], seconds=+endTime[2])
        except Exception as e:
            logger.error(f'{sys._getframe()}:{sys.exc_info()}')
            raise e
        
        cal_event = {
            'summary': discord_markdown_to_html(event.title),
            'description': discord_markdown_to_html(event.description) if event.description else "",
            'start': {
                'dateTime': event.event_date.strftime('%Y-%m-%dT%H:%M:%S%z'),
                'timeZone': event.tz,
            },
            'end': {
                'dateTime': endTimeDate.datetime.strftime('%Y-%m-%dT%H:%M:%S%z'),
                'timeZone': event.tz,
            },
            # 'recurrence': [
            #     'RRULE:FREQ=DAILY;COUNT=2'
            # ],
            'attendees': [],
            'reminders': {
                'useDefault': False,
                'overrides': [
                    {'method': 'email', 'minutes': 24 * 60},
                    {'method': 'popup', 'minutes': 30},
                ],
            },
        }
        
        try:
            cal_event = self.service.events().insert(calendarId=config.calendar_id, body=cal_event).execute()
        except Exception as e:
            logger.error(f'{sys._getframe()}:{sys.exc_info()}')
            raise e
        
        # logger.info('Event created: %s' % (cal_event.get('htmlLink')))
        
        if linkedEvent:
            linkedEvent.calendar_event_id = cal_event['id']
            linkedEvent.save()
        else:
            event.calendar_event_id = cal_event['id']
            event.save()
        
    def edit_event(self, event: Events, config: Config, linkedEvent: Events_Links = None):
        try:
            cal_event = self.service.events().get(calendarId=config.calendar_id, eventId=event.calendar_event_id if not linkedEvent else linkedEvent.calendar_event_id).execute()
        except Exception as e:
            logger.error(f'{sys._getframe()}:{sys.exc_info()}')
            raise e

        # Change the event summary and description
        cal_event['summary'] = discord_markdown_to_html(event.title)
        cal_event['description'] = discord_markdown_to_html(event.description) if event.description else ""

        try:
            updated_event = self.service.events().update(calendarId=config.calendar_id, eventId=event.calendar_event_id if not linkedEvent else linkedEvent.calendar_event_id, body=cal_event).execute()
        except Exception as e:
            logger.error(f'{sys._getframe()}:{sys.exc_info()}')
            raise e

        # logger.info('Event updated: %s' % (updated_event.get('htmlLink')))
        
    def delete_event(self, event: Events | Events_Links, config: Config):
        try:
            self.service.events().delete(calendarId=config.calendar_id, eventId=event.calendar_event_id).execute()
        except Exception as e:
            logger.error(f'{sys._getframe()}:{sys.exc_info()}')
    
    def add_access_to_calendar(self, config: Config, email:str, role: str = 'owner'):
        rule = {
            'scope': {
                'type': 'user',
                'value': email,
            },
            'role': role  # Other roles: 'reader', 'owner', 'freeBusyReader'
        }

        try:
            created_rule = self.service.acl().insert(calendarId=config.calendar_id, body=rule).execute()
        except HttpError as error:
            logger.error('An error occurred: %s' % error)