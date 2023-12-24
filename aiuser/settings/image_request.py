import json

import discord
from redbot.core import checks, commands

from aiuser.abc import MixinMeta, aiuser
from aiuser.common.constants import (
    DEFAULT_IMAGE_REQUEST_TRIGGER_SECOND_PERSON_WORDS,
    DEFAULT_IMAGE_REQUEST_TRIGGER_WORDS)


class ImageRequestSettings(MixinMeta):
    @aiuser.group()
    @checks.is_owner()
    async def imagerequest(self, _):
        """
        Generate self-portrait images based on user request (on trigger words / LLM decision)

        See [here](https://github.com/zhaobenny/bz-cogs/tree/main/aiuser#image-requests-%EF%B8%8F)

        (All subcommands are per server)
        """
        pass

    @imagerequest.command(name="preprompt")
    async def image_request_preprompt(self, ctx: commands.Context, *, preprompt: str):
        """This text will always be sent as part of the prompt in Stable Diffusion requests

        (Set LORAs here if supported eg. `<lora: name: weight>`)

        """
        await self.config.guild(ctx.guild).image_requests_preprompt.set(preprompt)
        embed = discord.Embed(
            title=" Stable Diffusion preprompt now set to:",
            description=f"{preprompt}",
            color=await ctx.embed_color(),
        )
        return await ctx.send(embed=embed)

    @imagerequest.command(name="subject")
    async def image_request_subject(self, ctx: commands.Context, *, subject: str):
        """
        The subject in Stable Diffusion requests (needed to better hint SD prompt generation by LLM)

        If the subject is well known in the SD model, use it here eg. `katsuragi misato`
        Else use a generic subject eg. `man` or `woman`
        """
        await self.config.guild(ctx.guild).image_requests_subject.set(subject)
        embed = discord.Embed(
            title=" Stable Diffusion subject now set to:",
            description=f"{subject}",
            color=await ctx.embed_color(),
        )
        return await ctx.send(embed=embed)

    @imagerequest.command(name="toggle")
    async def image_request_toggle(self, ctx: commands.Context):
        """Toggle requests to endpoint"""
        if await self.config.guild(ctx.guild).image_requests_endpoint() == None:
            return await ctx.send(
                ":warning: Please set a Stable Diffusion endpoint first!"
            )
        value = not (await self.config.guild(ctx.guild).image_requests())
        await self.config.guild(ctx.guild).image_requests.set(value)
        embed = discord.Embed(
            title="Stable Diffusion requests now set to:",
            description=f"{value}",
            color=await ctx.embed_color(),
        )
        return await ctx.send(embed=embed)

    @imagerequest.command(name="endpoint")
    async def image_request_endpoint(self, ctx: commands.Context, url: str):
        """Set compatible image generation endpoint (eg. for local A1111 include `/sdapi/v1/txt2img`)"""
        if not url.endswith("/"):
            url += "/"
        await self.config.guild(ctx.guild).image_requests_endpoint.set(url)
        embed = discord.Embed(
            title="Image generation endpoint now set to:",
            description=f"{url}",
            color=await ctx.embed_color(),
        )
        return await ctx.send(embed=embed)

    @imagerequest.command(name="reduce_calls")
    async def image_request_reduce_calls(self, ctx: commands.Context):
        """Toggle reduced LLM calls mode (mainly for trial OpenAI keys)

        :warning: Will trigger image generation based ONLY on keywords instead of checking with the LLM
        """
        value = not (
            await self.config.guild(ctx.guild).image_requests_reduced_llm_calls()
        )
        await self.config.guild(ctx.guild).image_requests_reduced_llm_calls.set(value)
        embed = discord.Embed(
            title="Reduced LLM calls for image requests now set to:",
            description=f"{value}",
            color=await ctx.embed_color(),
        )
        return await ctx.send(embed=embed)

    @imagerequest.command(name="parameters")
    async def image_request_parameters(self, ctx: commands.Context, *, json_block: str):
        """Set compatible parameters (depends on interface, eg. see [here](https://github.com/AUTOMATIC1111/stable-diffusion-webui/wiki/API) for A1111)

        Example command:
        `[p]aiuser imagerequest parameters ```{"sampler_name": "Euler a", "steps": 20}``` `
        """

        if json_block in ["reset", "clear"]:
            await self.config.guild(ctx.guild).image_requests_parameters.set(None)
            return await ctx.send("Parameters reset to default")

        embed = discord.Embed(title="Custom Parameters", color=await ctx.embed_color())
        parameters = await self.config.guild(ctx.guild).image_requests_parameters()
        data = {} if parameters is None else json.loads(parameters)

        if json_block not in ["show", "list"]:
            if not json_block.startswith("```"):
                return await ctx.send(
                    ":warning: Please use a code block (`` eg. ```json ``)"
                )

            json_block = json_block.replace("```json", "").replace("```", "")

            try:
                data = json.loads(json_block)
            except json.JSONDecodeError:
                return await ctx.channel.send(":warning: Invalid JSON format!")

            if "prompt" in data.keys():
                return await ctx.send(
                    f':warning: Invalid JSON! Please remove "prompt" key from your JSON.'
                )

            await self.config.guild(ctx.guild).image_requests_parameters.set(
                json.dumps(data)
            )

        if not data:
            embed.description = "No custom parameters set."
        else:
            embed.add_field(
                name=":warning: Warning :warning:",
                value="No checks were done to see if parameters were compatible\n----------------------------------------",
                inline=False,
            )
            for key, value in data.items():
                embed.add_field(
                    name=key, value=f"```{json.dumps(value, indent=4)}```", inline=False
                )

        await ctx.send(embed=embed)

    @imagerequest.command(name="config")
    async def image_request_config(self, ctx: commands.Context):
        """Show current settings"""
        config = await self.config.guild(ctx.guild).get_raw()
        embeds = []

        embed = discord.Embed(
            title="Image Request Settings", color=await ctx.embed_color()
        )
        embed.add_field(
            name="Enabled", value=f"`{config['image_requests']}`", inline=True)
        embed.add_field(
            name="Reduced LLM calls",
            value=f"`{config['image_requests_reduced_llm_calls']}`",
            inline=True,
        )
        embed.add_field(
            name="Image Generation Endpoint",
            value=f"{config['image_requests_endpoint']}",
            inline=False,
        )
        embed.add_field(
            name="Default prompt added",
            value=f"`{config['image_requests_preprompt']}`",
            inline=False,
        )
        embed.add_field(
            name="Subject to replace second person",
            value=f"`{config['image_requests_subject']}`",
        )

        embeds.append(embed)

        parameters = config["image_requests_parameters"]
        if parameters is not None:
            parameters = json.loads(parameters)
            parameters_embed = discord.Embed(
                title="Custom Parameters to Endpoint", color=await ctx.embed_color()
            )
            for key, value in parameters.items():
                parameters_embed.add_field(
                    name=key, value=f"```{json.dumps(value, indent=4)}```", inline=False
                )

            embeds.append(parameters_embed)

        for embed in embeds:
            await ctx.send(embed=embed)

    @imagerequest.group(name="trigger")
    async def imagerequest_trigger(self, _):
        """Set trigger words to detect image requests"""
        pass

    @imagerequest_trigger.command(name="add")
    async def imagerequest_trigger_add(self, ctx: commands.Context, *, word: str):
        """Add a word to the trigger words list"""
        words = await self.config.guild(ctx.guild).image_requests_trigger_words()
        if word in words:
            return await ctx.send("That word is already in the list")
        words.append(word)
        await self.config.guild(ctx.guild).image_requests_trigger_words.set(words)
        return await self.show_trigger_words(ctx, discord.Embed(
            title="The trigger words are now:",
            color=await ctx.embed_color()))

    @imagerequest_trigger.command(name="remove")
    async def imagerequest_trigger_remove(self, ctx: commands.Context, *, word: str):
        """Remove a word from the trigger words list"""
        words = await self.config.guild(ctx.guild).image_requests_trigger_words()
        if word not in words:
            return await ctx.send("That word is not in the list")
        words.remove(word)
        await self.config.guild(ctx.guild).image_requests_trigger_words.set(words)
        return await self.show_trigger_words(ctx, discord.Embed(
            title="The trigger words are now:",
            color=await ctx.embed_color()))

    @imagerequest_trigger.command(name="list", aliases=["show"])
    async def imagerequest_trigger_list(self, ctx: commands.Context):
        """Show the trigger words list"""
        return await self.show_trigger_words(ctx, discord.Embed(
            title="Trigger words for image requests",
            color=await ctx.embed_color()))

    @imagerequest_trigger.command(name="clear")
    async def imagerequest_trigger_clear(self, ctx: commands.Context):
        """Clear the trigger words list to default"""
        await self.config.guild(ctx.guild).image_requests_trigger_words.set(DEFAULT_IMAGE_REQUEST_TRIGGER_WORDS)
        return await ctx.send("The trigger words list has been reset.")

    async def show_trigger_words(self, ctx: commands.Context, embed: discord.Embed):
        words = await self.config.guild(ctx.guild).image_requests_trigger_words()
        if words:
            embed.description = ", ".join(words)
        else:
            embed.description = "No trigger words set."
        return await ctx.send(embed=embed)

    @imagerequest_trigger.command(name="sadd", aliases=["addsecond"])
    async def imagerequest_trigger_add_second(self, ctx: commands.Context, *, word: str):
        """Add a word to the second person words list (to replace with subject) """
        words = await self.config.guild(ctx.guild).image_requests_second_person_trigger_words()
        if word in words:
            return await ctx.send("That word is already in the list")
        words.append(word)
        await self.config.guild(ctx.guild).image_requests_second_person_trigger_words.set(words)
        return await self.show_trigger_second_words(ctx, discord.Embed(
            title="The second person words are now:",
            color=await ctx.embed_color()))

    @imagerequest_trigger.command(name="sremove", aliases=["removesecond"])
    async def imagerequest_trigger_remove_second(self, ctx: commands.Context, *, word: str):
        """Remove a word from the second person words list"""
        words = await self.config.guild(ctx.guild).image_requests_second_person_trigger_words()
        if word not in words:
            return await ctx.send("That word is not in the list")
        words.remove(word)
        await self.config.guild(ctx.guild).image_requests_second_person_trigger_words.set(words)
        return await self.show_trigger_second_words(ctx, discord.Embed(
            title="The second person words are now:",
            color=await ctx.embed_color()))

    @imagerequest_trigger.command(name="slist", aliases=["showsecond", "sshow"])
    async def imagerequest_trigger_list_second(self, ctx: commands.Context):
        """Show the second person words list"""
        return await self.show_trigger_second_words(ctx, discord.Embed(
            title="Second person words for image requests",
            color=await ctx.embed_color()))

    @imagerequest_trigger.command(name="sclear", aliases=["clearsecond"])
    async def imagerequest_trigger_clear_second(self, ctx: commands.Context):
        """Clear the second person words list to default"""
        await self.config.guild(ctx.guild).image_requests_second_person_trigger_words.set(DEFAULT_IMAGE_REQUEST_TRIGGER_SECOND_PERSON_WORDS)
        return await ctx.send("The second person words list has been reset.")

    async def show_trigger_second_words(self, ctx: commands.Context, embed: discord.Embed):
        words = await self.config.guild(ctx.guild).image_requests_second_person_trigger_words()
        if words:
            embed.description = ", ".join(words)
        else:
            embed.description = "No second person words set."
        return await ctx.send(embed=embed)
