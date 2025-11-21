import logging
import re
from typing import Optional, Union

import discord
from redbot.core import checks, commands

from aiuser.types.abc import MixinMeta, aiuser

logger = logging.getLogger("red.bz_cogs.aiuser")


class TriggerSettings(MixinMeta):
    @checks.admin_or_permissions(manage_guild=True)
    @aiuser.group()
    async def trigger(self, _):
        """Configure trigger settings for the bot to respond to

        (All subcommands per server)
        """
        pass

    @trigger.command(name="minlength", aliases=["min_length"])
    async def min_length(self, ctx: commands.Context, length: int):
        """Set the minimum length of messages that the bot will respond to"""
        await self.config.guild(ctx.guild).messages_min_length.set(length)
        embed = discord.Embed(
            title="The minimum length is now:",
            description=f"{length}",
            color=await ctx.embed_color(),
        )
        return await ctx.send(embed=embed)

    @trigger.command(name="ignore", aliases=["ignoreregex"])
    async def ignore(self, ctx: commands.Context, *, regex_pattern: Optional[str]):
        """Messages matching this regex won't be replied to or seen, by the bot"""
        if not regex_pattern:
            await self.config.guild(ctx.guild).ignore_regex.set(None)
            self.ignore_regex[ctx.guild.id] = None
            return await ctx.send("The ignore regex has been cleared.")
        try:
            self.ignore_regex[ctx.guild.id] = re.compile(regex_pattern)
        except Exception:
            return await ctx.send("Sorry, but that regex pattern seems to be invalid.")
        await self.config.guild(ctx.guild).ignore_regex.set(regex_pattern)
        embed = discord.Embed(
            title="The ignore regex is now:",
            description=f"`{regex_pattern}`",
            color=await ctx.embed_color(),
        )
        await ctx.send(embed=embed)

    @checks.is_owner()
    @trigger.command(name="conversation_reply_percent")
    async def conversation_reply_percent(self, ctx: commands.Context, percent: int):
        """Set a different percentage chance of the bot continuing to reply within `conversation_reply_time` time frame to better simulate a conversation.
        This is a additional percentage that will be rolled if the bot has already send a message in the last `conversation_reply_time` time frame.
        """
        if percent < 0 or percent > 100:
            return await ctx.send("Please enter a number between 0 and 100")
        await self.config.guild(ctx.guild).conversation_reply_percent.set(percent / 100)
        reply_time = await self.config.guild(ctx.guild).conversation_reply_time()
        embed = discord.Embed(
            title=f"The additional response chance within `{reply_time}s` is now:",
            description=f"{percent}%",
            color=await ctx.embed_color(),
        )
        return await ctx.send(embed=embed)

    @trigger.command(name="conversation_reply_time")
    async def conversation_reply_time(self, ctx: commands.Context, seconds: int):
        """Set the max time frame in seconds for the bot to have a `conversation_reply_percent` chance of replying to a message
        When `conversation_reply_time` have lapsed for the last bot message, `conversation_reply_percent` will not be used and be skipped.
        """
        if seconds < 0:
            return await ctx.send("Please enter a positive number")
        await self.config.guild(ctx.guild).conversation_reply_time.set(seconds)
        embed = discord.Embed(
            title="The conversation response time window is now:",
            description=f"{seconds} seconds",
            color=await ctx.embed_color(),
        )
        return await ctx.send(embed=embed)

    @trigger.command(name="reply_to_mentions", aliases=["mentions_replies"])
    @checks.is_owner()
    async def force_reply_to_mentions(self, ctx: commands.Context):
        """Toggles if the bot will always reply to mentions/replies"""
        value = not await self.config.guild(ctx.guild).reply_to_mentions_replies()
        await self.config.guild(ctx.guild).reply_to_mentions_replies.set(value)
        embed = discord.Embed(
            title="Always replying to mentions or replies for this server now set to:",
            description=f"{value}",
            color=await ctx.embed_color(),
        )
        return await ctx.send(embed=embed)

    @trigger.command()
    async def public_forget(self, ctx: commands.Context):
        """Toggles whether anyone can use the forget command, or only moderators"""
        value = not await self.config.guild(ctx.guild).public_forget()
        await self.config.guild(ctx.guild).public_forget.set(value)
        embed = discord.Embed(
            title="Anyone can use the forget command:",
            description=f"{value}",
            color=await ctx.embed_color(),
        )
        return await ctx.send(embed=embed)

    @trigger.command(name="grok")
    @checks.is_owner()
    async def grok(self, ctx: commands.Context):
        """Toggles a simple trigger where it always respond on an short message (less than 25 words) containng the word 'grok' or 'gork' AND 'true' or 'explain' or 'confirm'"""
        value = not await self.config.guild(ctx.guild).grok_trigger()
        await self.config.guild(ctx.guild).grok_trigger.set(value)
        embed = discord.Embed(
            title="The grok trigger is now:",
            description=f"{value}",
            color=await ctx.embed_color(),
        )
        return await ctx.send(embed=embed)

    @trigger.group(name="webhook")
    async def trigger_webhook(self, _):
        """Configure webhook and application bot reply settings"""
        pass

    @trigger_webhook.command(name="toggle")
    async def trigger_webhook_toggle(self, ctx: commands.Context):
        """Toggles if the bot will reply to webhooks and application bots"""
        value = not await self.config.guild(ctx.guild).reply_to_webhooks()
        await self.config.guild(ctx.guild).reply_to_webhooks.set(value)
        embed = discord.Embed(
            title="Replying to webhooks and apps for this server now set to:",
            description=f"{value}",
            color=await ctx.embed_color(),
        )
        return await ctx.send(embed=embed)

    @trigger_webhook.group(name="whitelist")
    async def trigger_webhook_whitelist(self, _):
        """Configure user ID whitelist for webhooks and application bots"""
        pass

    @trigger_webhook_whitelist.command(name="toggle")
    async def trigger_webhook_whitelist_toggle(self, ctx: commands.Context):
        """Toggles if the whitelist filtering is enabled for webhooks/apps"""
        value = not await self.config.guild(ctx.guild).webhook_whitelist_enabled()
        await self.config.guild(ctx.guild).webhook_whitelist_enabled.set(value)
        embed = discord.Embed(
            title="Webhook/app whitelist filtering is now:",
            description=f"{value}",
            color=await ctx.embed_color(),
        )
        return await ctx.send(embed=embed)

    @trigger_webhook_whitelist.command(name="add")
    async def trigger_webhook_whitelist_add(self, ctx: commands.Context, user_id: int):
        """Add a user ID to the webhook/app whitelist"""
        whitelist = await self.config.guild(ctx.guild).webhook_user_whitelist()
        if user_id in whitelist:
            return await ctx.send("That user ID is already in the whitelist")
        whitelist.append(user_id)
        await self.config.guild(ctx.guild).webhook_user_whitelist.set(whitelist)
        return await self.show_webhook_whitelist(
            ctx,
            discord.Embed(title="The webhook/app whitelist is now:", color=await ctx.embed_color()),
        )

    @trigger_webhook_whitelist.command(name="remove")
    async def trigger_webhook_whitelist_remove(self, ctx: commands.Context, user_id: int):
        """Remove a user ID from the webhook/app whitelist"""
        whitelist = await self.config.guild(ctx.guild).webhook_user_whitelist()
        if user_id not in whitelist:
            return await ctx.send("That user ID is not in the whitelist")
        whitelist.remove(user_id)
        await self.config.guild(ctx.guild).webhook_user_whitelist.set(whitelist)
        return await self.show_webhook_whitelist(
            ctx,
            discord.Embed(title="The webhook/app whitelist is now:", color=await ctx.embed_color()),
        )

    @trigger_webhook_whitelist.command(name="list", aliases=["show"])
    async def trigger_webhook_whitelist_list(self, ctx: commands.Context):
        """Show the webhook/app whitelist"""
        return await self.show_webhook_whitelist(
            ctx,
            discord.Embed(
                title="Webhook/app user ID whitelist",
                color=await ctx.embed_color(),
            ),
        )

    @trigger_webhook_whitelist.command(name="clear")
    async def trigger_webhook_whitelist_clear(self, ctx: commands.Context):
        """Clear the webhook/app whitelist"""
        await self.config.guild(ctx.guild).webhook_user_whitelist.set([])
        return await ctx.send("The webhook/app whitelist has been cleared.")

    async def show_webhook_whitelist(self, ctx: commands.Context, embed: discord.Embed):
        """Helper function to display webhook/app whitelist"""
        whitelist = await self.config.guild(ctx.guild).webhook_user_whitelist()
        if whitelist:
            embed.description = "\n".join([f"`{user_id}`" for user_id in whitelist])
        else:
            embed.description = "No user IDs whitelisted."
        return await ctx.send(embed=embed)

    @trigger.group(name="words")
    @commands.is_owner()
    async def trigger_words(self, _):
        """Configure a list of words that will make the bot always be triggered to respond to a message"""
        pass

    @trigger_words.command(name="add")
    async def trigger_words_add(self, ctx: commands.Context, *, word: str):
        """Add a word to the trigger words list"""
        words = await self.config.guild(ctx.guild).always_reply_on_words()
        if word in words:
            return await ctx.send("That word is already in the list")
        words.append(word)
        await self.config.guild(ctx.guild).always_reply_on_words.set(words)
        return await self.show_trigger_always_words(
            ctx,
            discord.Embed(
                title="The trigger words are now:", color=await ctx.embed_color()
            ),
        )

    @trigger_words.command(name="remove")
    async def trigger_words_remove(self, ctx: commands.Context, *, word: str):
        """Remove a word from the trigger words list"""
        words = await self.config.guild(ctx.guild).always_reply_on_words()
        if word not in words:
            return await ctx.send("That word is not in the list")
        words.remove(word)
        await self.config.guild(ctx.guild).always_reply_on_words.set(words)
        return await self.show_trigger_always_words(
            ctx,
            discord.Embed(
                title="The trigger words are now:", color=await ctx.embed_color()
            ),
        )

    @trigger_words.command(name="list", aliases=["show"])
    async def trigger_words_list(self, ctx: commands.Context):
        """Show the trigger words list"""
        return await self.show_trigger_always_words(
            ctx,
            discord.Embed(
                title="Trigger words that activate the bot",
                color=await ctx.embed_color(),
            ),
        )

    @trigger_words.command(name="clear")
    async def trigger_words_clear(self, ctx: commands.Context):
        """Clear the trigger words list"""
        await self.config.guild(ctx.guild).always_reply_on_words.set([])
        return await ctx.send("The trigger words list has been cleared.")

    async def show_trigger_always_words(
        self, ctx: commands.Context, embed: discord.Embed
    ):
        words = await self.config.guild(ctx.guild).always_reply_on_words()
        if words:
            embed.description = ", ".join(f"`{word}`" for word in words)
        else:
            embed.description = "No trigger words set."
        return await ctx.send(embed=embed)

    @trigger.group(name="whitelist", aliases=["whitelists"])
    async def trigger_whitelist(self, ctx: commands.Context):
        """If configured, only whitelisted roles / users can trigger a response in whitelisted channels"""
        pass

    @trigger_whitelist.command(name="add")
    async def trigger_whitelist_add(
        self, ctx: commands.Context, new: Union[discord.Role, discord.Member]
    ):
        """Add a role/user to the whitelist"""
        if isinstance(new, discord.Role):
            whitelist = await self.config.guild(ctx.guild).roles_whitelist()
            if new.id in whitelist:
                return await ctx.send("That role is already whitelisted")
            whitelist.append(new.id)
            await self.config.guild(ctx.guild).roles_whitelist.set(whitelist)

        elif isinstance(new, discord.Member):
            whitelist = await self.config.guild(ctx.guild).members_whitelist()
            if new.id in whitelist:
                return await ctx.send("That user is already whitelisted")
            whitelist.append(new.id)
            await self.config.guild(ctx.guild).members_whitelist.set(whitelist)

        return await self.show_trigger_whitelist(
            ctx,
            discord.Embed(title="The whitelist is now:", color=await ctx.embed_color()),
        )

    @trigger_whitelist.command(name="remove")
    async def trigger_whitelist_remove(
        self, ctx: commands.Context, rm: Union[discord.Role, discord.Member]
    ):
        """Remove a user/role from the whitelist"""
        if isinstance(rm, discord.Role):
            whitelist = await self.config.guild(ctx.guild).roles_whitelist()
            if rm.id not in whitelist:
                return await ctx.send("That role is not whitelisted")
            whitelist.remove(rm.id)
            await self.config.guild(ctx.guild).roles_whitelist.set(whitelist)

        elif isinstance(rm, discord.Member):
            whitelist = await self.config.guild(ctx.guild).members_whitelist()
            if rm.id not in whitelist:
                return await ctx.send("That user is not whitelisted")
            whitelist.remove(rm.id)
            await self.config.guild(ctx.guild).members_whitelist.set(whitelist)
        return await self.show_trigger_whitelist(
            ctx,
            discord.Embed(title="The whitelist is now:", color=await ctx.embed_color()),
        )

    @trigger_whitelist.command(name="list", aliases=["show"])
    async def trigger_whitelist_list(self, ctx: commands.Context):
        """Show the whitelist"""
        return await self.show_trigger_whitelist(
            ctx,
            discord.Embed(
                title="Whitelist of users/roles that will trigger LLM",
                color=await ctx.embed_color(),
            ),
        )

    @trigger_whitelist.command(name="clear")
    async def trigger_whitelist_clear(self, ctx: commands.Context):
        """Clear the whitelist, allowing anyone to trigger LLM in whitelisted channels"""
        await self.config.guild(ctx.guild).roles_whitelist.set([])
        await self.config.guild(ctx.guild).members_whitelist.set([])
        return await ctx.send("The whitelist has been cleared.")

    async def show_trigger_whitelist(self, ctx: commands.Context, embed: discord.Embed):
        roles_whitelist = await self.config.guild(ctx.guild).roles_whitelist()
        users_whitelist = await self.config.guild(ctx.guild).members_whitelist()
        if roles_whitelist:
            embed.add_field(
                name="Roles",
                value="\n".join([f"<@&{r}>" for r in roles_whitelist]),
                inline=False,
            )
        if users_whitelist:
            embed.add_field(
                name="Users",
                value="\n".join([f"<@{u}>" for u in users_whitelist]),
                inline=False,
            )
        if not roles_whitelist and not users_whitelist:
            embed.description = (
                "Nothing whitelisted\nAnyone can trigger bot in whitelisted channels"
            )
        return await ctx.send(embed=embed)
