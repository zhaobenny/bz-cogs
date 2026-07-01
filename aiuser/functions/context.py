from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, List, Optional

import discord
from redbot.core import Config, commands
from redbot.core.bot import Red

if TYPE_CHECKING:
    from aiuser.core.services import AIUserServices
    from aiuser.utils.vectorstore import VectorStore


@dataclass
class ToolContext:
    services: "AIUserServices"
    ctx: commands.Context
    config: Config
    bot: Red
    memories: Optional["VectorStore"] = None
    files_to_send: List[discord.File] = field(default_factory=list)
    audio_transcripts_to_cache: List[str] = field(default_factory=list)
    suppress_response: bool = False

    def attach_file(self, file: discord.File) -> None:
        """Queue a file to be sent with the bot's response."""
        self.files_to_send.append(file)

    def suppress(self) -> None:
        """Request that no text response is sent for this message."""
        self.suppress_response = True
