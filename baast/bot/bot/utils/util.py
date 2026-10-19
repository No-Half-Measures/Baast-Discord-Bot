import re
import typing
import arrow

from hikari import (ComponentInteraction, PartialGuild, PartialCommand, Role, Member, GuildCommandPermissions, NotFoundError, 
                    CommandPermission, CommandPermissionType, Permissions, PermissionOverwriteType, RESTGuild, PermissibleGuildChannel,
                    GatewayGuild)
import hikari.permissions

from bot.bot.utils.exceptions import DatetimeError


def HumanizeReminder(reminder: tuple[int,int,int]) -> str:
    if reminder[0] == 0 and reminder[1] == 0 and reminder[2] == 0:
        return "Disabled"
    
    s = ""
    if reminder[0]:
        if reminder[0] > 24:
            days = int(reminder[0] / 24)
            minutes = int((reminder[0] / 24 - int(reminder[0] / 24)) * 24)
            
            s += f"{days} days "
            s += f"{minutes} hrs "
        else:
            s += f"{reminder[0]} hrs "
    s += f"{reminder[1]} mins "
    s += f"{reminder[2]} seconds "#not a thing in terms of the rate we check reminders every minute
    
    return s



def HumanizeReminderShort(reminder: tuple[int,int,int]) -> str:
    s = ""
    if reminder[0]:
        if reminder[0] > 24:
            days = int(reminder[0] / 24)
            minutes = int((reminder[0] / 24 - int(reminder[0] / 24)) * 24)
            
            s += f"{days}D "
            s += f"{minutes}:"
        else:
            s += f"{reminder[0]}:"
    s += f"{reminder[1]}:"
    s += f"{reminder[2]}"
    return s

def DBifyReminder(reminder: tuple[int,int,int]) -> str:
    s = ""
    s += f"{reminder[0]}:"
    s += f"{reminder[1]}:"
    s += f"{reminder[2]}"
    return s


def ConvertTimeFromDB (dbtime: str) -> str:
    sTime = dbtime.split(':')

    hours: int = 0
    minutes: int = 0
    seconds: int = 0

    if 'd' in sTime[0].lower():
        split_string = sTime[0].lower().split("days,", 1)
        try:
            hours = (24 * int(split_string[0]))

            if len(split_string) > 1:
                hours += int(split_string[1])
        except ValueError:
            raise ValueError
    else:
        try:
            hours = int(sTime[0])
        except ValueError:
            raise ValueError

    if len(sTime) == 2:
        try:
            minutes = int(sTime[1])
        except ValueError:
            raise ValueError
    elif len(sTime) == 3:
        try:
            seconds = int(sTime[2])
        except ValueError:
            raise ValueError

    sTime = ''
    if hours > 0:
        sTime += f'{hours} hours '
    if minutes > 0:
        sTime += f'{minutes} minutes '
    if seconds > 0:
        sTime += f'{seconds} seconds '

    return sTime

def ConvertTimeFromDBToValues (dbtime: str) -> tuple[int,int,int]:
    sTime = dbtime.split(':')

    hours: int = 0
    minutes: int = 0
    seconds: int = 0

    if 'd' in sTime[0].lower():
        split_string = sTime[0].lower().split("days,", 1)
        try:
            hours = (24 * int(split_string[0]))

            if len(split_string) > 1:
                hours += int(split_string[1])
        except ValueError:
            raise ValueError
    else:
        try:
            hours = int(sTime[0])
        except ValueError:
            raise ValueError

    if len(sTime) == 2:
        try:
            minutes = int(sTime[1])
        except ValueError:
            raise ValueError
    elif len(sTime) == 3:
        try:
            seconds = int(sTime[2])
        except ValueError:
            raise ValueError

    return hours, minutes, seconds


def has_permissions(member: Member, permissions: Permissions) -> bool:
    roles = member.get_roles()
    # Convert to list to avoid any potential iteration issues
    roles_list = list(roles) if not isinstance(roles, list) else roles
    perms = Permissions.NONE
    
    for r in roles_list:
        perms |= r.permissions
        if perms.__contains__(permissions):
            return True
    
    return False

