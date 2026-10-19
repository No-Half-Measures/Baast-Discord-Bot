from hikari import ButtonStyle
from hikari.api import ButtonBuilder
from hikari.impl import ContainerComponentBuilder, SectionComponentBuilder, ThumbnailComponentBuilder, TextDisplayComponentBuilder, MessageActionRowBuilder, LinkButtonBuilder, InteractiveButtonBuilder




HelpTextDisplay = TextDisplayComponentBuilder(content=
"""## Getting Started
### Get Setup
Type the `/config` command in any channel and follow the prompts to complete server setup.
### Command access
You can manage Baast’s command permissions through Discord’s *Integrations* page:
1. Right-click your server and open **Server Settings**.
2. Navigate to **Integrations** → **Baast**.
3. From here, choose which roles or users can access each command.

These permissions also carry over to the Baast Web Panel, ensuring consistent access control.
### Creating an Event
To create an event, run `/event create` and follow the prompts.
The bot requires the following permissions to create events:
- **Channel Permissions:** `View Channel`, `Send Messages`, `Send Messages in Threads`, `Create Public Threads`, `Mention Everyone`, `Use External Emojis`
- **Global Permissions:** `Manage Roles`, `Manage Threads and Posts`""")

HelpButtons = MessageActionRowBuilder(
        components=[
            LinkButtonBuilder(
                url="https://baast.app",
                label="Website",
            ),
            LinkButtonBuilder(
                url="https://baast.app/pricing",
                label="Premium",
            ),
            LinkButtonBuilder(
                url="https://discord.gg/RNrA9Gtxmm",
                label="Support Server",
            ),
            LinkButtonBuilder(
                url="https://baast.app/docs/",
                label="Documentation",
            ),
        ]
    )



WelcomeComponents = [
    ContainerComponentBuilder(
        components=[
            SectionComponentBuilder(
                accessory=ThumbnailComponentBuilder(
                    media="https://baast.app/static/baast_icon_large.png",
                ),
                components=[
                    TextDisplayComponentBuilder(content=
"""# Welcome to Baast
Baast is your all-in-one solution for managing events on Discord. With sleek slash commands and smart automation, it makes organising, tracking, and running events effortless for your community."""),
                ]
            ),
            HelpTextDisplay,
            TextDisplayComponentBuilder(content=
"""\n\n## Key Features
- Attendance tracking
- Embed Custom Colors
- Automatic Reminders
- Recurring events *(Premium)*
- Google Calendar sync *(Premium)*
- Cross-server event sharing *(Premium)*"""),
            TextDisplayComponentBuilder(content="""For more help, check out our [documentation](https://baast.app/docs/) or join the support server.
            
**Thank you for choosing Baast!**"""),
        ]
    ),
    HelpButtons,
]


HelpComponents = [
    ContainerComponentBuilder(
        components=[
            SectionComponentBuilder(
                accessory=ThumbnailComponentBuilder(
                    media="https://baast.app/static/baast_icon_large.png",
                ),
                components=[
                    TextDisplayComponentBuilder(content=
"""# Baast Help
Baast is your all-in-one solution for managing events on Discord. With sleek slash commands and smart automation, it makes organising, tracking, and running events effortless for your community."""),
                ]
            ),
            HelpTextDisplay,
            TextDisplayComponentBuilder(content="""For more help, check out our [documentation](https://baast.app/docs/) or join the support server."""),
        ]
    ),
    HelpButtons,
]

LeaveComponents = [
    ContainerComponentBuilder(
        components=[
            SectionComponentBuilder(
                accessory=ThumbnailComponentBuilder(
                    media="https://baast.app/static/baast_icon_large.png",
                ),
                components=[
                    TextDisplayComponentBuilder(content=
"""# We're sorry to see you go!
We saw that Baast got kicked from your server!

We would love to hear why you're leaving so we can improve Baast for you and other users.

Please click the button below to leave a feedback message.
"""
),
                ]
            )
        ]
    ),
    MessageActionRowBuilder(
        components=[
            InteractiveButtonBuilder(
                style=ButtonStyle.PRIMARY,
                label="Leave Feedback",
                custom_id="leave_feedback",
            ),
            LinkButtonBuilder(
                url="https://invite.baast.app",
                label="Reinvite Baast",
            ),
        ]
    ),
]