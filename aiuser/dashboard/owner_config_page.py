import discord
import wtforms

from aiuser.dashboard.decorator import dashboard_page
from aiuser.settings.utilities import get_available_models
from aiuser.types.abc import MixinMeta

@dashboard_page(name="bot_owner_per_server_settings", description="Some bot owner-only settings per server", methods=("GET", "POST"), is_owner=True)
async def bot_owner_server_config(self: MixinMeta, guild: discord.Guild, **kwargs):

    class Form(kwargs["Form"]):
        def __init__(self):
            super().__init__(prefix="bot_owner_server_config_")

        percent = wtforms.FloatField("Server Response Percent",
                                     validators=[
                                         wtforms.validators.InputRequired(),
                                         wtforms.validators.NumberRange(min=0, max=100)
                                     ])
        model: wtforms.SelectFieldBase = wtforms.SelectField(
            "LLM (used as the server-wide response model if no more specific model is set)", choices=[], validators=[
                wtforms.validators.InputRequired()])
        whitelist = wtforms.SelectMultipleField(
            "Whitelisted Channels", choices=[(channel.id, channel.name) for channel in guild.text_channels])
        messages_backread = wtforms.IntegerField("History Backread / Message Context Size (Increases 💵 usage)",
                                                 validators=[
                                                     wtforms.validators.InputRequired(),
                                                     wtforms.validators.NumberRange(min=0)
                                                 ])
        messages_backread_seconds = wtforms.IntegerField("History / Context Cutoff Time in Seconds (If messages are spaced further apart, history stops accumulating)",
                                                         description="Time in seconds.",
                                                         validators=[
                                                             wtforms.validators.InputRequired(),
                                                             wtforms.validators.NumberRange(min=0)
                                                         ])
        reply_to_mentions = wtforms.BooleanField("Always respond to mentions/replies")
        scan_images = wtforms.BooleanField("Read Images (Increases 💵 usage)")
        function_calling = wtforms.BooleanField("Enable Function Calling (⚠️ Ensure selected model supports function calling)")
        random_messages = wtforms.BooleanField("Randomly Send Messages (Send random messages at random intervals)")

        submit: wtforms.SubmitField = wtforms.SubmitField("Save Changes")

    form: Form = Form()

    reply_mentions_val = await self.config.guild(guild).reply_to_mentions_replies()
    form.reply_to_mentions.default = form.reply_to_mentions.checked = reply_mentions_val
    form.percent.default = await self.config.guild(guild).reply_percent() * 100
    form.messages_backread.default = await self.config.guild(guild).messages_backread()
    form.messages_backread_seconds.default = await self.config.guild(guild).messages_backread_seconds()
    form.whitelist.default = [str(id) for id in await self.config.guild(guild).channels_whitelist()]
    models = await get_available_models(self.openai_client)
    form.model.default = await self.config.guild(guild).model()
    form.model.choices = [(model, model) for model in models]

    scan_images_val = await self.config.guild(guild).scan_images()
    form.scan_images.default = form.scan_images.checked = scan_images_val
    function_calling_val = await self.config.guild(guild).function_calling()
    form.function_calling.default = form.function_calling.checked = function_calling_val

    random_messages_val = await self.config.guild(guild).random_messages_enabled()
    form.random_messages.default = form.random_messages.checked = random_messages_val

    if form.validate_on_submit():
        pecentage = form.percent.data
        model = form.model.data
        new_whitelist = [int(id) for id in form.whitelist.data]
        reply_mentions = form.reply_to_mentions.data
        messages_backread = form.messages_backread.data
        messages_backread_seconds = form.messages_backread_seconds.data
        scan_images = form.scan_images.data
        function_calling = form.function_calling.data
        random_messages = form.random_messages.data
        try:
            await self.config.guild(guild).reply_percent.set(pecentage / 100)
            await self.config.guild(guild).model.set(model)
            await self.config.guild(guild).reply_to_mentions_replies.set(reply_mentions)
            await self.config.guild(guild).channels_whitelist.set(new_whitelist)
            await self.config.guild(guild).messages_backread.set(messages_backread)
            await self.config.guild(guild).messages_backread_seconds.set(messages_backread_seconds)
            await self.config.guild(guild).scan_images.set(scan_images)
            await self.config.guild(guild).function_calling.set(function_calling)
            await self.config.guild(guild).random_messages_enabled.set(random_messages)
            self.channels_whitelist[guild.id] = new_whitelist
        except Exception:
            return {
                "status": 1,
                "notifications": [{"message": "Something went wrong while saving the config!", "category": "error"}],
            }
        return {
            "status": 0,
            "notifications": [{"message": "Saved config!", "category": "success"}],
            "redirect_url": kwargs["request_url"],
        }

    source = """<p>Only a subset of available settings. See Discord cog commands for all available settings.</p>{{ form|safe }}"""

    return {
        "status": 0,
        "web_content": {"source": source, "form": form},
    } 