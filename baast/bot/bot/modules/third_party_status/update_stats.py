import aiohttp
import json

import lightbulb
from lightbulb import Client


from loguru import logger


loader = lightbulb.Loader()
@loader.task(lightbulb.uniformtrigger(hours=24))
async def update_stats(client: Client) -> None:
    guilds = await client.rest.fetch_my_guilds()
    server_count = len(guilds)
    shard_count = 1#client.shard_count
    
    async with aiohttp.ClientSession() as session:
        data = {"server_count": server_count, "shard_count": shard_count}
        json_data = json.dumps(data)
        headers = {"Authorization": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpZCI6IjkxNjgxNzE4MTA4ODU3MTQzMyIsImJvdCI6dHJ1ZSwiaWF0IjoxNjgzODM4NTQ1fQ.Q3gseUa_zuCTKtuG0tQy_84U7oXtdNXwNfQ5SzgBohs", "Content-Type": "application/json"}
        resp = await session.post(url="https://top.gg/api/bots/916817181088571433/stats", headers=headers, data=json_data)
        
        if resp.status != 200:
            print(f"Failed to update TopGG stats: {resp.status} {await resp.text()}")
        else:
            print("TopGG stats updated successfully.")
    await session.close()
    
    
    async with aiohttp.ClientSession() as session:
        data = {"users": 0, "guilds": server_count, "voice_connections": 0}
        json_data = json.dumps(data)
        headers = {"Authorization": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0IjoxLCJpZCI6IjkxNjgxNzE4MTA4ODU3MTQzMyIsImlhdCI6MTc1NTA5Njk1OH0.upLFAjZ-kA4ZLx7ME749KfftBNXuBfPwkV3HnqoZ6KA", "Content-Type": "application/json"}
        resp = await session.post(url="https://discordbotlist.com/api/v1/bots/916817181088571433/stats", headers=headers, data=json_data)
        
        if resp.status != 200:
            print(f"Failed to update DiscordBotList stats: {resp.status} {await resp.text()}")
        else:
            print("DiscordBotList stats updated successfully.")
    await session.close()
    
    
    async with aiohttp.ClientSession() as session:
        data = [
        {
            "name": "help",
            "description": "Get help with using the bot.",
            "type": 1
        },
        {
            "name": "event",
            "description": "Create and manage events.",
            "type": 1
        },
        {
            "name": "calendar",
            "description": "Create and manage a google calendar.",
            "type": 1
        },
        ]
        json_data = json.dumps(data)
        headers = {"Authorization": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0IjoxLCJpZCI6IjkxNjgxNzE4MTA4ODU3MTQzMyIsImlhdCI6MTc1NTA5Njk1OH0.upLFAjZ-kA4ZLx7ME749KfftBNXuBfPwkV3HnqoZ6KA", "Content-Type": "application/json"}
        resp = await session.post(url="https://discordbotlist.com/api/v1/bots/916817181088571433/commands", headers=headers, data=json_data)
        
        if resp.status != 200:
            print(f"Failed to update DiscordBotList stats: {resp.status} {await resp.text()}")
        else:
            print("DiscordBotList stats updated successfully.")
    await session.close()
        