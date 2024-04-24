import typing

import discord
from redbot.core import commands
from redbot.core.bot import Red


# This decorator is required because the cog Dashboard may load after the third party when the bot is started.
def dashboard_page(*args, **kwargs):
    def decorator(func: typing.Callable):
        func.__dashboard_decorator_params__ = (args, kwargs)
        return func
    return decorator


class DashboardIntegration:
    bot: Red

    @commands.Cog.listener()
    # ``on_dashboard_cog_add`` is triggered by the Dashboard cog automatically.
    async def on_dashboard_cog_add(self, dashboard_cog: commands.Cog) -> None:
        dashboard_cog.rpc.third_parties_handler.add_third_party(self)  # Add the third party to Dashboard.

    # Create a default page for the third party (``name=None``). It will be available at the URL ``/third-party/MyCog``.
    @dashboard_page(name=None, description="Send **Hello** to a user!", methods=("GET", "POST"), is_owner=True)
    # The kwarg ``user`` means that Red-Dashboard will request a connection from a bot user with OAuth from Discord.
    async def send_hello(self, user: discord.User, **kwargs) -> typing.Dict[str, typing.Any]:
        import wtforms

        class Form(kwargs["Form"]):  # Create a WTForms form.
            def __init__(self):
                super().__init__(prefix="send_hello_form_")
            user: wtforms.IntegerField = wtforms.IntegerField(
                "User:", validators=[wtforms.validators.InputRequired(), kwargs["DpyObjectConverter"](discord.User)])
            message: wtforms.TextAreaField = wtforms.TextAreaField(
                "Message:", validators=[wtforms.validators.InputRequired(), wtforms.validators.Length(max=2000)], default="Hello World!")
            submit: wtforms.SubmitField = wtforms.SubmitField("Send Hello!")

        form: Form = Form()
        # Check if the form is valid, run validators and retrieve the Discord objects.
        if form.validate_on_submit() and await form.validate_dpy_converters():
            # Thanks to the ``DpyObjectConverter`` validator, the user object is directly retrieved.
            recipient = form.user.data
            try:
                await recipient.send(form.message.data)
            except discord.Forbidden:
                return {
                    "status": 0,
                    "notifications": [{"message": f"Hello could not be sent to {recipient.display_name}!", "category": "error"}],
                }
            return {
                "status": 0,
                "notifications": [{"message": f"Hello sent to {recipient.display_name} with success!", "category": "success"}],
                "redirect_url": kwargs["request_url"],
            }

        source = "{{ form|safe }}"

        return {
            "status": 0,
            "web_content": {"source": source, "form": form},
        }

    # Create a page nammed "guild" for the third party. It will be available at the URL ``/dashboard/<guild_id>/third-party/MyCog/guild``.
    @dashboard_page(name="guild", description="Get basic details about a __guild__!")
    # The kwarg ``guild`` means that Red-Dashboard will ask for the choice of a guild among those to which the user has access.
    async def guild_page(self, user: discord.User, guild: discord.Guild, **kwargs) -> typing.Dict[str, typing.Any]:
        return {
            "status": 0,
            "web_content": {  # Return a web content with the text variable ``title_content``.
                "source": '<h4>You are in the guild "{{ guild.name }}" ({{ guild.id }})!</h4>',
                "guild": {"name": guild.name, "id": guild.id},
            },
        }
