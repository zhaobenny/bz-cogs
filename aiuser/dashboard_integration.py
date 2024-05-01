import typing

import discord
from redbot.core import commands
from redbot.core.bot import Red

from aiuser.abc import MixinMeta
from aiuser.common.utilities import is_using_openai_endpoint


def dashboard_page(*args, **kwargs):
    def decorator(func: typing.Callable):
        func.__dashboard_decorator_params__ = (args, kwargs)
        return func
    return decorator


class DashboardIntegration(MixinMeta):
    bot: Red

    @commands.Cog.listener()
    async def on_dashboard_cog_add(self, dashboard_cog: commands.Cog) -> None:
        dashboard_cog.rpc.third_parties_handler.add_third_party(self)

    @dashboard_page(name=None, methods=("GET"), is_owner=True, hidden=True)
    async def show_config(self, **kwargs):
        return {
            "status": 0,
            "web_content": {
                "source": "Not implemented yet.",
            },
        }

    @dashboard_page(name="bot_owner_server_config", description="Bot owner specific configuration for a server", methods=("GET", "POST"), is_owner=True)
    async def bot_owner_server_config(self, guild: discord.Guild, **kwargs):
        import wtforms

        class Form(kwargs["Form"]):
            def __init__(self):
                super().__init__(prefix="bot_owner_server_config_")

            percent = wtforms.FloatField("Server Response Percent",
                                         validators=[
                                             wtforms.validators.InputRequired(),
                                             wtforms.validators.NumberRange(min=0, max=100)
                                         ])
            model: wtforms.SelectFieldBase = wtforms.SelectField(
                "Model", choices=[])
            whitelist = wtforms.SelectMultipleField(
                "Whitelisted Channels", choices=[(channel.id, channel.name) for channel in guild.text_channels])
            reply_to_mentions = wtforms.fields.SelectField(
                "Always respond to mentions/replies", choices=[(True, "True"), (False, "False")])

            submit: wtforms.SubmitField = wtforms.SubmitField("Save Changes")

        form: Form = Form()

        reply_mentions = await self.config.guild(guild).reply_to_mentions_replies()
        form.reply_to_mentions.default = reply_mentions
        form.reply_to_mentions.data = reply_mentions
        form.percent.default = await self.config.guild(guild).reply_percent() * 100
        form.whitelist.default = [str(id) for id in await self.config.guild(guild).channels_whitelist()]

        models_list = await self.openai_client.models.list()
        if is_using_openai_endpoint(self.openai_client):
            models = [
                model.id for model in models_list.data if "gpt" in model.id]
        else:
            models = [model.id for model in models_list.data]

        form.model.default = await self.config.guild(guild).model()
        form.model.choices = [(model, model) for model in models]

        if form.validate_on_submit():
            pecentage = form.percent.data
            model = form.model.data
            new_whitelist = [int(id) for id in form.whitelist.data]
            reply_mentions = form.reply_to_mentions.data
            try:
                await self.config.guild(guild).reply_percent.set(pecentage / 100)
                await self.config.guild(guild).model.set(model)
                await self.config.guild(guild).reply_to_mentions_replies.set(reply_mentions)
                await self.config.guild(guild).channels_whitelist.set(new_whitelist)
                self.channels_whitelist[guild.id] = new_whitelist
            except Exception:
                return {
                    "status": 0,
                    "notifications": [{"message": f"Something went wrong while saving the config!", "category": "error"}],
                }
            return {
                "status": 0,
                "notifications": [{"message": f"Saved config!", "category": "success"}],
                "redirect_url": kwargs["request_url"],
            }

        source = "{{ form|safe }}"

        return {
            "status": 0,
            "web_content": {"source": source, "form": form},
        }
