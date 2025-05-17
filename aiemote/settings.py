import asyncio
import re
from typing import Optional

import discord
from emoji import EMOJI_DATA
from redbot.core import checks, commands
from redbot.core.utils.menus import SimpleMenu, start_adding_reactions
from redbot.core.utils.predicates import ReactionPredicate


class Settings:
    MATCH_DISCORD_EMOJI_REGEX = r"<a?:[A-Za-z0-9]+:[0-9]+>"

    @commands.group(name="aiemote", alias=["ai_emote"])
    @checks.admin_or_permissions(manage_guild=True)
    async def aiemote(self, _):
        """ Totally not glorified sentiment analysis™

            Picks a reaction for a message using gpt-4o-mini

            To get started, please add a channel to the whitelist with:
            `[p]aiemote allow <#channel>`
        """
        pass

    @aiemote.command(name="whitelist")
    @checks.admin_or_permissions(manage_guild=True)
    async def whitelist_list(self, ctx: commands.Context):
        """ List all channels in the whitelist """
        whitelist = self.whitelist.get(ctx.guild.id, [])
        if not whitelist:
            return await ctx.send("No channels in whitelist")
        channels = [ctx.guild.get_channel(channel_id) for channel_id in whitelist]
        embed = discord.Embed(title="Whitelist", color=await ctx.embed_color())
        embed.add_field(name="Channels", value="\n".join([channel.mention for channel in channels]))
        await ctx.send(embed=embed)

    @aiemote.command(name="allow", aliases=["add"])
    @checks.admin_or_permissions(manage_guild=True)
    async def whitelist_add(self, ctx: commands.Context, channel: discord.TextChannel):
        """ Add a channel to the whitelist

            *Arguments*
            - `<channel>` The mention of channel
        """
        whitelist = self.whitelist.get(ctx.guild.id, [])
        if channel.id in whitelist:
            return await ctx.send("Channel already in whitelist")
        whitelist.append(channel.id)
        self.whitelist[ctx.guild.id] = whitelist
        await self.config.guild(ctx.guild).whitelist.set(whitelist)
        return await ctx.tick()

    @aiemote.command(name="remove", aliases=["rm"])
    @checks.admin_or_permissions(manage_guild=True)
    async def whitelist_remove(self, ctx: commands.Context, channel: discord.TextChannel):
        """ Remove a channel from the whitelist

            *Arguments*
            - `<channel>` The mention of channel
        """
        whitelist = self.whitelist.get(ctx.guild.id, [])
        if channel.id not in whitelist:
            return await ctx.send("Channel not in whitelist")
        whitelist.remove(channel.id)
        self.whitelist[ctx.guild.id] = whitelist
        await self.config.guild(ctx.guild).whitelist.set(whitelist)
        return await ctx.tick()

    @aiemote.command(name="optinbydefault", alias=["optindefault"])
    @checks.admin_or_permissions(manage_guild=True)
    async def optin_by_default(self, ctx: commands.Context):
        """ Toggles whether users are opted in by default in this server

            This command is disabled for servers with more than 150 members.
        """
        if len(ctx.guild.members) > 150:
            return await ctx.send("You cannot enable this setting for servers with more than 150 members.")
        value = not await self.config.guild(ctx.guild).optin_by_default()
        await self.config.guild(ctx.guild).optin_by_default.set(value)
        embed = discord.Embed(
            title="Users are now opted in by default in this server:",
            description=f"{value}",
            color=await ctx.embed_color())
        return await ctx.send(embed=embed)

    @aiemote.command(name="optin")
    async def optin_user(self, ctx: commands.Context):
        """ Opt in of sending your message to OpenAI (bot-wide)

            This will allow the bot to react to your messages
        """
        optin = await self.config.optin()
        optout = await self.config.optout()

        if ctx.author.id in await self.config.optin() and ctx.author.id not in self.optout_users:
            return await ctx.send("You are already opted in bot-wide")

        optin.append(ctx.author.id)
        self.optin_users.append(ctx.author.id)
        await self.config.optin.set(optin)

        if ctx.author.id in optout:
            optout.remove(ctx.author.id)
            self.optout_users.remove(ctx.author.id)
            await self.config.optout.set(optout)

        await ctx.send("You are now opted in bot-wide")

    @aiemote.command(name="optout")
    async def optout_user(self, ctx: commands.Context):
        """ Opt out of sending your message to OpenAI (bot-wide)

            The bot will no longer react to your messages
        """
        optin = await self.config.optin()
        optout = await self.config.optout()

        if ctx.author.id not in await self.config.optin() and ctx.author.id in self.optout_users:
            return await ctx.send("You are already opted out")

        if ctx.author.id in optin:
            optin.remove(ctx.author.id)
            self.optin_users.remove(ctx.author.id)
            await self.config.optin.set(optin)

        optout.append(ctx.author.id)
        self.optout_users.append(ctx.author.id)
        await self.config.optout.set(optout)

        await ctx.send("You are now opted out bot-wide")

    @commands.group(name="aiemoteowner", alias=["ai_emote_admin"])
    @checks.is_owner()
    async def aiemote_owner(self, _):
        """ Owner only commands for aiemote
        """
        pass

    @aiemote_owner.command(name="instruction", aliases=["extra_instruction", "extra"])
    @checks.is_owner()
    async def set_extra_instruction(self, ctx: commands.Context, *, instruction: Optional[str]):
        """ Add additonal (prompting) instruction for the langauge model when picking an emoji

            *Arguments*
            - `<instruction>` The extra instruction to use
        """
        if not instruction:
            await self.config.extra_instruction.set("")
        else:
            await self.config.extra_instruction.set(instruction)
        return await ctx.tick()

    async def check_valid_emoji(self, ctx: commands.Context, emoji):
        if emoji in EMOJI_DATA.keys():
            return True
        if (not bool(re.fullmatch(self.MATCH_DISCORD_EMOJI_REGEX, emoji))):
            await ctx.send("Invalid emoji!")
            return False
        emoji = discord.PartialEmoji.from_str(emoji)
        isBotEmoji = bool(discord.utils.get(self.bot.emojis, name=emoji.name, id=emoji.id))
        if not isBotEmoji:
            await ctx.send("Invalid emoji! Custom emojis must be usable by the bot itself")
            return False
        return True

    async def add_emoji(self, ctx: commands.Context, emoji_list, emoji, description):
        if any(item["emoji"] == str(emoji) for item in emoji_list):
            await ctx.send("Emoji already in list")
            return False

        emoji_list.append({
            "description": description,
            "emoji": str(emoji)
        })
        return True

    async def remove_emoji(self, ctx: commands.Context, emoji_list, emoji):
        index = next((i for i, item in enumerate(emoji_list) if item["emoji"] == str(emoji)), -1)
        if index == -1:
            await ctx.send("Emoji not in list")
            return False

        del emoji_list[index]
        return True

    @aiemote_owner.command(name="add")
    @checks.is_owner()
    async def add_global_emoji(self, ctx: commands.Context, emoji, *, description: str):
        """ Add an emoji to the global list

            *Arguments*
            - `<emoji>` The emoji to add
            - `<description>` A description of the emoji to be used by OpenAI
        """
        if not await self.check_valid_emoji(ctx, emoji):
            return
        emojis = await self.config.global_emojis()
        if not emojis:
            emojis = []
        if await self.add_emoji(ctx, emojis, emoji, description):
            await self.config.global_emojis.set(emojis)
            await ctx.tick()

    @aiemote_owner.command(name="remove", aliases=["rm"])
    @checks.is_owner()
    async def remove_global_emoji(self, ctx: commands.Context, emoji):
        """ Remove an emoji from the global list

            *Arguments*
            - `<emoji>` The emoji to remove
        """
        if not await self.check_valid_emoji(ctx, emoji):
            return

        emojis = await self.config.global_emojis()
        if await self.remove_emoji(ctx, emojis, emoji):
            await self.config.global_emojis.set(emojis)
            await ctx.tick()

    async def create_emoji_embed(self, ctx, title: str, emojis: list):
        embeds = []
        chunk_size = 8

        if len(emojis) == 0:
            embed = discord.Embed(title=title, description="None", color=await ctx.embed_color())
            embeds.append(embed)
            return embeds

        for i in range(0, len(emojis), chunk_size):
            embed = discord.Embed(title=title, color=await ctx.embed_color())

            chunk = emojis[i: i + chunk_size]
            for item in chunk:
                partial_emoji = discord.PartialEmoji.from_str(item["emoji"])
                emoji = str(partial_emoji)
                embed.add_field(name=emoji, value=item["description"], inline=False)

            embeds.append(embed)

        if len(embeds) > 1:
            for i, page in enumerate(embeds):
                page.set_footer(text=f"Page {i+1} of {len(embeds)}")

        return embeds

    @aiemote_owner.command(name="config", aliases=["settings", "list", "conf"])
    @checks.is_owner()
    async def list_all_emoji(self, ctx: commands.Context):
        """ List all emojis in the global list (and current server list)
        """
        emojis = await self.config.global_emojis()
        globalembeds = await self.create_emoji_embed(ctx, "Global Emojis", emojis)
        emojis = await self.config.guild(ctx.guild).server_emojis()
        serverembeds = await self.create_emoji_embed(ctx, "Current Server-specific Emojis", emojis)
        settingsembed = discord.Embed(title="Main Settings", color=await ctx.embed_color())
        settingsembed.add_field(name="Percent Chance", value=f"{self.percent}%", inline=False)
        settingsembed.add_field(name="Additonal Instruction", value=await self.config.extra_instruction() or "None", inline=False)
        await ctx.send(embed=settingsembed)
        if len(globalembeds) > 1:
            await (SimpleMenu(globalembeds)).start(ctx)
        else:
            await ctx.send(embed=globalembeds[0])
        if len(serverembeds) > 1:
            await (SimpleMenu(serverembeds)).start(ctx)
        else:
            await ctx.send(embed=serverembeds[0])

    @aiemote_owner.command(name="reset")
    @checks.is_owner()
    async def reset_all_settings(self, ctx: commands.Context):
        """
        Reset *all* settings
        """
        embed = discord.Embed(
            title="Are you sure?",
            description="This will reset all settings to default! (Including ALL per server lists)",
            color=await ctx.embed_color())
        confirm = await ctx.send(embed=embed)
        start_adding_reactions(confirm, ReactionPredicate.YES_OR_NO_EMOJIS)
        pred = ReactionPredicate.yes_or_no(confirm, ctx.author)
        try:
            await ctx.bot.wait_for("reaction_add", timeout=10.0, check=pred)
        except asyncio.TimeoutError:
            return await confirm.edit(embed=discord.Embed(title="Cancelled.", color=await ctx.embed_color()))
        if pred.result is False:
            return await confirm.edit(embed=discord.Embed(title="Cancelled.", color=await ctx.embed_color()))
        else:
            await self.config.clear_all_guilds()
            await self.config.clear_all_globals()
            self.whitelist = {}
            self.percent = 50
            return await confirm.edit(embed=discord.Embed(title="Cleared.", color=await ctx.embed_color()))

    @aiemote_owner.command(name="sadd")
    @checks.is_owner()
    async def add_server_emoji(self, ctx: commands.Context, emoji, *, description: str):
        """ Add an emoji to this current server list

            *Arguments*
            - `<emoji>` The emoji to add
            - `<description>` A description of the emoji to be used by OpenAI
        """
        if not await self.check_valid_emoji(ctx, emoji):
            return
        emojis = await self.config.guild(ctx.guild).server_emojis()
        if not emojis:
            emojis = []
        if await self.add_emoji(ctx, emojis, emoji, description):
            await self.config.guild(ctx.guild).server_emojis.set(emojis)
            await ctx.tick()

    @aiemote_owner.command(name="sremove", aliases=["srm"])
    @checks.is_owner()
    async def remove_server_emoji(self, ctx: commands.Context, emoji):
        """ Remove an emoji from this current server list

            *Arguments*
            - `<emoji>` The emoji to remove
        """
        if not await self.check_valid_emoji(ctx, emoji):
            return

        emojis = await self.config.guild(ctx.guild).server_emojis()
        if await self.remove_emoji(ctx, emojis, emoji):
            await self.config.guild(ctx.guild).server_emojis.set(emojis)
            await ctx.tick()

    @aiemote_owner.command(name="percent")
    @checks.is_owner()
    async def set_percent(self, ctx: commands.Context, percent: int):
        """ Set the chance that the bot will react to a message (for all servers bot is in)

            *Arguments*
            - `<percent>` The percent chance that the bot will react to a message
        """
        if percent < 0 or percent > 100:
            return await ctx.send("Invalid percent")
        self.percent = percent
        await self.config.percent.set(percent)
        return await ctx.tick() 