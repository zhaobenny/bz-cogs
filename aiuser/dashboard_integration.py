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
    async def main(self, **kwargs):
        return {
            "status": 0,
            "web_content": {
                "source": "Not implemented yet.",
            },
        }

    @dashboard_page(name="consent", description="Opt in / out into this cog using your messages", methods=("GET", "POST"))
    async def opt_consent(self, user: discord.User, **kwargs):
        import wtforms

        class Form(kwargs["Form"]):
            def __init__(self):
                super().__init__(prefix="consent_")
            accept: wtforms.SubmitField = wtforms.SubmitField("Yes, I consent.", render_kw={
                "class": "btn mb-0 btn-success btn-md w-50 my-4 mb-2"})
            reject: wtforms.SubmitField = wtforms.SubmitField("No, I do NOT consent.", render_kw={
                                                              "class": "btn mb-0 btn-danger btn-md w-50 my-4 mb-2"})

        form = Form()
        whitelist = await self.config.optin()
        blacklist = await self.config.optout()

        if user.id in whitelist:
            whitelist_text = "opted in"
            form.accept.render_kw["disabled"] = True
            form.reject.render_kw["disabled"] = False
        elif user.id in blacklist:
            whitelist_text = "opted out"
            form.accept.render_kw["disabled"] = False
            form.reject.render_kw["disabled"] = True
        else:
            whitelist_text = "not opted in or out"
            form.accept.render_kw["disabled"] = False
            form.reject.render_kw["disabled"] = False

        source = """<div class="container">"""
        source += f"""<p>Hello <b>{user.name}</b>. You are currently {whitelist_text}. Change your preference regarding data collection below. </p>"""
        source += """
                <p>Do you consent to sending your Discord text/images messages on <b>ALL</b> servers with this bot <i>AND</i>  this cog enabled, to OpenAI or a third-party endpoint? <br> This will allow the bot to reply to your messages or use your messages.</p>
                {{ form|safe }}
            </div>
        """

        if form.validate_on_submit():
            try:
                if form.accept.data:
                    await self.config.optin.set(whitelist + [user.id])
                    await self.config.optout.set([id for id in blacklist if id != user.id])
                elif form.reject.data:
                    await self.config.optout.set(blacklist + [user.id])
                    await self.config.optin.set([id for id in whitelist if id != user.id])
            except Exception:
                return {
                    "status": 1,
                    "notifications": [{"message": f"Something went wrong while saving changes!", "category": "error"}],
                }
            return {
                "status": 0,
                "notifications": [{"message": f"Saved changes!", "category": "success"}],
                "redirect_url": kwargs["request_url"],
            }

        return {
            "status": 0,
            "web_content": {"source": source, "form": form},
        }

    @dashboard_page(name="bot_owner_per_server_config", description="Per server settings specific to bot owners", methods=("GET", "POST"), is_owner=True)
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
                "Large Language Model", choices=[], validators=[
                    wtforms.validators.InputRequired()])
            whitelist = wtforms.SelectMultipleField(
                "Whitelisted Channels", choices=[(channel.id, channel.name) for channel in guild.text_channels])
            messages_backread = wtforms.IntegerField("History Backread (number of messages to use as context, bigger number = more cost)",
                                                     validators=[
                                                         wtforms.validators.InputRequired(),
                                                         wtforms.validators.NumberRange(min=0)
                                                     ])
            messages_backread_seconds = wtforms.IntegerField("History Time Dropoff in Seconds (set max time messages can be apart before no more can be added)",
                                                             validators=[
                                                                 wtforms.validators.InputRequired(),
                                                                 wtforms.validators.NumberRange(min=0)
                                                             ])
            reply_to_mentions = wtforms.fields.SelectField(
                "Always respond to mentions/replies", choices=[(True, "True"), (False, "False")])

            submit: wtforms.SubmitField = wtforms.SubmitField("Save Changes")

        form: Form = Form()

        reply_mentions = await self.config.guild(guild).reply_to_mentions_replies()
        form.reply_to_mentions.default = reply_mentions
        form.reply_to_mentions.data = reply_mentions
        form.percent.default = await self.config.guild(guild).reply_percent() * 100
        form.messages_backread.default = await self.config.guild(guild).messages_backread()
        form.messages_backread_seconds.default = await self.config.guild(guild).messages_backread_seconds()
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
            messages_backread = form.messages_backread.data
            try:
                await self.config.guild(guild).reply_percent.set(pecentage / 100)
                await self.config.guild(guild).model.set(model)
                await self.config.guild(guild).reply_to_mentions_replies.set(reply_mentions)
                await self.config.guild(guild).channels_whitelist.set(new_whitelist)
                await self.config.guild(guild).messages_backread.set(messages_backread)
                self.channels_whitelist[guild.id] = new_whitelist
            except Exception:
                return {
                    "status": 1,
                    "notifications": [{"message": f"Something went wrong while saving the config!", "category": "error"}],
                }
            return {
                "status": 0,
                "notifications": [{"message": f"Saved config!", "category": "success"}],
                "redirect_url": kwargs["request_url"],
            }

        source = """<p>Only a subset of available settings. See Discord cog commands for all available settings.</p>{{ form|safe }}"""

        return {
            "status": 0,
            "web_content": {"source": source, "form": form},
        }
