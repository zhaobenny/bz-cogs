from typing import Optional

from redbot.core import commands

from aiuser.config.defaults import DEFAULT_PROMPT
from aiuser.config.model_info import get_model_info
from aiuser.config.resolver import ScopedConfigResolver
from aiuser.context.messages import MessagesThread
from aiuser.types.abc import MixinMeta
from aiuser.utils.utilities import format_variables


class ThreadSetup:
    """Handles initialization logic for a MessagesThread"""

    def __init__(self, cog: MixinMeta, ctx: commands.Context) -> None:
        self.cog = cog
        self.ctx = ctx
        self.config = cog.config
        self.guild = ctx.guild
        self.bot = cog.bot

    async def create_thread(
        self, prompt: Optional[str] = None, history: bool = True
    ) -> MessagesThread:
        """Create and fully setup a MessagesThread"""
        thread = MessagesThread(self.cog, self.ctx)

        thread.model = await self.config.guild(self.guild).model()
        thread.token_limit = (
            await self.config.guild(self.guild).custom_model_tokens_limit()
            or get_model_info(thread.model).token_limit
        )

        if not prompt:  # jank
            await thread.add_discord_message(thread.init_message)

        bot_prompt = prompt or await self._pick_prompt()
        formatted_prompt = await format_variables(self.ctx, bot_prompt)
        await thread.add_system_message(formatted_prompt)

        if await self._should_use_image_model():
            scan_model = await self.config.guild(self.guild).scan_images_model()
            if scan_model:
                thread.model = scan_model

        if history:
            await thread.populate_history()

        return thread

    async def _pick_prompt(self) -> str:
        """Select the prompt via member > role > channel > guild > global"""
        scoped_prompt = await ScopedConfigResolver(self.config).resolve(
            "custom_text_prompt",
            guild=self.guild,
            channel=self.ctx.channel,
            member=self.ctx.message.author,
        )
        return scoped_prompt or await self.config.custom_text_prompt() or DEFAULT_PROMPT

    async def _should_use_image_model(self) -> bool:
        """Check if we should switch to image scanning model"""
        if (
            self.ctx.interaction
            or not await self.config.guild(self.guild).scan_images()
        ):
            return False

        message = self.ctx.message

        if message.attachments and message.attachments[0].content_type.startswith(
            "image/"
        ):
            return True

        if message.reference:
            ref = message.reference
            if not ref.channel_id or not ref.message_id:
                return False
            replied = ref.cached_message or await self.bot.get_channel(
                ref.channel_id
            ).fetch_message(ref.message_id)
            return replied.attachments and replied.attachments[
                0
            ].content_type.startswith("image/")

        return False

async def create_messages_thread(
    cog: MixinMeta,
    ctx: commands.Context,
    prompt: Optional[str] = None,
    history: bool = True,
) -> MessagesThread:
    setup = ThreadSetup(cog, ctx)
    return await setup.create_thread(prompt, history)
