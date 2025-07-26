from redbot.core import commands
from redbot.core.bot import Red

from aiuser.types.abc import MixinMeta

from .consent_page import opt_consent
from .main_page import main
from .owner_config_page import bot_owner_server_config


class DashboardIntegration(MixinMeta):
    bot: Red
    main = main
    opt_consent = opt_consent
    bot_owner_server_config = bot_owner_server_config

    @commands.Cog.listener()
    async def on_dashboard_cog_add(self, dashboard_cog: commands.Cog) -> None:
        dashboard_cog.rpc.third_parties_handler.add_third_party(self)
