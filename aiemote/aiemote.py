import logging
import random
from typing import Optional

import discord
import openai
import tiktoken
from redbot.core import Config, checks, commands
from redbot.core.bot import Red

logger = logging.getLogger("red.bz_cogs.aiemote")


class aiemote(commands.Cog):
    def __init__(self, bot):
        super().__init__()
        self.bot: Red = bot
        self.config = Config.get_conf(self, identifier=754069)
        self.encoding = tiktoken.encoding_for_model("gpt-3.5-turbo")

        default_global = {
            "percent": 50,
            "global_emojis": [
                {
                    "description": "A happy face",
                    "emoji": "😀",
                },
                {
                    "description": "A sad face",
                    "emoji": "😢",
                },
            ],
            "extra_instruction": "",
        }

        default_guild = {
            "server_emojis": [],
            "whitelist": []
        }

        self.config.register_guild(**default_guild)
        self.config.register_global(**default_global)

    async def cog_load(self):
        self.whitelist = {}
        all_config = await self.config.all_guilds()
        self.percent = await self.config.percent()
        for guild_id, config in all_config.items():
            self.whitelist[guild_id] = config["whitelist"]

    @commands.Cog.listener()
    async def on_red_api_tokens_update(self, service_name, api_tokens):
        if service_name == "openai":
            openai.api_key = api_tokens.get("api_key")

    async def initalize_openai(self, ctx: commands.Context):
        openai.api_key = (await self.bot.get_shared_api_tokens("openai")).get("api_key")
        if not openai.api_key:
            await ctx.send(
                f"OpenAI API key not set for `aiemote`. "
                f"Please set it with `{ctx.clean_prefix}set api openai api_key,API_KEY`")

    @commands.Cog.listener()
    async def on_message_without_command(self, message: discord.Message):
        ctx: commands.Context = await self.bot.get_context(message)
        if not (await self.is_valid_to_react(ctx)):
            return
        if (self.percent < random.randint(0, 99)):
            return
        emoji = await self.pick_emoji(message)
        if emoji:
            await message.add_reaction(emoji)

    async def pick_emoji(self, message: discord.Message):
        options = "\n"
        emojis = await self.config.guild(message.guild).emojis() or []
        emojis += await self.config.global_emojis() or []
        for index, value in enumerate(emojis):
            options += f"{index}. {value['description']}\n"

        logit_bias = {}
        for i in range(len(emojis)):
            encoded_value = self.encoding.encode(str(i))
            if len(encoded_value) == 1:
                logit_bias[encoded_value[0]] = 100

        system_prompt = f"You are in a chat room. You will pick an emoji for the following message. {await self.config.extra_instruction()} Here are your options: {options} Your answer will be a int between 0 and {len(emojis)-1}."
        print(system_prompt)
        content = self.stringify_any_mentions(message)
        try:
            response = await openai.ChatCompletion.acreate(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": content}
                ],
                max_tokens=1,
                logit_bias=logit_bias,
            )
        except:
            logger.error("Failed to get response from OpenAI", exc_info=True)
            return None
        response = response["choices"][0]["message"]["content"]
        if response.isnumeric():
            index = int(response)
            if index < 0 or index >= len(emojis):
                return None
            partial_emoji = discord.PartialEmoji.from_str(emojis[index]["emoji"])
            return partial_emoji
        else:
            logger.warning(
                f" Skipping react! Non-numeric response from OpenAI: {response}. (Please report to dev if this occurs often)")
            return None

    async def is_valid_to_react(self, ctx: commands.Context):
        if ctx.guild is None or ctx.author.bot:
            return False

        whitelist = self.whitelist.get(ctx.guild.id, [])
        if await self.bot.cog_disabled_in_guild(self, ctx.guild):
            return False
        if not await self.bot.ignored_channel_or_guild(ctx):
            return False
        if not await self.bot.allowed_by_whitelist_blacklist(ctx.author):
            return False

        if (not isinstance(ctx.channel, discord.Thread) and (ctx.channel.id not in whitelist)):
            return False
        if (isinstance(ctx.channel, discord.Thread) and (ctx.channel.parent_id not in whitelist)):
            return False

        if not openai.api_key:
            await self.initalize_openai(ctx)
            if not openai.api_key:
                return False

        # skipping images / embeds
        if not ctx.message.content or (ctx.message.attachments and ctx.message.attachments.count() > 0):
            return False

        # skipping long / short messages
        if len(ctx.message.content) > 1500 or len(ctx.message.content) < 10:
            logger.debug(f"Skipping message in {ctx.guild.name} with length {len(ctx.message.content)}")
            return False

        return True

    def stringify_any_mentions(self, message: discord.Message) -> str:
        """
        Converts mentions to text
        """
        content = message.content
        mentions = message.mentions + message.role_mentions + message.channel_mentions

        if not mentions:
            return content

        for mentioned in mentions:
            if mentioned in message.channel_mentions:
                content = content.replace(mentioned.mention, f'#{mentioned.name}')
            elif mentioned in message.role_mentions:
                content = content.replace(mentioned.mention, f'@{mentioned.name}')
            else:
                content = content.replace(mentioned.mention, f'@{mentioned.display_name}')

        return content

    @commands.group(name="aiemote", alias=["ai_emote"])
    @checks.admin_or_permissions(manage_guild=True)
    async def aiemote(self, _):
        """ Totally not glorified sentiment analysis™

            Picks a reaction for a message using ChatGPT

            To get started, please add a channel to the whitelist with:
            `[p]aiemote allow <#channel>`
        """
        pass

    @aiemote.command(name="whitelist")
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

    @commands.group(name="aiemoteadmin", alias=["ai_emote_admin"])
    @checks.is_owner()
    async def aiemote_admin(self, _):
        """ Owner only commands for aiemote
        """
        pass

    @aiemote_admin.command(name="instruction", aliases=["extra_instruction", "extra"])
    @checks.is_owner()
    async def set_extra_instruction(self, ctx: commands.Context, *, instruction: Optional[str]):
        """ Add additonal instruction for the OpenAI when picking an emoji

            *Arguments*
            - `<instruction>` The extra instruction to use
        """
        if not instruction:
            await self.config.extra_instruction.set("")
        else:
            await self.config.extra_instruction.set(instruction)
        return await ctx.tick()

    @aiemote_admin.command(name="add")
    @checks.is_owner()
    async def add_global_emoji(self, ctx: commands.Context, emoji: discord.Emoji, *, description: str):
        """ Add a emoji to the global list

            *Arguments*
            - `<emoji>` The emoji to add
            - `<description>` A description of the emoji to be used by OpenAI
        """
        emojis = await self.config.global_emojis()
        for item in emojis:
            if item["emoji"] == str(emoji):
                return await ctx.send("Emoji already in list")
        emojis.append({
            "description": description,
            "emoji": str(emoji)
        })
        await self.config.global_emojis.set(emojis)
        return await ctx.tick()

    @aiemote_admin.command(name="remove")
    @checks.is_owner()
    async def remove_global_emoji(self, ctx: commands.Context, emoji: discord.Emoji):
        """ Remove a emoji from the global list

            *Arguments*
            - `<emoji>` The emoji to remove
        """
        emojis = await self.config.global_emojis()
        index = -1
        for item in emojis:
            if item["emoji"] == str(emoji):
                index = emojis.index(item)
        if index == -1:
            return await ctx.send("Emoji not in list")
        del emojis[index]
        await self.config.global_emojis.set(emojis)
        return await ctx.tick()

    @aiemote_admin.command(name="config", aliases=["settings", "list", "conf"])
    @checks.is_owner()
    async def list_all_emoji(self, ctx: commands.Context):
        """ List all emojis in the global list (and current server list)
        """
        emojis = await self.config.global_emojis()
        globalembed = discord.Embed(title="Global Emojis", color=await ctx.embed_color())
        if len(emojis) == 0:
            globalembed.description = "None"
        for item in emojis:
            partial_emoji = discord.PartialEmoji.from_str(item["emoji"])
            emoji = str(partial_emoji)
            globalembed.add_field(name=emoji, value=item["description"], inline=False)
        emojis = await self.config.guild(ctx.guild).server_emojis()
        serverembed = discord.Embed(title="Current Server-specific Emojis", color=await ctx.embed_color())
        if len(emojis) == 0:
            serverembed.description = "None"
        for item in emojis:
            partial_emoji = discord.PartialEmoji.from_str(item["emoji"])
            emoji = str(partial_emoji)
            globalembed.add_field(name=emoji, value=item["description"])
        settingsembed = discord.Embed(title="Global Settings", color=await ctx.embed_color())
        settingsembed.add_field(name="Percent Chance", value=f"{self.percent}%", inline=False)
        settingsembed.add_field(name="Additonal Instruction", value=await self.config.extra_instruction() or "None", inline=False)
        await ctx.send(embed=settingsembed)
        await ctx.send(embed=globalembed)
        await ctx.send(embed=serverembed)

    @aiemote_admin.command(name="sadd")
    @checks.is_owner()
    async def add_server_emoji(self, ctx: commands.Context, emoji: discord.Emoji, *, description: str):
        """ Add a emoji to this current server list

            *Arguments*
            - `<emoji>` The emoji to add
            - `<description>` A description of the emoji to be used by OpenAI
        """
        emojis = await self.config.guild(ctx.guild).server_emojis()
        for item in emojis:
            if item["emoji"] == str(emoji):
                return await ctx.send("Emoji already in list")
        emojis.append({
            "description": description,
            "emoji": str(emoji)
        })
        await self.config.guild(ctx.guild).server_emojis.set(emojis)
        return await ctx.tick()

    @aiemote_admin.command(name="sremove")
    @checks.is_owner()
    async def remove_server_emoji(self, ctx: commands.Context, emoji: discord.Emoji):
        """ Remove a emoji from this current server list

            *Arguments*
            - `<emoji>` The emoji to remove
        """
        emojis = await self.config.guild(ctx.guild).server_emojis()
        index = -1
        for item in emojis:
            if item["emoji"] == str(emoji):
                index = emojis.index(item)
        if index == -1:
            return await ctx.send("Emoji not in list")
        del emojis[index]
        await self.config.guild(ctx.guild).server_emojis.set(emojis)
        return await ctx.tick()

    @aiemote_admin.command(name="percent")
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