def HasChannelPermission(channel: PermissibleGuildChannel, guild: GatewayGuild, member: Member, reqPerms: Permissions = Permissions.VIEW_CHANNEL) -> bool:
    # Guild owner always has all permissions
    if member.id == guild.owner_id:
        return True
    
    # Start with base permissions from member's roles
    base_permissions = Permissions.NONE
    for role_id in member.role_ids:
        role = guild.get_role(role_id)
        if role:
            base_permissions |= role.permissions
    
    # Apply channel permission overwrites
    # Process overwrites in order: @everyone role first, then other roles, then member-specific
    overwrite_ids = list(channel.permission_overwrites.keys())
    
    # Sort overwrites: @everyone first, then roles by position (highest first), then members
    def sort_key(overwrite_id):
        overwrite = channel.permission_overwrites[overwrite_id]
        if overwrite.type == PermissionOverwriteType.ROLE:
            if overwrite_id == guild.id:  # @everyone role
                return (0, 0)  # @everyone comes first
            role = guild.get_role(overwrite_id)
            if role:
                return (1, -role.position)  # Higher position = lower number (reverse sort)
            return (1, 0)
        else:  # MEMBER overwrite
            return (2, overwrite_id)
    
    overwrite_ids.sort(key=sort_key)
    
    # Apply overwrites in order
    final_permissions = base_permissions
    
    for overwrite_id in overwrite_ids:
        overwrite = channel.permission_overwrites[overwrite_id]
        
        if overwrite.type == PermissionOverwriteType.MEMBER:
            if overwrite_id == member.id:
                # Remove denied permissions and add allowed permissions
                final_permissions = (final_permissions & ~overwrite.deny) | overwrite.allow
        elif overwrite.type == PermissionOverwriteType.ROLE:
            if overwrite_id == guild.id:  # @everyone role
                # Apply @everyone overwrite
                final_permissions = (final_permissions & ~overwrite.deny) | overwrite.allow
            elif overwrite_id in member.role_ids:
                # Apply role-specific overwrite
                final_permissions = (final_permissions & ~overwrite.deny) | overwrite.allow
    
    # Check if the member has all required permissions
    return (final_permissions & reqPerms) == reqPerms

def validate_interval(interval_str: str) -> int:
    """
    Validates interval string and converts it to days.
    Valid formats: '6D' (days), '3W' (weeks), '1M' (months)
    Returns: interval in days
    Raises: ValueError if format is invalid
    """
    if not interval_str or len(interval_str) < 2:
        raise ValueError("Invalid interval format")
    
    # Convert to uppercase for consistency
    interval_str = interval_str.upper().strip()
    
    # Get the number and unit parts
    try:
        number = int(interval_str[:-1])
        unit = interval_str[-1]
    except ValueError:
        raise ValueError("Invalid number format")
    
    if number < 0:
        raise ValueError("Interval must be greater than 0")
    
    # Convert to days based on unit
    match unit:
        case 'D':
            return number
        case 'W':
            return number * 7
        case 'M':
            return number * 30  # Approximate month as 30 days
        case _:
            raise ValueError("Invalid unit. Use D (days), W (weeks), or M (months)")

    
def validate_datetime(datetimeStr: str, require_time: bool = True) -> tuple[DatetimeError, arrow.Arrow]:
    try:
        splus = r'\s+'
        utc_start_time: arrow.Arrow = (
            arrow.get(
                datetimeStr,
                [fr"DD/MM/YYYY{fr'[{splus}]h:mm[{splus}]A ZZZ' if require_time else ''}", 
                fr"DD/MM/YYYY{fr'[{splus}]HH:mm ZZZ' if require_time else ''}", 
                fr"DD/MM/YYYY{fr'[{splus}]H:mm ZZZ' if require_time else ''}",
                fr"D/M/YYYY{fr'[{splus}]h:mm[{splus}]A ZZZ' if require_time else ''}", 
                fr"D/M/YYYY{fr'[{splus}]HH:mm ZZZ' if require_time else ''}", 
                fr"D/M/YYYY{fr'[{splus}]H:mm ZZZ' if require_time else ''}"]
            )
        )
    except:
        #await user.send(content=Embed(title=None, description='Invalid Date/Time! Try Again...', color=hikari.Color(0xff0000)))
        return DatetimeError.NotValid, None
    else:
        if utc_start_time.to('UTC') < arrow.utcnow():
            #await user.send(content=Embed(title=None, description='Start time can\'t be in the past! Try Again...', color=hikari.Color(0xff0000)))
            return DatetimeError.PreNow, None
        else:
            return DatetimeError.Valid, utc_start_time
        

