import random
from typing import Set

import discord
from redbot.core import commands, Config

CONSENT_EMBED_TITLE = ":information_source: AI User Opt-In / Opt-Out"

class ConsentManager:
    def __init__(self, config: Config, bot: commands.Bot, guild: discord.Guild):
        self.config = config
        self.bot = bot
        self.guild = guild
    
    async def get_unknown_consent_users(self, messages) -> Set[discord.Member]:
        """Find users who haven't made an opt-in/out choice yet"""
        users = set()

        if await self.config.guild(self.guild).optin_by_default():
            return users

        for message in messages:
            if (
                (not message.author.bot)
                and (message.author.id not in await self.config.optin())
                and (message.author.id not in await self.config.optout())
            ):
                users.add(message.author)

        return users
    
    async def should_send_consent_embed(self, users: Set[discord.Member]) -> bool:
        """Decide if we should send the opt-in embed"""
        if not users:
            return False
        if await self.config.guild(self.guild).optin_disable_embed():
            return False
        # 33% chance OR if more than 3 users need to opt in
        return (random.random() <= 0.33) or (len(users) > 3)
    
    async def send_consent_embed(self, channel, users: Set[discord.Member]):
        """Send the consent embed to the channel"""
        from aiuser.context.consent.view import (
            ConsentView,  # Import here to avoid circular imports
        )
        
        users_mentions = ", ".join([user.mention for user in users])
        embed = discord.Embed(
            title=CONSENT_EMBED_TITLE,
            color=await self.bot.get_embed_color(channel),
        )
        view = ConsentView(self.config)
        embed.description = (
            f"{users_mentions}\n"
            "Please choose whether to allow a subset of your Discord messages from any server with the bot, "
            "to be sent to OpenAI or an external party.\n"
            "This will allow the bot to reply to your messages or use your messages.\n"
            "This message will disappear if all current chatters have made a choice."
        )
        await channel.send(embed=embed, view=view)
    
    async def is_user_allowed(self, user: discord.Member) -> bool:
        """Check if a user is allowed to have their messages processed"""
        if user.id in await self.config.optout():
            return False
        if user.id in await self.config.optin():
            return True
        # If not explicitly opted in/out, check default behavior
        return await self.config.guild(self.guild).optin_by_default()