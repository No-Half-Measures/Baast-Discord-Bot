import sys
import arrow
import re
from asgiref.sync import sync_to_async

from google.oauth2 import service_account
from gspread import Worksheet, service_account, exceptions, Spreadsheet

from hikari import RESTAware, User

from app.models import Config, Events, Templates, Option_Presets, Attendance
from cache.models import DiscordUser

from cache.helpers import GetGuild
from bot.bot.utils.enums import SignupOption
from bot.bot.utils.util import discord_markdown_to_html

from django.conf import settings

from loguru import logger

GOOGLE_SERVICE_ACCOUNT_FILE = getattr(settings, 'GOOGLE_SERVICE_ACCOUNT_FILE')

# If modifying these SCOPES, delete the file token.json.
SCOPES = ['https://www.googleapis.com/auth/calendar']

#googleClient = service_account(filename=GOOGLE_SERVICE_ACCOUNT_FILE)

class Sheet():
    service = None
    spreadsheet: Spreadsheet = None
    archive_spreadsheet: Spreadsheet = None
    sheet: Worksheet = None
    
    guild_id: int = None
    
    def __init__(self, config: Config, guildName: str, event: Events = None):
        self.service = service_account(filename=GOOGLE_SERVICE_ACCOUNT_FILE)
        
        self.guild_id = config.guild
        
        if config.p_sheetid:
            try:
                self.spreadsheet: Spreadsheet = self.service.open_by_key(config.p_sheetid)
            except:
                logger.critical(f'{sys._getframe()}:{sys.exc_info()}')
            
        if config.p_archive_sheetid:
            try:
                self.archive_spreadsheet: Spreadsheet = self.service.open_by_key(config.p_archive_sheetid)
            except:
                logger.critical(f'{sys._getframe()}:{sys.exc_info()}')
        
        
        if not self.spreadsheet or not config.p_sheetid:
            self.spreadsheet = self.service.create(title=f'{guildName} - Events')
            noDelSheet = self.spreadsheet.get_worksheet_by_id("0")
            noDelSheet.delete_rows(2, noDelSheet.row_count)
            noDelSheet.delete_columns(2, noDelSheet.col_count)
            noDelSheet.update_acell('A1', 'This sheet is protected from deletion. Please do not delete it. This is due to the way we have to have atleast one sheet in the spreadsheet as the one remaining is unable to be deleted so to prevent issues with Baast this sheet is protected.')
            noDelSheet.update_title(f'DummySheet')
            noDelSheet.add_protected_range('')
            
            config.p_sheetid = self.spreadsheet.id
            config.save()
            
        if not self.archive_spreadsheet or not config.p_archive_sheetid:
            self.archive_spreadsheet = self.service.create(title=f'{guildName} - Archive')
            
            config.p_archive_sheetid = self.archive_spreadsheet.id
            config.save()
        
        if event and event.worksheet_id:
            try:
                self.sheet = self.spreadsheet.get_worksheet_by_id(event.worksheet_id)
            except:
                logger.warning(f'Failed to get worksheet for event {config.id}:{event.id} - {sys._getframe()}:{sys.exc_info()}')
        
    def addUser(self, email: str, role: str):
        self.spreadsheet.share(email, perm_type='user', role=role)
        self.archive_spreadsheet.share(email, perm_type='user', role=role)
        
    def editUser(self, email: str, role: str):
        self.spreadsheet.share(email, perm_type='user', role=role, notify=False)
        self.archive_spreadsheet.share(email, perm_type='user', role=role, notify=False)
    
    def removeUser(self, email: str):
        self.spreadsheet.remove_permissions(email)
        self.archive_spreadsheet.remove_permissions(email)
        
    async def CreateSheet(self, event: Events, eventURL: str):
        templatePreset: Templates = await sync_to_async(event.GetTemplate)()
        if templatePreset == None or templatePreset.worksheetid == None or templatePreset.sheetid == None:
            logger.critical(f'NO TEMPLATE PRESENT OR TEMPLATE SHEET ID NOT SET')
            logger.critical(f'{templatePreset} : {templatePreset.worksheetid} : {templatePreset.sheetid}')
            return
        
        try:
            templateSheet = self.service.open_by_key(templatePreset.sheetid)
        except:
            logger.critical(f'{sys._getframe()}:{sys.exc_info()}')
            return
        
        try:
            sheetTemplate: Worksheet = templateSheet.get_worksheet_by_id(templatePreset.worksheetid)
        except:
            logger.critical(f'{sys._getframe()}:{sys.exc_info()}')
            return
        
        try:
            responce = sheetTemplate.copy_to(self.spreadsheet.id)
            self.sheet = self.spreadsheet.get_worksheet_by_id(responce['sheetId'])
            
            event.worksheet_id = self.sheet.id
            await event.asave()
        except:
            logger.critical(f'{sys._getframe()}:{sys.exc_info()}')
            return
        
        try:
            optionPresets: Option_Presets = await sync_to_async(event.GetOptionPreset)()
        except:
            logger.critical(f'{sys._getframe()}:{sys.exc_info()}')
            return
        
        ## Update Cells
        if templatePreset.cells['cell_title'] != 'None':
            try:
                self.sheet.update_acell(templatePreset.cells['cell_title'], event.title)
            except:
                logger.critical(f'{sys._getframe()}:{sys.exc_info()}')
                return

        if templatePreset.cells['cell_desc'] != 'None':
            try:
                self.sheet.update_acell(templatePreset.cells['cell_desc'], event.description.replace("*", "") if event.description != None else 'None')
            except:
                logger.critical(f'{sys._getframe()}:{sys.exc_info()}')
                return
        
        if templatePreset.cells['cell_date'] != 'None':
            try:
                self.sheet.update_acell(templatePreset.cells['cell_date'], event.date_arrow.format("DD/MM/YYYY HH:mm"))
            except:
                logger.critical(f'{sys._getframe()}:{sys.exc_info()}')
                return
        
        if templatePreset.cells['cell_link'] != 'None':
            try:
                self.sheet.update_acell(templatePreset.cells['cell_link'], eventURL)
            except:
                logger.critical(f'{sys._getframe()}:{sys.exc_info()}')
                return
        
        ## Update Capacity
        # if templatePreset.cells['cell_capacity'] != 'None':
        #     try:
        #         self.sheet.update_acell(templatePreset.cells['cell_capacity'], event.capacity)
        #     except:
        #         logger.critical(f'{sys._getframe()}:{sys.exc_info()}')
        #         return
            
        ## Rename Sheet
        try:
            self.sheet.update_title(f'{event.title} - {event.date_arrow.format("DD/MM/YYYY HH:mm")}')
        except exceptions.APIError as e:
            if e._extract_text(e.response)['code'] == 400:
                title = f'{event.title} - {event.date_arrow.format("DD/MM/YYYY HH:mm")}'
                copyCount = 0
                
                for ws in self.spreadsheet.worksheets():
                    if title in ws.title:
                        copyCount += 1
                
                try:
                    self.sheet.update_title(f'{title} ({copyCount})')
                except:
                    logger.critical(f'{sys._getframe()}:{sys.exc_info()}')
                    return
        except:
            logger.critical(f'{sys._getframe()}:{sys.exc_info()}')
            return

    
    async def UpdateTitle(self, title:str, eventDate: arrow.Arrow, templatePreset: Templates):
        if not self.sheet:
            return
        
        if templatePreset.cells['cell_title'] != 'None':
            try:
                self.sheet.update_acell(templatePreset.cells['cell_title'], title)
                
                self.sheet.update_title(f'{title} - {eventDate.format("DD/MM/YYYY HH:mm")}')
            except:
                logger.warning(f'{sys._getframe()}:{sys.exc_info()}')
                return

    async def UpdateDescription(self, description: str, templatePreset: Templates):
        if not self.sheet:
            return
        
        if templatePreset.cells['cell_desc'] != 'None':
            try:
                self.sheet.update_acell(templatePreset.cells['cell_desc'], description.replace("*", "") if description != None else 'None')
            except:
                logger.warning(f'{sys._getframe()}:{sys.exc_info()}')
                return

    async def UpdateCapacity(self, capacity: int, optionPresets: Option_Presets, templatePreset: Templates):
        if not self.sheet:
            return
        
        if templatePreset.cells['cell_capacity'] != 'None':
            batchCells = []
            batchData = []
            
            for option in optionPresets.options:
                if option['is_attending']:
                    for key in templatePreset.cells[str(optionPresets.id)]:
                        if key == option['label']:
                            batchCells.append(templatePreset.cells[str(optionPresets.id)][key])
                            
                            if optionPresets.use_capacity:
                                strlist = re.split(r'(\d+)', templatePreset.cells[str(optionPresets.id)][key])
                                batchData.append('=CONCATENATE("' + option['label'] + ' ",COUNTA('+templatePreset.cells[str(optionPresets.id)][key]+':'+strlist[0]+'), "/",'+ str(capacity) +')')
                            else:
                                batchData.append(option['label'])
            
            try:
                self.sheet.batch_update([{'range': ','.join(batchCells),'values': batchData}])
            except:
                logger.warning(f'{sys._getframe()}:{sys.exc_info()}')
                return

    async def UpdateDate(self, eventDate: arrow.Arrow, templatePreset: Templates):
        if not self.sheet:
            return
        
        if templatePreset.cells['cell_date'] != 'None':
            try:
                self.sheet.update_acell(templatePreset.cells['cell_date'], eventDate.format("DD/MM/YYYY HH:mm"))
            except:
                logger.warning(f'{sys._getframe()}:{sys.exc_info()}')
                return
    
    async def UpdateAttendance(self, event: Events):
        if not self.sheet:
            return
        
        try:
            templatePreset: Templates = await sync_to_async(event.GetTemplate)()
            optionPresets: Option_Presets = await sync_to_async(event.GetOptionPreset)()
        except:
            logger.critical(f'{sys._getframe()}:{sys.exc_info()}')
            return
        
        try:
            attendance: Attendance = await sync_to_async(event.GetAttendance)()
        except:
            logger.critical(f'{sys._getframe()}:{sys.exc_info()}')
            return
        
        batchCells = []
        batchClear = []
        batchData = [] #[[],[],....]
        
        for i, option in enumerate(optionPresets.options):
            cell: str = templatePreset.cells[str(optionPresets.id)][option['label']]
            if cell != 'None':
                splitCell = re.split(r'(\d+)', cell)
                cell = splitCell[0] + str(int(splitCell[1]))

                if cell not in batchCells:
                    batchClear.append(cell + ':' + splitCell[0])
                    batchCells.append(cell)
                
                uNames = []
                signups = attendance.get_signup_option_list(SignupOption(i))
                for usrID in signups:
                    try:
                        _user: DiscordUser = await sync_to_async(DiscordUser.objects.get)(id=usrID)
                    except:
                        uNames.append(f"{str(usrID)}{' ✅' if attendance.isConfirmed(usrID) else ''}")
                    else:
                        uNames.append(f"{_user.name}{' ✅' if attendance.isConfirmed(usrID) else ''}")
                
                
                if len(batchData) == 0 or len(batchData) == batchCells.index(cell):    
                    batchData.append(uNames)
                else:
                    batchData[batchCells.index(cell)] += uNames
        
        
        try:
            self.sheet.batch_clear(batchClear)
        except: 
            logger.warning(f'{sys._getframe()}:{sys.exc_info()}')
            return
        
        data = []
        for i, cell in enumerate(batchCells):
            data.append({'range': cell, 'values': self.split_list(batchData[i], 1)})

        try:
            self.sheet.batch_update(data)
        except:
            logger.warning(f'{sys._getframe()}:{sys.exc_info()}')
            return

    def split_list(self, lst, chunk_size):
        return [lst[i:i + chunk_size] for i in range(0, len(lst), chunk_size)]
    
    
    async def DeleteSheet(self):
        if self.spreadsheet and self.sheet:
            try:
                self.spreadsheet.del_worksheet(self.sheet)
            except:
                logger.critical(f'{sys._getframe()}:{sys.exc_info()}')
                
            self.sheet = None
        
    async def ArchiveSheet(self):
        if self.archive_spreadsheet and self.sheet:
            try:
                responce = self.sheet.copy_to(self.archive_spreadsheet.id)
                archivedSheet = self.archive_spreadsheet.get_worksheet_by_id(responce['sheetId'])
            except:
                logger.critical(f'{sys._getframe()}:{sys.exc_info()}')
            
            try:
                archivedSheet.update_title(self.sheet.title)
            except:
                logger.critical(f'{sys._getframe()}:{sys.exc_info()}')
            
            await self.DeleteSheet()
            
            self.sheet = None
        