def validate_time(timeStr: str) -> tuple[int,int,int]:
    sTime = timeStr.split(':')

    hours: int = 0
    minutes: int = 0
    seconds: int = 0

    if 'd' in sTime[0].lower():
        split_string = sTime[0].lower().split("d", 1)
        try:
            hours = (24 * int(split_string[0]))

            if len(split_string) > 1:
                hours += int(split_string[1])
        except ValueError:
            raise ValueError
    else:
        try:
            hours = int(sTime[0])
        except ValueError:
            raise ValueError

    if len(sTime) == 2:
        try:
            minutes = int(sTime[1])
        except ValueError:
            raise ValueError
    elif len(sTime) == 3:
        try:
            seconds = int(sTime[2])
        except ValueError:
            raise ValueError
    elif len(sTime) > 3:
        raise ValueError
    
    return hours, minutes, seconds


from loguru import logger
async def CanManage_(interaction: ComponentInteraction, guild: PartialGuild | RESTGuild, base: str = 'event') -> bool:
    
    if has_permissions(interaction.member, Permissions.ADMINISTRATOR) or guild.owner_id == interaction.member.id:
        return True
    
    cmds: typing.Sequence[PartialCommand] = await interaction.app.rest.fetch_application_commands(guild.get_my_member().id, guild)
    
    member: Member = await interaction.app.rest.fetch_member(guild, interaction.user)
    roles: typing.Sequence[Role] = member.get_roles()
    # Convert to list to avoid any potential iteration issues
    roles_list = list(roles) if not isinstance(roles, list) else roles
    
    for c in cmds:
        if c.name == base:
            try:
                gcp: GuildCommandPermissions = await c.fetch_guild_permissions(guild)
            except NotFoundError: #No Overrides
                defulatPerm = c.default_member_permissions
                
                roles = await member.fetch_roles()
                permissions = Permissions.NONE
                for role in roles:
                    permissions |= role.permissions
                    
                if (permissions & defulatPerm) == defulatPerm:
                    return True
                return False
            except:
                logger.info(f'{interaction.user} has an exception for {base} in {guild}')
                return False
            else:
                perms: typing.Sequence[CommandPermission] = gcp.permissions
                for perm in perms:
                    if perm.type == CommandPermissionType.USER and perm.id == interaction.user.id:
                        return perm.has_access
                    elif perm.type == CommandPermissionType.ROLE:
                        for role in roles:
                            if perm.id == role.id:
                                return perm.has_access    
    return False


def discord_markdown_to_html(text):
    # Convert bold
    text = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', text)
    text = re.sub(r'__(.*?)__', r'<b>\1</b>', text)
    
    # Convert italic
    text = re.sub(r'\*(.*?)\*', r'<i>\1</i>', text)
    text = re.sub(r'_(.*?)_', r'<i>\1</i>', text)
    
    # Convert strikethrough
    text = re.sub(r'~~(.*?)~~', r'<s>\1</s>', text)
    
    # Convert inline code
    text = re.sub(r'`(.*?)`', r'<code>\1</code>', text)
    
    # Convert code block
    text = re.sub(r'```(.*?)```', r'<pre><code>\1</code></pre>', text, flags=re.DOTALL)
    
    # Convert links
    text = re.sub(r'\[(.*?)\]\((.*?)\)', r'<a href="\2">\1</a>', text)
    
    # Convert unordered list
    text = re.sub(r'^\s*-\s+(.*)', r'<ul><li>\1</li></ul>', text, flags=re.MULTILINE)
    
    # Convert ordered list
    text = re.sub(r'^\s*\d+\.\s+(.*)', r'<ol><li>\1</li></ol>', text, flags=re.MULTILINE)
    
    # Merge multiple <ul> or <ol> tags into one
    text = text.replace('</ul><ul>', '')
    text = text.replace('</ol><ol>', '')

    return text