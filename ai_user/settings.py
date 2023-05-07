import importlib
import logging
import discord
import openai
import tiktoken
from typing import Optional
from redbot.core import checks, commands
from redbot.core.utils.menus import SimpleMenu

from ai_user.abc import MixinMeta
from ai_user.prompts.constants import DEFAULT_PROMPT, PRESETS, SCAN_IMAGE_MODES

logger = logging.getLogger("red.bz_cogs.ai_user")


class Settings(MixinMeta):
    @commands.group()
    @commands.guild_only()
    async def ai_user(self, _):
        """ Utilize OpenAI to reply to messages and images in approved channels """
        pass

    @ai_user.command()
    async def forget(self, ctx: commands.Context):
        """ Forces the AI to forget the current conversation up to this point """
        if not ctx.channel.permissions_for(ctx.author).manage_messages\
                and not await self.config.guild(ctx.guild).public_forget():
            return await ctx.react_quietly("❌")

        self.override_prompt_start_time[ctx.guild.id] = ctx.message.created_at
        await ctx.react_quietly("✅")

    @ai_user.command(aliases=["settings", "showsettings"])
    async def config(self, ctx: commands.Context):
        """ Returns current config """
        whitelist = await self.config.guild(ctx.guild).channels_whitelist()
        channels = [f"<#{channel_id}>" for channel_id in whitelist]

        embed = discord.Embed(title="AI User Settings", color=await ctx.embed_color())
        embed.add_field(name="Model",
                        value=await self.config.guild(ctx.guild).model(), inline=True)
        embed.add_field(name="Filter Responses",
                        value=await self.config.guild(ctx.guild).filter_responses(), inline=True)
        embed.add_field(name="Reply Percent",
                        value=f"{await self.config.guild(ctx.guild).reply_percent() * 100:.2f}%", inline=True)
        embed.add_field(name="Scan Images",
                        value=await self.config.guild(ctx.guild).scan_images(), inline=True)
        embed.add_field(name="Scan Image Mode",
                        value=await self.config.guild(ctx.guild).scan_images_mode(), inline=True)
        embed.add_field(name="Scan Image Max Size",
                        value=f"{await self.config.guild(ctx.guild).max_image_size() / 1024 / 1024:.2f} MB", inline=True)
        embed.add_field(name="Always Reply on Ping or Reply",
                        value=await self.config.guild(ctx.guild).reply_to_mentions_replies(), inline=False)
        embed.add_field(name="Max Messages in History",
                        value=f"{await self.config.guild(ctx.guild).messages_backread()}", inline=False)
        embed.add_field(name="Max Time (s) between each Message in History",
                        value=await self.config.guild(ctx.guild).messages_backread_seconds(), inline=False)
        embed.add_field(name="Public Forget Command",
                        value=await self.config.guild(ctx.guild).public_forget(), inline=False)
        embed.add_field(name="Whitelisted Channels",
                        value=" ".join(channels) if channels else "None", inline=False)
        return await ctx.send(embed=embed)

    @ai_user.group()
    @checks.is_owner()
    async def image(self, _):
        """ Change the image scan setting for the current server. (See cog README.md) """
        pass

    @image.command(name="scan")
    @checks.is_owner()
    async def image_scanning(self, ctx: commands.Context):
        """ Toggle image scanning for the current server """
        value = not (await self.config.guild(ctx.guild).scan_images())
        await self.config.guild(ctx.guild).scan_images.set(value)
        embed = discord.Embed(
            title="Scanning Images for this server now set to:",
            description=f"{value}",
            color=await ctx.embed_color())
        return await ctx.send(embed=embed)

    @image.command(name="maxsize")
    @checks.is_owner()
    async def image_maxsize(self, ctx: commands.Context, new_value: float):
        """ Set max download size in Megabytes for image scanning """
        await self.config.guild(ctx.guild).max_image_size.set(new_value * 1024 * 1024)
        embed = discord.Embed(
            title="Max download size to scan images now set to:",
            description=f"{new_value:.2f} MB",
            color=await ctx.embed_color())
        return await ctx.send(embed=embed)

    @image.command(name="mode")
    @checks.is_owner()
    async def image_mode(self, ctx: commands.Context, new_value: str):
        """ Set method to scan, local or ai-horde (see cog README.md) """
        if new_value not in SCAN_IMAGE_MODES:
            await ctx.send(f"Invalid mode. Choose from: {', '.join(SCAN_IMAGE_MODES)}")
        elif new_value == "local":
            try:
                importlib.import_module("pytesseract")
                importlib.import_module("torch")
                importlib.import_module("transformers")
                await self.config.guild(ctx.guild).scan_images_mode.set(new_value)
                embed = discord.Embed(title="Scanning Images for this server now set to", color=await ctx.embed_color())
                embed.add_field(name=":warning: WILL CAUSE HEAVY CPU LOAD :warning:", value=new_value, inline=False)
                return await ctx.send(embed=embed)
            except:
                logger.error("Image processing dependencies import failed. ", exc_info=True)
                await self.config.guild(ctx.guild).scan_images_mode.set("ai-horde")
                return await ctx.send("Local image processing dependencies not available. Please install them (see cog README.md) to use this feature locally.")
        elif new_value == "ai-horde":
            await self.config.guild(ctx.guild).scan_images_mode.set("ai-horde")
            embed = discord.Embed(title="Scanning Images for this server now set to", description=new_value, color=await ctx.embed_color())
            if (await self.bot.get_shared_api_tokens("ai-horde")).get("api_key"):
                key_description = "Key set."
            else:
                key_description = f"No key set. \n Request will be lower priority.\n  \
                                   Create one [here](https://stablehorde.net/#:~:text=0%20alchemy%20forms.-,Usage,-First%20Register%20an)\
                                   and set it with `{ctx.clean_prefix}set api ai-horde api_key,API_KEY`"
            embed.add_field(
                name="AI Horde API key:",
                value=key_description,
                inline=False)
            embed.add_field(
                name="Reminder",
                value="AI Horde is a crowdsourced volunteer service. \n Please contribute back if heavily used. See [here](https://stablehorde.net/)",
                inline=False)
            return await ctx.send(embed=embed)

    @ai_user.command()
    @checks.is_owner()
    async def percent(self, ctx: commands.Context, new_value: float):
        """ Change the bot's response chance """
        await self.config.guild(ctx.guild).reply_percent.set(new_value / 100)
        await self.cache_guild_options(ctx)
        embed = discord.Embed(
            title="Chance that the bot will reply on this server is now:",
            description=f"{new_value:.2f}%",
            color=await ctx.embed_color())
        return await ctx.send(embed=embed)

    @ai_user.command()
    @checks.is_owner()
    async def model(self, ctx: commands.Context, new_value: str):
        """ Changes chat completion model """
        if not openai.api_key:
            await self.initalize_openai(ctx)

        models_list = openai.Model.list()
        gpt_models = [model.id for model in models_list['data']
                      if model.id.startswith('gpt')]

        if new_value not in gpt_models:
            return await ctx.send(f"Invalid model. Choose from: {', '.join(gpt_models)}")

        await self.config.guild(ctx.guild).set(new_value)
        embed = discord.Embed(
            title="This server's chat model is now set to:",
            description=new_value,
            color=await ctx.embed_color())
        return await ctx.send(embed=embed)

    @ai_user.command()
    @checks.admin_or_permissions(manage_guild=True)
    async def filter_responses(self, ctx: commands.Context):
        """ Toggles rudimentary filtering of canned replies """
        value = not await self.config.guild(ctx.guild).filter_responses()
        await self.config.guild(ctx.guild).filter_responses.set(value)
        embed = discord.Embed(
            title="Filtering canned responses for this server now set to:",
            description=f"{value}",
            color=await ctx.embed_color())
        return await ctx.send(embed=embed)

    @ai_user.command()
    @checks.admin_or_permissions(manage_guild=True)
    async def add(self, ctx: commands.Context, channel: discord.TextChannel):
        """ Add a channel to the whitelist to allow the bot to reply in """
        if not channel:
            return await ctx.send("Invalid channel mention, use #channel")
        new_whitelist = await self.config.guild(ctx.guild).channels_whitelist()
        if channel.id in new_whitelist:
            return await ctx.send("Channel already in whitelist")
        new_whitelist.append(channel.id)
        await self.config.guild(ctx.guild).channels_whitelist.set(new_whitelist)
        await self.cache_guild_options(ctx)
        embed = discord.Embed(title="The server whitelist is now:", color=await ctx.embed_color())
        channels = [f"<#{channel_id}>" for channel_id in new_whitelist]
        embed.description = "\n".join(channels) if channels else "None"
        return await ctx.send(embed=embed)

    @ai_user.command()
    @checks.admin_or_permissions(manage_guild=True)
    async def remove(self, ctx: commands.Context, channel: discord.TextChannel):
        """ Remove a channel from the whitelist """
        if not channel:
            return await ctx.send("Invalid channel mention, use #channel")
        new_whitelist = await self.config.guild(ctx.guild).channels_whitelist()
        if channel.id not in new_whitelist:
            return await ctx.send("Channel not in whitelist")
        new_whitelist.remove(channel.id)
        await self.config.guild(ctx.guild).channels_whitelist.set(new_whitelist)
        await self.cache_guild_options(ctx)
        embed = discord.Embed(title="The server whitelist is now:", color=await ctx.embed_color())
        channels = [f"<#{channel_id}>" for channel_id in new_whitelist]
        embed.description = "\n".join(channels) if channels else "None"
        return await ctx.send(embed=embed)

    @ai_user.command()
    @checks.is_owner()
    async def mentions_replies(self, ctx: commands.Context):
        """ Toggles bot always replying to mentions/replies """
        value = not await self.config.guild(ctx.guild).reply_to_mentions_replies()
        await self.config.guild(ctx.guild).reply_to_mentions_replies.set(value)
        embed = discord.Embed(
            title="Always replying to mentions or replies for this server now set to:",
            description=f"{value}",
            color=await ctx.embed_color())
        return await ctx.send(embed=embed)

    @ai_user.command()
    @checks.admin_or_permissions(manage_guild=True)
    async def public_forget(self, ctx: commands.Context):
        """ Toggles whether anyone can use the forget command, or only moderators """
        value = not await self.config.guild(ctx.guild).public_forget()
        await self.config.guild(ctx.guild).public_forget.set(value)
        embed = discord.Embed(
            title="Anyone can use the forget command:",
            description=f"{value}",
            color=await ctx.embed_color())
        return await ctx.send(embed=embed)

    @ai_user.group()
    @checks.is_owner()
    async def history(self, _):
        """ Change the prompt context settings for the current server """
        pass

    @history.command()
    @checks.is_owner()
    async def backread(self, ctx: commands.Context, new_value: int):
        """ Set max amount of messages to be used """
        await self.config.guild(ctx.guild).messages_backread.set(new_value)
        embed = discord.Embed(
            title="The number of previous messages used for context on this server is now:",
            description=f"{new_value}",
            color=await ctx.embed_color())
        return await ctx.send(embed=embed)

    @history.command()
    @checks.is_owner()
    async def time(self, ctx: commands.Context, new_value: int):
        """ Set max time (s) allowed between messages to be used """
        await self.config.guild(ctx.guild).messages_backread_seconds.set(new_value)
        embed = discord.Embed(
            title="The max time (s) allowed between messages for context on this server is now:",
            description=f"{new_value}",
            color=await ctx.embed_color())
        return await ctx.send(embed=embed)

    @ai_user.group()
    @checks.admin_or_permissions(manage_guild=True)
    async def prompt(self, _):
        """ Change the prompt settings for the current server """
        pass

    @prompt.command(name="reset")
    @checks.is_owner()
    async def prompt_reset(self, ctx: commands.Context):
        """ Reset ALL prompts in this guild to default (inc. channels and members) """
        self.override_prompt_start_time[ctx.guild.id] = ctx.message.created_at
        await self.config.guild(ctx.guild).custom_text_prompt.set(None)
        for member in ctx.guild.members:
            await self.config.member(member).custom_text_prompt.set(None)
        for channel in ctx.guild.channels:
            await self.config.channel(channel).custom_text_prompt.set(None)
        embed = discord.Embed(title="All prompts have been reset.", color=await ctx.embed_color())
        return await ctx.send(embed=embed)

    @prompt.group(name="show", invoke_without_command=True)
    async def prompt_show(self, ctx):
        """ Show the prompt for the current context. Subcommands: server, members, channels """
        channel_prompt = await self.config.channel(ctx.channel).custom_text_prompt()
        prompt = channel_prompt or await self.config.guild(ctx.guild).custom_text_prompt() or DEFAULT_PROMPT
        embed = discord.Embed(
            title=f"The prompt for this {'channel' if channel_prompt else 'server'} is:",
            description=self._truncate_prompt(prompt),
            color=await ctx.embed_color())
        embed.add_field(name="Tokens", value=await self.get_tokens(ctx, prompt))
        await ctx.send(embed=embed)

    @prompt_show.command(name="server", aliases=["guild"])
    async def show_server_prompt(self, ctx: commands.Context):
        """ Show the current server prompt """
        prompt = await self.config.guild(ctx.guild).custom_text_prompt() or DEFAULT_PROMPT
        embed = discord.Embed(
            title=f"The prompt for this server is:",
            description=self._truncate_prompt(prompt),
            color=await ctx.embed_color())
        embed.add_field(name="Tokens", value=await self.get_tokens(ctx, prompt))
        await ctx.send(embed=embed)

    @prompt_show.command(name="members", aliases=["users"])
    async def show_user_prompts(self, ctx: commands.Context):
        """ Show all users with custom prompts """
        pages = []
        for member in ctx.guild.members:
            prompt = await self.config.member(member).custom_text_prompt()
            if prompt:
                page = discord.Embed(
                    title=f"The prompt for user {member.name} is:",
                    description=self._truncate_prompt(prompt),
                    color=await ctx.embed_color())
                page.add_field(name="Tokens", value=await self.get_tokens(ctx, prompt))
                pages.append(page)
        if not pages:
            return await ctx.send("No users with custom prompts")
        if len(pages) == 1:
            return await ctx.send(embed=pages[0])
        for i, page in enumerate(pages):
            page.set_footer(text=f"Page {i+1} of {len(pages)}")
        await SimpleMenu(pages).start(ctx)

    @prompt_show.command(name="channels")
    async def show_channel_prompts(self, ctx: commands.Context):
        """ Show all channels with custom prompts """
        pages = []
        for channel in ctx.guild.channels:
            prompt = await self.config.channel(channel).custom_text_prompt()
            if prompt:
                page = discord.Embed(
                    title=f"The prompt for channel #{channel.name} is:",
                    description=self._truncate_prompt(prompt),
                    color=await ctx.embed_color())
                page.add_field(name="Tokens", value=await self.get_tokens(ctx, prompt))
                pages.append(page)
        if not pages:
            return await ctx.send("No channels with custom prompts")
        if len(pages) == 1:
            return await ctx.send(embed=pages[0])
        for i, page in enumerate(pages):
            page.set_footer(text=f"Page {i+1} of {len(pages)}")
        await SimpleMenu(pages).start(ctx)

    @prompt.command(name="preset")
    @checks.admin_or_permissions(manage_guild=True)
    async def prompt_preset(self, ctx: commands.Context, *, preset: str):
        """ List presets using 'list', or set a preset """
        if preset == 'list':
            embed = discord.Embed(
                title="Presets",
                description=f"Use `{ctx.clean_prefix}ai_user prompt preset <preset>` to set a preset.",
                color=await ctx.embed_color())
            embed.add_field(name="Available presets",
                            value="\n".join(PRESETS.keys()), inline=False)
            return await ctx.send(embed=embed)
        if preset not in PRESETS:
            return await ctx.send("Invalid preset. Use `list` to see available presets.")
        await self.config.guild(ctx.guild).custom_text_prompt.set(PRESETS[preset])
        embed = discord.Embed(
            title="The prompt for this server is now changed to:",
            description=f"{self._truncate_prompt(PRESETS[preset])}",
            color=await ctx.embed_color())
        embed.add_field(name="Tokens", value=await self.get_tokens(ctx, PRESETS[preset]))
        return await ctx.send(embed=embed)

    @prompt.group(name="set", aliases=["custom", "customize"])
    @checks.is_owner()
    async def prompt_custom(self, _):
        """ Customize the prompt sent to OpenAI """
        pass

    @prompt_custom.command(name="server", aliases=["guild"])
    @checks.is_owner()
    async def set_server_prompt(self, ctx: commands.Context, *, prompt: Optional[str]):
        """ Set custom prompt for current server """
        self.override_prompt_start_time[ctx.guild.id] = ctx.message.created_at
        if not prompt:
            await self.config.guild(ctx.guild).custom_text_prompt.set(None)
            return await ctx.send(f"The prompt for this server is now reset to the default prompt")
        await self.config.guild(ctx.guild).custom_text_prompt.set(prompt)
        embed = discord.Embed(
            title="The prompt for this server is now changed to:",
            description=f"{self._truncate_prompt(prompt)}",
            color=await ctx.embed_color())
        embed.add_field(name="Tokens", value=await self.get_tokens(ctx, prompt))
        return await ctx.send(embed=embed)

    @prompt_custom.command(name="member", aliases=["user"])
    @checks.is_owner()
    async def set_user_prompt(self, ctx: commands.Context, member: discord.Member, *, prompt: Optional[str]):
        """ Set custom prompt for a member of this server, overrides server and channel prompts """
        if not prompt:
            await self.config.member(member).custom_text_prompt.set(None)
            return await ctx.send(f"The prompt for user {member.mention} is now reset to default server prompt.")
        await self.config.member(member).custom_text_prompt.set(prompt)
        embed = discord.Embed(
            title=f"The prompt for user {member.mention} is now changed to:",
            description=f"{self._truncate_prompt(prompt)}",
            color=await ctx.embed_color())
        embed.add_field(name="Tokens", value=await self.get_tokens(ctx, prompt))
        return await ctx.send(embed=embed)

    @prompt_custom.command(name="channel")
    @checks.is_owner()
    async def set_channel_prompt(self, ctx: commands.Context, *, prompt: Optional[str]):
        """ Set custom prompt for the current channel, overrides the server prompt """
        if not prompt:
            await self.config.channel(ctx.channel).custom_text_prompt.set(None)
            return await ctx.send(f"The prompt for {ctx.channel.mention} is now reset to default server prompt.")
        await self.config.channel(ctx.channel).custom_text_prompt.set(prompt)
        embed = discord.Embed(
            title=f"The prompt for channel #{ctx.channel.name} is now changed to:",
            description=f"{self._truncate_prompt(prompt)}",
            color=await ctx.embed_color())
        embed.add_field(name="Tokens", value=await self.get_tokens(ctx, prompt))
        return await ctx.send(embed=embed)

    async def cache_guild_options(self, ctx: commands.Context):
        self.cached_options[ctx.guild.id] = {
            "channels_whitelist": await self.config.guild(ctx.guild).channels_whitelist(),
            "reply_percent": await self.config.guild(ctx.guild).reply_percent(),
        }

    async def get_tokens(self, ctx: commands.Context, prompt: str) -> int:
        prompt = f"You are {ctx.guild.me.name}. {prompt}"
        encoding = tiktoken.encoding_for_model(await self.config.guild(ctx.guild).model())
        return len(encoding.encode(prompt, disallowed_special=()))

    @staticmethod
    def _truncate_prompt(prompt: str) -> str:
        return prompt[:1900] + "..." if len(prompt) > 1900 else prompt

