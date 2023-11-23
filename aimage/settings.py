import discord
from redbot.core import checks, commands
from redbot.core.utils.menus import SimpleMenu

from aimage.abc import MixinMeta
from aimage.constants import AUTO_COMPLETE_SAMPLERS


class Settings(MixinMeta):

    @commands.group(name="aimage")
    @commands.guild_only()
    @checks.bot_has_permissions(embed_links=True, add_reactions=True)
    @checks.admin_or_permissions(manage_guild=True)
    async def aimage(self, _: commands.Context):
        """Manage AI Image cog settings"""
        pass

    @aimage.command(name="config")
    async def config(self, ctx: commands.Context):
        """
        Show the current AI Image config
        """
        guild = ctx.guild
        config = await self.config.guild(guild).get_raw()

        embed = discord.Embed(title="AImage Config", color=await ctx.embed_color())
        embed.add_field(name="Endpoint", value=config["endpoint"])
        embed.add_field(name="NSFW allowed",
                        value=config["nsfw"], inline=False)
        embed.add_field(name="Default negative prompt",
                        value=config["negative_prompt"], inline=False)
        embed.add_field(name="Default sampler",
                        value=config["sampler"], inline=False)
        embed.add_field(name="Default cfg", value=config["cfg"])
        embed.add_field(name="Default sampling_steps",
                        value=config["sampling_steps"])
        blacklist = ", ".join(config["words_blacklist"])
        if len(blacklist) > 1024:
            blacklist = blacklist[:1020] + "..."
        elif not blacklist:
            blacklist = "None"
        embed.add_field(name="Blacklisted words",
                        value=blacklist, inline=False)

        return await ctx.send(embed=embed)

    @aimage.command(name="endpoint")
    async def endpoint(self, ctx: commands.Context, endpoint: str):
        """
        Set the endpoint URL for AI Image (include `/sdapi/v1/`)
        """
        if not endpoint.endswith("/"):
            endpoint += "/"
        await self.config.guild(ctx.guild).endpoint.set(endpoint)
        await ctx.tick()

    @aimage.command(name="nsfw")
    async def nsfw(self, ctx: commands.Context):
        """
        Toggles filtering of NSFW images
        """

        nsfw = await self.config.guild(ctx.guild).nsfw()
        if nsfw:
            await ctx.message.add_reaction("🔄")
            data = await self._fetch_data(ctx.guild, "scripts") or {}
            await ctx.message.remove_reaction("🔄", ctx.me)
            if "censorscript" not in data.get("txt2img", []):
                return await ctx.send(":warning: Compatible censor script is not installed in A1111, install [this.](https://github.com/IOMisaka/sdapi-scripts)")

        await self.config.guild(ctx.guild).nsfw.set(not nsfw)
        await ctx.send(f"NSFW filtering is now {'`disabled`' if not nsfw else '`enabled`'}")

    @aimage.command(name="negative_prompt")
    async def negative_prompt(self, ctx: commands.Context, negative_prompt: str):
        """
        Set the default negative prompt
        """
        await self.config.guild(ctx.guild).negative_prompt.set(negative_prompt)
        await ctx.tick()

    @aimage.command(name="cfg")
    async def cfg(self, ctx: commands.Context, cfg: int):
        """
        Set the default cfg
        """
        await self.config.guild(ctx.guild).cfg.set(cfg)
        await ctx.tick()

    @aimage.command(name="sampling_steps")
    async def sampling_steps(self, ctx: commands.Context, sampling_steps: int):
        """
        Set the default sampling steps
        """
        await self.config.guild(ctx.guild).sampling_steps.set(sampling_steps)
        await ctx.tick()

    @aimage.command(name="sampler")
    async def sampler(self, ctx: commands.Context, sampler: str):
        """
        Set the default sampler
        """
        await ctx.message.add_reaction("🔄")
        data = await self._fetch_data(ctx.guild, "samplers")
        await ctx.message.remove_reaction("🔄", ctx.me)
        if not data:
            samplers = AUTO_COMPLETE_SAMPLERS
        else:
            samplers = [choice["name"] for choice in data]

        if sampler not in samplers:
            return await ctx.send(f":warning: Sampler must be one of: `{', '.join(samplers)}`")

        await self.config.guild(ctx.guild).sampler.set(sampler)
        await ctx.tick()

    @aimage.group(name="blacklist")
    async def blacklist(self, _: commands.Context):
        """
        Manage the blacklist of words that will be rejected in prompts
        """
        pass

    @blacklist.command(name="add")
    async def blacklist_add(self, ctx: commands.Context, *words: str):
        """
        Add words to the blacklist

        (Separate multiple inputs with spaces, and use quotes (\"\") if needed)
        """
        current_words = await self.config.guild(ctx.guild).words_blacklist()
        added = []
        for word in words:
            if word not in current_words:
                added.append(word)
                current_words.append(word)
        if not added:
            return await ctx.send("No words added")
        await self.config.guild(ctx.guild).words_blacklist.set(current_words)
        return await ctx.send(f"Added words `{', '.join(added)}` to the blacklist")

    @blacklist.command(name="remove")
    async def blacklist_remove(self, ctx: commands.Context, *words: str):
        """
        Remove words from the blacklist

        (Separate multiple inputs with spaces, and use quotes (\"\") if needed)
        """
        current_words = await self.config.guild(ctx.guild).words_blacklist()

        removed = []
        for word in words:
            if word in current_words:
                removed.append(word)
                current_words.remove(word)
        if not removed:
            return await ctx.send("No words removed")
        await self.config.guild(ctx.guild).words_blacklist.set(current_words)
        return await ctx.send(f"Removed words `{', '.join(removed)}` from blacklist")

    @blacklist.command(name="list", aliases=["show"])
    async def blacklist_list(self, ctx: commands.Context):
        """
        List all words in the blacklist
        """
        current_words = await self.config.guild(ctx.guild).words_blacklist()

        if not current_words:
            return await ctx.send("No words in blacklist")

        pages = []

        for i in range(0, len(current_words), 10):
            embed = discord.Embed(title="Blacklisted words",
                                  color=await ctx.embed_color())
            embed.description = "\n".join(current_words[i:i+10])
            pages.append(embed)

        if len(pages) == 1:
            return await ctx.send(embed=pages[0])

        for i, page in enumerate(pages):
            page.set_footer(text=f"Page {i+1} of {len(pages)}")

        await SimpleMenu(pages).start(ctx)

    @blacklist.command(name="clear")
    async def blacklist_clear(self, ctx: commands.Context):
        """
        Clear the blacklist to nothing!
        """
        await self.config.guild(ctx.guild).words_blacklist.set([])
        await ctx.tick()

    @commands.group(name="aimageowner")
    @checks.bot_has_permissions(embed_links=True, add_reactions=True)
    @checks.is_owner()
    async def aimageowner(self, _: commands.Context):
        """Manage AI Image owner settings"""
        pass

    @aimageowner.command(name="config")
    async def config_owner(self, ctx: commands.Context):
        """
        Show the current AI Image config
        """
        config = await self.config.get_raw()

        embed = discord.Embed(title="Global AImage Config", color=await ctx.embed_color())
        embed.add_field(name="Endpoint", value=config["endpoint"])
        embed.add_field(name="NSFW allowed",
                        value=config["nsfw"], inline=False)
        blacklist = ", ".join(config["words_blacklist"])
        if len(blacklist) > 1024:
            blacklist = blacklist[:1020] + "..."
        elif not blacklist:
            blacklist = "None"
        embed.add_field(name="Blacklisted words",
                        value=blacklist, inline=False)

        return await ctx.send(embed=embed)

    @aimageowner.command(name="endpoint")
    async def endpoint_owner(self, ctx: commands.Context, endpoint: str):
        """
        Set a global endpoint URL for AI Image (include `/sdapi/v1/`)

        Will be used if no guild endpoint is set
        """
        await self.config.endpoint.set(endpoint)
        await ctx.tick()

    @aimageowner.command(name="nsfw")
    async def nsfw_owner(self, ctx: commands.Context):
        """
        Toggles filtering of NSFW images for global endpoint
        """

        nsfw = await self.config.nsfw()
        if nsfw:
            await ctx.message.add_reaction("🔄")
            endpoint = await self.config.endpoint()
            async with self.session.get(endpoint + "scripts") as res:
                if res.status != 200:
                    await ctx.message.remove_reaction("🔄", ctx.me)
                    return await ctx.send(":warning: Couldn't request Stable Diffusion endpoint!")
                res = await res.json()
                if "censorscript" not in res.get("txt2img", []):
                    await ctx.message.remove_reaction("🔄", ctx.me)
                    return await ctx.send(":warning: Compatible censor script is not installed on A1111, install [this.](https://github.com/IOMisaka/sdapi-scripts)")
            await ctx.message.remove_reaction("🔄", ctx.me)
        await self.config.nsfw.set(not nsfw)
        await ctx.send(f"NSFW filtering is now {'`disabled`' if not nsfw else '`enabled`'}")

    @aimageowner.group(name="blacklist")
    async def blacklist_owner(self, _: commands.Context):
        """
        Manage the blacklist of words that will be rejected in prompts when using the global endpoint
        """
        pass

    @blacklist_owner.command(name="add")
    async def blacklist_add_owner(self, ctx: commands.Context, *words: str):
        """
        Add words to the global blacklist

        (Separate multiple inputs with spaces, and use quotes (\"\") if needed)
        """
        current_words = await self.config.words_blacklist()
        added = []
        for word in words:
            if word not in current_words:
                added.append(word)
                current_words.append(word)
        if not added:
            return await ctx.send("No words added")

        await self.config.words_blacklist.set(current_words)
        return await ctx.send(f"Added words `{', '.join(added)}` to the blacklist")

    @blacklist_owner.command(name="remove")
    async def blacklist_remove_owner(self, ctx: commands.Context, *words: str):
        """
        Remove words from the global blacklist

        (Separate multiple inputs with spaces, and use quotes (\"\") if needed)
        """
        current_words = await self.config.words_blacklist()
        removed = []
        for word in words:
            if word in current_words:
                removed.append(word)
                current_words.remove(word)
        if not removed:
            return await ctx.send("No words removed")

        await self.config.words_blacklist.set(current_words)
        await ctx.send(f"Removed words `{words}` to global blacklist")

    @blacklist_owner.command(name="list", aliases=["show"])
    async def blacklist_list(self, ctx: commands.Context):
        """
        List all words in the blacklist
        """
        current_words = await self.config.words_blacklist()

        if not current_words:
            return await ctx.send("No words in global blacklist")

        pages = []

        for i in range(0, len(current_words), 10):
            embed = discord.Embed(title="Blacklisted words for global endpoint",
                                  color=await ctx.embed_color())
            embed.description = "\n".join(current_words[i:i+10])
            pages.append(embed)

        if len(pages) == 1:
            return await ctx.send(embed=pages[0])

        for i, page in enumerate(pages):
            page.set_footer(text=f"Page {i+1} of {len(pages)}")

    @blacklist_owner.command(name="clear")
    async def blacklist_clear_owner(self, ctx: commands.Context):
        """
        Clear the global blacklist to nothing!
        """
        await self.config.words_blacklist.set([])
        await ctx.tick()

    @aimageowner.command()
    @checks.bot_in_a_guild()
    async def forcesync(self, ctx: commands.Context):
        """
        Force sync slash commands (mainly for development usage)
        """
        self.bot.tree.copy_global_to(
            guild=discord.Object(id=ctx.guild.id))
        synced = await ctx.bot.tree.sync(guild=ctx.guild)
        await ctx.send(f"Force synced {len(synced)} commands")
