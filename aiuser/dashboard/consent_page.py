import pathlib

import discord

from aiuser.dashboard.decorator import dashboard_page

# Define the path to the templates directory
TEMPLATES_PATH = pathlib.Path(__file__).parent / "templates"


@dashboard_page(
    name="data_usage_consent",
    description="Opt in/out of providing your messages to OpenAI or a third-party provider",
    methods=("GET", "POST"),
)
async def opt_consent(self, user: discord.User, **kwargs):
    import wtforms

    class Form(kwargs["Form"]):
        def __init__(self):
            super().__init__(prefix="consent_")

        accept: wtforms.SubmitField = wtforms.SubmitField(
            "Yes, I consent.",
            render_kw={
                "class": "btn btn-success px-4 py-2",
            },
        )
        reject: wtforms.SubmitField = wtforms.SubmitField(
            "No, I do NOT consent.",
            render_kw={
                "class": "btn btn-danger px-4 py-2",
            },
        )

    form = Form()
    whitelist = await self.config.optin()
    blacklist = await self.config.optout()

    if user.id in whitelist:
        whitelist_text = "opted in"
        form.accept.render_kw["disabled"] = True
        form.accept.render_kw["class"] = "btn btn-outline-secondary px-4 py-2"
        form.reject.render_kw["disabled"] = False
    elif user.id in blacklist:
        whitelist_text = "opted out"
        form.accept.render_kw["disabled"] = False
        form.reject.render_kw["disabled"] = True
        form.reject.render_kw["class"] = "btn btn-outline-secondary px-4 py-2"
    else:
        whitelist_text = "not opted in or out"
        form.accept.render_kw["disabled"] = False
        form.reject.render_kw["disabled"] = False

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
                "notifications": [
                    {
                        "message": "Something went wrong while saving changes!",
                        "category": "error",
                    }
                ],
            }
        return {
            "status": 0,
            "notifications": [{"message": "Saved changes!", "category": "success"}],
            "redirect_url": kwargs["request_url"],
        }

    template_path = TEMPLATES_PATH / "consent_page.html"
    source = template_path.read_text()

    return {
        "status": 0,
        "web_content": {
            "source": source,  # Template content
            "user_name": user.name,  # Context variable
            "whitelist_text": whitelist_text,  # Context variable
            "form": form,  # Context variable (WTForms object)
        },
    }
