import json

import discord
from redbot.core import checks, commands

from aiuser.abc import MixinMeta, aiuser


class StableDiffusionSettings(MixinMeta):
    @aiuser.group()
    @checks.is_owner()
    async def stablediffusion(self, _):
        """
            Settings to generate images using stable-diffusion-webui (A1111) when requested to (based on rudimentary checks / OpenAI decision)

            :warning: Trial OpenAI keys are not recommended! :warning:

            (All subcommands are per server)
        """
        pass


    @stablediffusion.command(name="preprompt")
    async def stable_diffusion_preprompt(self, ctx: commands.Context, *, preprompt: str):
        """ This text will always be sent as part of the prompt in stable-diffusion-webui requests

            Set LORAs here eg. `<lora: name: weight>`

        """
        await self.config.guild(ctx.guild).SD_preprompt.set(preprompt)
        embed = discord.Embed(
            title=" stable-diffusion-webui preprompt now set to:",
            description=f"{preprompt}",
            color=await ctx.embed_color())
        return await ctx.send(embed=embed)

    @stablediffusion.command(name="subject")
    async def stable_diffusion_subject(self, ctx: commands.Context, *, subject: str):
        """
            The subject in stable-diffusion-webui requests (needed to better hint SD prompt generation by OpenAI)

            If the subject is well known in the SD model, use it here eg. `katsuragi misato`
            Else use a generic subject eg. `man` or `woman`
        """
        await self.config.guild(ctx.guild).SD_subject.set(subject)
        embed = discord.Embed(
            title=" stable-diffusion-webui subject now set to:",
            description=f"{subject}",
            color=await ctx.embed_color())
        return await ctx.send(embed=embed)

    @stablediffusion.command(name="toggle")
    async def stable_diffusion_toggle(self, ctx: commands.Context):
        """ Toggle stable-diffusion-webui requests """
        if await self.config.guild(ctx.guild).SD_endpoint() == None:
            return await ctx.send(":warning: Please set a stable-diffusion-webui endpoint first!")
        value = not (await self.config.guild(ctx.guild).SD_requests())
        await self.config.guild(ctx.guild).SD_requests.set(value)
        if await self.config.custom_openai_endpoint() != None:
            return await ctx.send(":warning: Can not enable stable-diffusion-webui requests when using a custom OpenAI endpoint!")
        embed = discord.Embed(
            title="Stable Diffusion requests now set to:",
            description=f"{value}",
            color=await ctx.embed_color())
        return await ctx.send(embed=embed)

    @stablediffusion.command(name="endpoint")
    async def stable_diffusion_endpoint(self, ctx: commands.Context, url: str):
        """ Set stable-diffusion-webui endpoint """
        await self.config.guild(ctx.guild).SD_endpoint.set(url)
        embed = discord.Embed(
            title="Stable Diffusion url now set to:",
            description=f"{url}",
            color=await ctx.embed_color())
        return await ctx.send(embed=embed)

    @stablediffusion.command(name="parameters")
    async def stable_diffusion_parameters(self, ctx: commands.Context, *, json_block: str):
        """ Set stable-diffusion-webui parameters

            Example command:
            `[p]aiuser sd parameters ```{"sampler_name": "Euler a", "steps": 20}``` `

            See [here](https://github.com/AUTOMATIC1111/stable-diffusion-webui/wiki/API)
        """

        if json_block in ['reset', 'clear']:
            await self.config.guild(ctx.guild).SD_parameters.set(None)
            return await ctx.send("Parameters reset to default")

        embed = discord.Embed(title="Custom Parameters", color=await ctx.embed_color())
        parameters = await self.config.guild(ctx.guild).SD_parameters()
        data = {} if parameters is None else json.loads(parameters)

        if json_block not in ['show', 'list']:
            if not json_block.startswith("```"):
                return await ctx.send(":warning: Please use a code block (`` eg. ```json ``)")

            json_block = json_block.replace("```json", "").replace("```", "")

            try:
                data = json.loads(json_block)
            except json.JSONDecodeError:
                return await ctx.channel.send(":warning: Invalid JSON format!")

            if "prompt" in data.keys():
                return await ctx.send(f":warning: Invalid JSON! Please remove \"prompt\" key from your JSON.")

            await self.config.guild(ctx.guild).SD_parameters.set(json.dumps(data))

        if not data:
            embed.description = "No custom parameters set."
        else:
            embed.add_field(
                name=":warning: Warning :warning:",
                value="No checks were done to see if parameters were compatible\n----------------------------------------",
                inline=False
            )
            for key, value in data.items():
                embed.add_field(name=key, value=f"```{json.dumps(value, indent=4)}```", inline=False)

        await ctx.send(embed=embed)
