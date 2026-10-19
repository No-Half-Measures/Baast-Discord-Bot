from enum import Enum

class InputTooLong(Exception):
    pass
class NoValues(Exception):
    pass
class DisabledDMs(Exception):
    pass

class DatetimeError(Enum):
    NotValid = 0
    Valid = 1
    PreNow = 2
    
class SetupEnd(Exception):{}

class SetupCancel(Exception):{}