import logging
import re
from typing import Optional

import discord
from redbot.core import checks, commands
from redbot.core.utils.chat_formatting import box, pagify
from redbot.core.utils.menus import SimpleMenu

from aiuser.abc import MixinMeta, aiuser

logger = logging.getLogger("red.bz_cogs.aiuser")


class TriggerSettings(MixinMeta):
    @checks.admin_or_permissions(manage_guild=True)
    @aiuser.group()
    async def trigger(self, _):
        """ Configure trigger settings for the bot to respond to

            (All subcommands per server)
        """
        pass

    @trigger.command(name="ignore", aliases=["ignoreregex"])
    async def ignore(self, ctx: commands.Context, *, regex_pattern: Optional[str]):
        """ Messages matching this regex won't be replied to or seen, by the bot """
        if not regex_pattern:
            await self.config.guild(ctx.guild).ignore_regex.set(None)
            self.ignore_regex[ctx.guild.id] = None
            return await ctx.send("The ignore regex has been cleared.")
        try:
            self.ignore_regex[ctx.guild.id] = re.compile(regex_pattern)
        except:
            return await ctx.send("Sorry, but that regex pattern seems to be invalid.")
        await self.config.guild(ctx.guild).ignore_regex.set(regex_pattern)
        embed = discord.Embed(
            title="The ignore regex is now:",
            description=f"`{regex_pattern}`",
            color=await ctx.embed_color())
        await ctx.send(embed=embed)

    @trigger.command(name="reply_to_mentions", aliases=["mentions_replies"])
    @checks.is_owner()
    async def force_reply_to_mentions(self, ctx: commands.Context):
        """ Toggles if the bot will always reply to mentions/replies """
        value = not await self.config.guild(ctx.guild).reply_to_mentions_replies()
        await self.config.guild(ctx.guild).reply_to_mentions_replies.set(value)
        embed = discord.Embed(
            title="Always replying to mentions or replies for this server now set to:",
            description=f"{value}",
            color=await ctx.embed_color())
        return await ctx.send(embed=embed)

    @trigger.command()
    async def public_forget(self, ctx: commands.Context):
        """ Toggles whether anyone can use the forget command, or only moderators """
        value = not await self.config.guild(ctx.guild).public_forget()
        await self.config.guild(ctx.guild).public_forget.set(value)
        embed = discord.Embed(
            title="Anyone can use the forget command:",
            description=f"{value}",
            color=await ctx.embed_color())
        return await ctx.send(embed=embed)

    @trigger.group()
    async def random(self, _):
        """ Configure the random trigger

            Every 33 minutes, a RNG roll will determine if a random message will be sent using a list of topics as a prompt.
            The chosen channel must have a hour pass without a message sent in it for a random message to be sent.

            (All subcommands per server)
        """
        pass

    @random.command(name="toggle")
    @checks.is_owner()
    async def random_toggle(self, ctx: commands.Context):
        """ Toggles random message trigger """
        value = not await self.config.guild(ctx.guild).random_messages_enabled()
        await self.config.guild(ctx.guild).random_messages_enabled.set(value)
        embed = discord.Embed(
            title="Senting of random messages:",
            description=f"{value}",
            color=await ctx.embed_color())
        return await ctx.send(embed=embed)

    @random.command(name="percent", aliases=["set", "chance"])
    @checks.is_owner()
    async def set_random_rng(self, ctx: commands.Context, percent: float):
        """ Sets the chance that a random message will be sent every 33 minutes

            **Arguments**
                - `percent` A number between 0 and 100
        """
        await self.config.guild(ctx.guild).random_messages_percent.set(percent / 100)
        embed = discord.Embed(
            title="The chance that a random message will be sent is:",
            description=f"{percent:.2f}%",
            color=await ctx.embed_color())
        return await ctx.send(embed=embed)

    @random.group(name="topics")
    async def random_topics(self, _):
        """ Manage topics to be used in random messages for current server """
        pass

    @random_topics.command(name="show", aliases=["list"])
    async def show_random_topics(self, ctx: commands.Context):
        """ Lists topics to used in random messages """
        topics = await self.config.guild(ctx.guild).random_messages_topics()

        if not topics:
            return await ctx.send("The topic list is empty.")

        formatted_list = "\n".join(f"{index+1}. {topic}" for index, topic in enumerate(topics))
        pages = []
        for text in pagify(formatted_list, page_length=888):
            page = discord.Embed(
                title=f"List of random message topics in {ctx.guild.name}",
                description=box(text),
                color=await ctx.embed_color())
            pages.append(page)

        if len(pages) == 1:
            return await ctx.send(embed=pages[0])

        for i, page in enumerate(pages):
            page.set_footer(text=f"Page {i+1} of {len(pages)}")

        return await SimpleMenu(pages).start(ctx)

    @random_topics.command(name="add", aliases=["a"])
    async def add_random_topics(self, ctx: commands.Context, *, topic: str):
        """ Add a new topic """
        topics = await self.config.guild(ctx.guild).random_messages_topics()
        if topic in topics:
            return await ctx.send("That topic is already in the list.")
        if topic and len(topic) > await self.config.max_topic_length() and not await ctx.bot.is_owner(ctx.author):
            return await ctx.send(f"Topic too long. Max length is {await self.config.max_topic_length()} characters.")
        topics.append(topic)
        await self.config.guild(ctx.guild).random_messages_topics.set(topics)
        embed = discord.Embed(
            title="Added topic to random message topics:",
            description=f"{topic}",
            color=await ctx.embed_color())
        return await ctx.send(embed=embed)

    @random_topics.command(name="remove", aliases=["rm", "delete"])
    async def remove_random_topics(self, ctx: commands.Context, *, number: int):
        """ Removes a topic (by number) from the list"""
        topics = await self.config.guild(ctx.guild).random_messages_topics()
        if not (1 <= number <= len(topics)):
            return await ctx.send("Invalid topic number.")
        topic = topics[number - 1]
        topics.remove(topic)
        await self.config.guild(ctx.guild).random_messages_topics.set(topics)
        embed = discord.Embed(
            title="Removed topic from random message topics:",
            description=f"{topic}",
            color=await ctx.embed_color())
        return await ctx.send(embed=embed)
