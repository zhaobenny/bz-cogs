from __future__ import annotations

from abc import ABC
from typing import TYPE_CHECKING

from redbot.core import Config, commands
from redbot.core.bot import Red

if TYPE_CHECKING:
    from aiuser.core.services import AIUserServices


class CompositeMetaClass(type(commands.Cog), type(ABC)):
    pass


class MixinMeta(ABC):
    bot: Red
    config: Config
    services: Optional["AIUserServices"]
    __version__: str

    @property
    def consent(self):
        return self.services.consent
