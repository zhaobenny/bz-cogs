import pathlib

import discord

from aiuser.dashboard.decorator import dashboard_page

TEMPLATES_PATH = pathlib.Path(__file__).parent / "templates"


@dashboard_page(
    name="data_usage_consent",
    description="Manage your consent for data usage by the cog.",
    methods=("GET", "POST"),
)
async def opt_consent(self, user: discord.User, **kwargs):
    import wtforms

    class Form(kwargs["Form"]):
        def __init__(self):
            super().__init__(prefix="consent_")

        accept: wtforms.SubmitField = wtforms.SubmitField(
            "Consent",
            render_kw={
                "class": "btn btn-success px-4 py-2",
            },
        )
        reject: wtforms.SubmitField = wtforms.SubmitField(
            "Do not consent",
            render_kw={
                "class": "btn btn-danger px-4 py-2",
            },
        )

    form = Form()

    if self.consent.is_opted_in(user.id):
        whitelist_text = "opted in"
        consent_choice = "accept"
        form.accept.render_kw["disabled"] = True
        form.accept.render_kw["class"] = "btn btn-outline-secondary px-4 py-2"
        form.reject.render_kw["disabled"] = False
    elif self.consent.is_opted_out(user.id):
        whitelist_text = "opted out"
        consent_choice = "reject"
        form.accept.render_kw["disabled"] = False
        form.reject.render_kw["disabled"] = True
        form.reject.render_kw["class"] = "btn btn-outline-secondary px-4 py-2"
    else:
        whitelist_text = "not opted in or out"
        consent_choice = ""
        form.accept.render_kw["disabled"] = False
        form.reject.render_kw["disabled"] = False

    if form.validate_on_submit():
        try:
            if form.accept.data:
                await self.consent.opt_in(user.id)
            elif form.reject.data:
                await self.consent.opt_out(user.id)
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
            "data": {"status": 0},
        }

    template_path = TEMPLATES_PATH / "consent_page.html"
    source = template_path.read_text()

    return {
        "status": 0,
        "web_content": {
            "source": source,
            "user_name": user.name,
            "whitelist_text": whitelist_text,
            "consent_choice": consent_choice,
            "csrf": form.hidden_tag(),
        },
    }
