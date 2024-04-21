import discord
from redbot.core import checks, commands
from redbot.core.utils.menus import SimpleMenu

from aimage.abc import MixinMeta
from aimage.constants import AUTO_COMPLETE_SAMPLERS
from aimage.helpers import get_auth


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
        embed.add_field(name="Endpoint", value=f"{config['endpoint']}", inline=False)
        embed.add_field(name="Default Negative Prompt", value=f"`{config['negative_prompt']}`", inline=False)
        embed.add_field(name="Default Checkpoint", value=f"`{config['checkpoint']}`")
        embed.add_field(name="Default VAE", value=f"`{config['vae']}`")
        embed.add_field(name="Default Sampler", value=f"`{config['sampler']}`")
        embed.add_field(name="Default CFG", value=f"`{config['cfg']}`")
        embed.add_field(name="Default Sampling Steps", value=f"`{config['sampling_steps']}`")
        embed.add_field(name="Default Size", value=f"`{config['width']}x{config['height']}`")
        embed.add_field(name="NSFW allowed", value=f"`{config['nsfw']}`")
        embed.add_field(name="Use ADetailer", value=f"`{config['adetailer']}`")
        embed.add_field(name="Use Tiled VAE", value=f"`{config['tiledvae']}`")
        embed.add_field(name="Max img2img size", value=f"`{config['max_img2img']}`²")

        blacklist = ", ".join(config["words_blacklist"])
        if len(blacklist) > 1024:
            blacklist = blacklist[:1020] + "..."
        elif not blacklist:
            blacklist = "None"
        embed.add_field(name="Blacklisted words",
                        value=f"`{blacklist}`", inline=False)

        return await ctx.send(embed=embed)

    @aimage.command(name="endpoint")
    async def endpoint(self, ctx: commands.Context, endpoint: str):
        """
        Set the endpoint URL for AI Image (include `/sdapi/v1/`)
        """
        if not endpoint:
            endpoint = None
        elif not endpoint.endswith("/"):
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
                return await ctx.send(":warning: Compatible censor script is not installed in A1111, install [this.](<https://github.com/IOMisaka/sdapi-scripts>)")

        await self.config.guild(ctx.guild).nsfw.set(not nsfw)
        await ctx.send(f"NSFW filtering is now {'`disabled`' if not nsfw else '`enabled`'}")

    @aimage.command(name="negative_prompt")
    async def negative_prompt(self, ctx: commands.Context, *, negative_prompt: str):
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
    async def sampler(self, ctx: commands.Context, *, sampler: str):
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

    @aimage.command(name="width")
    async def width(self, ctx: commands.Context, width: int):
        """
        Set the default width
        """
        if width < 256 or width > 1536:
            return await ctx.send("Value must range between 256 and 1536.")
        await self.config.guild(ctx.guild).width.set(width)
        await ctx.tick()

    @aimage.command(name="height")
    async def height(self, ctx: commands.Context, height: int):
        """
        Set the default height
        """
        if height < 256 or height > 1536:
            return await ctx.send("Value must range between 256 and 1536.")
        await self.config.guild(ctx.guild).height.set(height)
        await ctx.tick()

    @aimage.command(name="max_img2img")
    async def max_img2img(self, ctx: commands.Context, resolution: int):
        """
        Set the maximum size (in pixels squared) of img2img and hires upscale.
        Used to prevent out of memory errors. Default is 1536.
        """
        if resolution < 512 or resolution > 4096:
            return await ctx.send("Value must range between 512 and 4096.")
        await self.config.guild(ctx.guild).max_img2img.set(resolution)
        await ctx.tick()

    @aimage.command(name="checkpoint")
    async def checkpoint(self, ctx: commands.Context, *, checkpoint: str):
        """
        Set the default checkpoint used for generating images.
        """
        await ctx.message.add_reaction("🔄")
        data = await self._fetch_data(ctx.guild, "sd-models")
        data = [choice["model_name"] for choice in data]
        await ctx.message.remove_reaction("🔄", ctx.me)
        if checkpoint not in data:
            return await ctx.send(f":warning: Invalid checkpoint. Pick one of these:\n`{', '.join(data)}`")
        await self.config.guild(ctx.guild).checkpoint.set(checkpoint)
        await ctx.tick()

    @aimage.command(name="vae")
    async def vae(self, ctx: commands.Context, *, vae: str):
        """
        Set the default vae used for generating images.
        """
        await ctx.message.add_reaction("🔄")
        data = await self._fetch_data(ctx.guild, "sd-vae")
        data = [choice["model_name"] for choice in data]
        await ctx.message.remove_reaction("🔄", ctx.me)
        if vae not in data:
            return await ctx.send(f":warning: Invalid vae. Pick one of these:\n`{', '.join(data)}`")
        await self.config.guild(ctx.guild).vae.set(vae)
        await ctx.tick()

    @aimage.command(name="auth")
    async def auth(self, ctx: commands.Context, *, auth: str):
        """
        Set the API auth username:password in that format.
        """
        try:
            await ctx.message.delete()
        except:
            pass
        await self.config.guild(ctx.guild).auth.set(auth)
        await ctx.send("✅ Auth set.")

    @aimage.command(name="adetailer")
    async def adetailer(self, ctx: commands.Context):
        """
        Whether to use face adetailer on generated pictures, which improves quality.
        """
        new = not await self.config.guild(ctx.guild).adetailer()
        if new:
            await ctx.message.add_reaction("🔄")
            data = await self._fetch_data(ctx.guild, "scripts") or {}
            await ctx.message.remove_reaction("🔄", ctx.me)
            if "adetailer" not in data.get("txt2img", []):
                return await ctx.send(":warning: The ADetailer script is not installed in A1111, install [this.](<https://github.com/Bing-su/adetailer>)")

        await self.config.guild(ctx.guild).adetailer.set(new)
        await ctx.send(f"ADetailer is now {'`disabled`' if not new else '`enabled`'}")

    @aimage.command(name="tiledvae")
    async def tiledvae(self, ctx: commands.Context):
        """
        Whether to use tiled vae on generated pictures, which is used to prevent out of memory errors.
        """
        new = not await self.config.guild(ctx.guild).tiledvae()
        if new:
            await ctx.message.add_reaction("🔄")
            data = await self._fetch_data(ctx.guild, "scripts") or {}
            await ctx.message.remove_reaction("🔄", ctx.me)
            if "tiled vae" not in data.get("txt2img", []):
                return await ctx.send(":warning: The Tiled VAE script is not installed in A1111, install [this.](<https://github.com/pkuliyi2015/multidiffusion-upscaler-for-automatic1111>)")

        await self.config.guild(ctx.guild).tiledvae.set(new)
        await ctx.send(f"Tiled VAE is now {'`disabled`' if not new else '`enabled`'}")

    @aimage.command(name="aihorde_mode")
    async def aihorde_mode(self, ctx: commands.Context):
        """
        Whether the aihorde fallback, if enabled, should use a generalist model or an anime model.
        """
        new = not await self.config.guild(ctx.guild).aihorde_anime()
        await self.config.guild(ctx.guild).aihorde_anime.set(new)
        await ctx.send(f"aihorde mode is now {'`generalist`' if not new else '`anime`'}")

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

    @aimageowner.command(name="auth")
    async def auth_owner(self, ctx: commands.Context, auth: str):
        """
        Set the API auth username:password in that format.

        Will be used if no guild endpoint is set
        """
        try:
            await ctx.message.delete()
        except:
            pass
        await self.config.auth.set(auth)
        await ctx.send("✅ Auth set.")

    @aimageowner.command(name="nsfw")
    async def nsfw_owner(self, ctx: commands.Context):
        """
        Toggles filtering of NSFW images for global endpoint
        """

        nsfw = await self.config.nsfw()
        if nsfw:
            await ctx.message.add_reaction("🔄")
            endpoint = await self.config.endpoint()
            auth_str = await self.config.auth()
            async with self.session.get(endpoint + "scripts", auth=get_auth(auth_str)) as res:
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

    @aimageowner.command(name="aihorde")
    async def aihorde_owner(self, ctx: commands.Context):
        """
        Whether to use aihorde (a crowdsourced volunteer service) as a fallback for generations.
        Set your AI Horde API key with [p]set api ai-horde api_key,API_KEY
        """
        new = not await self.config.aihorde()
        await self.config.aihorde.set(new)
        await ctx.send(f"aihorde fallback is now {'`disabled`' if not new else '`enabled`'}")

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
    async def blacklist_list_owner(self, ctx: commands.Context):
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
