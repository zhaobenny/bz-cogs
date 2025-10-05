from typing import Optional

import discord
from redbot.core import checks, commands
from redbot.core.utils.menus import SimpleMenu

from aimage.abc import MixinMeta


class Settings(MixinMeta):

    @commands.group(name="aimage")
    @commands.guild_only()
    @checks.bot_has_permissions(embed_links=True, add_reactions=True)
    @checks.admin_or_permissions(manage_guild=True)
    async def aimage(self, _: commands.Context):
        """ Manage AI Image cog settings for this server """
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

        negative_prompt = config["negative_prompt"]
        if len(negative_prompt) > 1000:
            negative_prompt = negative_prompt[:1000] + "..."
        embed.add_field(name="Default Negative Prompt", value=f"`{negative_prompt}`", inline=False)

        embed.add_field(name="Default Checkpoint", value=f"`{config['checkpoint']}`")
        embed.add_field(name="Default VAE", value=f"`{config['vae']}`")
        embed.add_field(name="Default Sampler", value=f"`{config['sampler']}`")
        embed.add_field(name="Default CFG", value=f"`{config['cfg']}`")
        embed.add_field(name="Default Sampling Steps", value=f"`{config['sampling_steps']}`")
        embed.add_field(name="Default Size", value=f"`{config['width']}x{config['height']}`")
        embed.add_field(name="NSFW allowed", value=f"`{config['nsfw']}`")
        embed.add_field(name="NSFW sensitivity", value=f"`{config['nsfw_sensitivity']}`")
        embed.add_field(name="Use ADetailer", value=f"`{config['adetailer']}`")
        embed.add_field(name="Use Tiled VAE", value=f"`{config['tiledvae']}`")
        embed.add_field(name="Max img2img size", value=f"`{config['max_img2img']}`²")

        blacklist = ", ".join(config["words_blacklist"])

        if len(blacklist) > 1000:
            blacklist = blacklist[:1000] + "..."
        elif not blacklist:
            blacklist = "None"
        embed.add_field(name="Blacklisted words",
                        value=f"`{blacklist}`", inline=False)

        return await ctx.send(embed=embed)

    @aimage.command(name="endpoint")
    async def endpoint(self, ctx: commands.Context, endpoint: str):
        """
        Set the endpoint URL for AI Image (eg. `http://localhost:7860/sdapi/v1/`)
        """
        if not endpoint:
            endpoint = None
        elif not endpoint.endswith("/"):
            endpoint += "/"

        if endpoint and not endpoint.endswith("/sdapi/v1/"):
            await ctx.send(f"⚠️ Endpoint URL does not end with `/sdapi/v1/`. Continuing anyways...")

        await self.config.guild(ctx.guild).endpoint.set(endpoint)
        await ctx.send(f"✅ Endpoint set to `{endpoint}`.")

    @aimage.command(name="nsfw")
    async def nsfw(self, ctx: commands.Context):
        """
        Toggles filtering of NSFW images (A1111 only)
        """

        nsfw = await self.config.guild(ctx.guild).nsfw()
        if nsfw:
            await ctx.message.add_reaction("🔄")
            await self._update_autocomplete_cache(ctx)
            data = self.autocomplete_cache[ctx.guild.id].get("scripts") or []
            await ctx.message.remove_reaction("🔄", ctx.me)
            if "censorscript" not in data:
                return await ctx.send(":warning: Compatible censor script is not installed in A1111, install [the updated CensorScript.py](<https://github.com/hollowstrawberry/sd-webui-nsfw-checker>).")

        await self.config.guild(ctx.guild).nsfw.set(not nsfw)
        await ctx.send(f"NSFW filtering is now {'`disabled`' if not nsfw else '`enabled`'}")

    @aimage.command(name="nsfw_sensitivity")
    async def nsfw_sensitivity(self, ctx: commands.Context, value: Optional[float]):
        """
        Views or sets the sensitivity for the nsfw filter (A1111 only)
        Valid values are between -0.2 and 0.2
        """

        if value is None:
            nsfw_sensitivity = await self.config.guild(ctx.guild).nsfw_sensitivity()
            await ctx.send(f"The sensitivity is currently set to `{nsfw_sensitivity:.3f}`")
        elif value < -0.2 or value > 0.2:
            await ctx.send(f"Valid values are between -0.2 and 0.2")
        else:
            await self.config.guild(ctx.guild).nsfw_sensitivity.set(value)
            await ctx.send(f"The sensitivity is currently set to `{value:.3f}`"
                           "\nNote that you need [the updated CensorScript.py](<https://github.com/hollowstrawberry/sd-webui-nsfw-checker>) in your A1111 to use this.")

    @aimage.command(name="nsfw_blurred")
    async def nsfw_blurred(self, ctx: commands.Context):
        """
        Toggles whether images blocked by the nsfw filter should still be shown, but blurred.
        """

        value = not await self.config.guild(ctx.guild).nsfw_blurred()
        await self.config.guild(ctx.guild).nsfw_blurred.set(value)
        await ctx.send(f"Show filtered images is now `{'enabled' if value else 'disabled'}`"
                        "\nNote that you need [the updated CensorScript.py](<https://github.com/hollowstrawberry/sd-webui-nsfw-checker>) in your A1111 to use this.")


    @aimage.command(name="negative_prompt")
    async def negative_prompt(self, ctx: commands.Context, *, negative_prompt: Optional[str]):
        """
        Set the default negative prompt
        """
        if not negative_prompt:
            negative_prompt = ""
        await self.config.guild(ctx.guild).negative_prompt.set(negative_prompt)
        await ctx.tick(message="✅ Default negative prompt updated.")

    @aimage.command(name="cfg")
    async def cfg(self, ctx: commands.Context, cfg: int):
        """
        Set the default cfg
        """
        await self.config.guild(ctx.guild).cfg.set(cfg)
        await ctx.tick(message="✅ Default CFG updated.")

    @aimage.command(name="sampling_steps")
    async def sampling_steps(self, ctx: commands.Context, sampling_steps: int):
        """
        Set the default sampling steps
        """
        await self.config.guild(ctx.guild).sampling_steps.set(sampling_steps)
        await ctx.tick(message="✅ Default sampling steps updated.")

    @aimage.command(name="sampler")
    async def sampler(self, ctx: commands.Context, *, sampler: str):
        """
        Set the default sampler
        """
        await ctx.message.add_reaction("🔄")
        await self._update_autocomplete_cache(ctx)
        samplers = self.autocomplete_cache[ctx.guild.id].get("samplers") or []
        await ctx.message.remove_reaction("🔄", ctx.me)

        if sampler not in samplers:
            return await ctx.send(f":warning: Sampler must be one of: `{', '.join(samplers)}`")

        await self.config.guild(ctx.guild).sampler.set(sampler)
        await ctx.tick(message="✅ Default sampler updated.")

    @aimage.command(name="width")
    async def width(self, ctx: commands.Context, width: int):
        """
        Set the default width
        """
        if width < 256 or width > 1536:
            return await ctx.send("Value must range between 256 and 1536.")
        await self.config.guild(ctx.guild).width.set(width)
        await ctx.tick(message="✅ Default width updated.")

    @aimage.command(name="height")
    async def height(self, ctx: commands.Context, height: int):
        """
        Set the default height
        """
        if height < 256 or height > 1536:
            return await ctx.send("Value must range between 256 and 1536.")
        await self.config.guild(ctx.guild).height.set(height)
        await ctx.tick(message="✅ Default height updated.")

    @aimage.command(name="max_img2img")
    async def max_img2img(self, ctx: commands.Context, resolution: int):
        """
        Set the maximum size (in pixels squared) of img2img and hires upscale.
        Used to prevent out of memory errors. Default is 1536.
        """
        if resolution < 512 or resolution > 4096:
            return await ctx.send("Value must range between 512 and 4096.")
        await self.config.guild(ctx.guild).max_img2img.set(resolution)
        await ctx.tick(message="✅ Maximum img2img size updated.")

    @aimage.command(name="checkpoint", aliases=["model"])
    async def checkpoint(self, ctx: commands.Context, *, checkpoint: str):
        """
        Set the default checkpoint / model used for generating images.
        """
        await ctx.message.add_reaction("🔄")
        await self._update_autocomplete_cache(ctx)
        data = self.autocomplete_cache[ctx.guild.id].get("checkpoints") or []
        await ctx.message.remove_reaction("🔄", ctx.me)
        
        if checkpoint not in data:
            checkpoints = []

            remaining_length = 1900
            for cp in data:
                if len(cp) + 2 <= remaining_length:
                    checkpoints.append(cp)
                    remaining_length -= (len(cp) + 2)
                else:
                    break
            return await ctx.send(f":warning: Invalid checkpoint. Pick one of these:`\n{', '.join(checkpoints)}`")

        await self.config.guild(ctx.guild).checkpoint.set(checkpoint)
        await ctx.tick(message="✅ Default checkpoint updated.")

    @aimage.command(name="vae")
    async def vae(self, ctx: commands.Context, *, vae: str):
        """
        Set the default vae used for generating images.
        """
        await ctx.message.add_reaction("🔄")
        await self._update_autocomplete_cache(ctx)
        data = self.autocomplete_cache[ctx.guild.id].get("vaes") or []
        await ctx.message.remove_reaction("🔄", ctx.me)
        if vae not in data:
            vaes = []

            remaining_length = 1900
            for vae in data:
                if len(vae) + 2 <= remaining_length:
                    vaes.append(vae)
                    remaining_length -= (len(vae) + 2)
                else:
                    break
            return await ctx.send(f":warning: Invalid vae. Pick one of these:\n`{', '.join(vaes)}`")

        await self.config.guild(ctx.guild).vae.set(vae)
        await ctx.tick(message="✅ Default VAE updated.")

    @aimage.command(name="auth")
    async def auth(self, ctx: commands.Context, *, auth: str):
        """
        Sets the account from A1111 host flag `--api-auth` in this format `username:password` 
        """
        try:
            await ctx.message.delete()
        except Exception:
            pass
        await self.config.guild(ctx.guild).auth.set(auth)
        await ctx.send("✅ Auth set.")

    @aimage.command(name="adetailer")
    async def adetailer(self, ctx: commands.Context):
        """
        Whether to use face `adetailer` A1111 extension on generated pictures, which improves quality.
        """
        new = not await self.config.guild(ctx.guild).adetailer()
        if new:
            await ctx.message.add_reaction("🔄")
            await self._update_autocomplete_cache(ctx)
            data = self.autocomplete_cache[ctx.guild.id].get("scripts") or []
            await ctx.message.remove_reaction("🔄", ctx.me)
            if "adetailer" not in data:
                return await ctx.send(":warning: The ADetailer script is not installed in A1111, install [this.](<https://github.com/Bing-su/adetailer>)")

        await self.config.guild(ctx.guild).adetailer.set(new)
        await ctx.send(f"ADetailer is now {'`disabled`' if not new else '`enabled`'}")

    @aimage.command(name="tiledvae")
    async def tiledvae(self, ctx: commands.Context):
        """
        Whether to use tiled vae on generated pictures from A1111 hosts, which is used to prevent out of memory errors.
        """
        new = not await self.config.guild(ctx.guild).tiledvae()
        if new:
            await ctx.message.add_reaction("🔄")
            await self._update_autocomplete_cache(ctx)
            data = self.autocomplete_cache[ctx.guild.id].get("scripts") or []
            await ctx.message.remove_reaction("🔄", ctx.me)
            if "tiled vae" not in data:
                return await ctx.send(":warning: The Tiled VAE script is not installed in A1111, install [this.](<https://github.com/pkuliyi2015/multidiffusion-upscaler-for-automatic1111>)")

        await self.config.guild(ctx.guild).tiledvae.set(new)
        await ctx.send(f"Tiled VAE is now {'`disabled`' if not new else '`enabled`'}")

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
        await ctx.tick(message="✅ Blacklist cleared.")

    @aimage.command()
    @checks.is_owner()
    @checks.bot_in_a_guild()
    async def forcesync(self, ctx: commands.Context):
        """
        Resync slash commands / image generators 

        (Mainly a debug tool)
        """
        await ctx.message.add_reaction("🔄")
        await self._update_autocomplete_cache(ctx)
        self.bot.tree.copy_global_to(
            guild=discord.Object(id=ctx.guild.id))
        synced = await ctx.bot.tree.sync(guild=ctx.guild)
        await ctx.message.remove_reaction("🔄", ctx.me)
        await ctx.send(f"Force synced {len(synced)} commands")
