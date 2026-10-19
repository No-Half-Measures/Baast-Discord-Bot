import sys
from typing import List

from hikari.channels import ThreadMember
import hikari



async def ThreadHasUser(ThreadMembers: List[ThreadMember], user: hikari.User):
    for m in ThreadMembers:
        if m.user_id == user.id:
            return True
    return False
