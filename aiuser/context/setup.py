from typing import Optional

import discord
from redbot.core import commands

from aiuser.config.defaults import DEFAULT_PROMPT
from aiuser.config.models import OTHER_MODELS_LIMITS
from aiuser.context.messages import MessagesThread
from aiuser.types.abc import MixinMeta
from aiuser.utils.utilities import format_variables


class ThreadSetup:
    """ Handles initialization logic for a MessagesThread """

    def __init__(self, cog: MixinMeta, ctx: commands.Context) -> None:
        self.cog = cog
        self.ctx = ctx
        self.config = cog.config
        self.guild = ctx.guild
        self.bot = cog.bot

    async def create_thread(
        self,
        prompt: Optional[str] = None,
        history: bool = True
    ) -> MessagesThread:
        """Create and fully setup a MessagesThread"""
        thread = MessagesThread(self.cog, self.ctx)

        thread.model = await self.config.guild(self.guild).model()
        thread.token_limit = (
            await self.config.guild(self.guild).custom_model_tokens_limit()
            or self._get_token_limit(thread.model)
        )

        if not prompt:  # jank
            await thread.add_msg(thread.init_message)

        bot_prompt = prompt or await self._pick_prompt()
        formatted_prompt = await format_variables(self.ctx, bot_prompt)
        await thread.add_system(formatted_prompt)

        if await self._should_use_image_model():
            scan_model = await self.config.guild(self.guild).scan_images_model()
            if scan_model:
                thread.model = scan_model

        if history:
            await thread.add_history()

        return thread

    async def _pick_prompt(self) -> str:
        """Select the appropriate prompt based on configuration hierarchy"""
        author = self.ctx.message.author
        role_prompt: Optional[str] = None

        # Webhook messages have User objects instead of Member objects
        if isinstance(author, discord.Member):
            for role in author.roles:
                if role.id in (await self.config.all_roles()):
                    role_prompt = await self.config.role(role).custom_text_prompt()
                    break

            member_prompt = await self.config.member(author).custom_text_prompt()
        else:
            member_prompt = None

        return (member_prompt
                or role_prompt
                or await self.config.channel(self.ctx.channel).custom_text_prompt()
                or await self.config.guild(self.guild).custom_text_prompt()
                or await self.config.custom_text_prompt()
                or DEFAULT_PROMPT)

    async def _should_use_image_model(self) -> bool:
        """Check if we should switch to image scanning model"""
        if (self.ctx.interaction
            or not await self.config.guild(self.guild).scan_images()):
            return False

        message = self.ctx.message

        if message.attachments and message.attachments[0].content_type.startswith('image/'):
            return True

        if message.reference:
            ref = message.reference
            if not ref.channel_id or not ref.message_id:
                return False
            replied = ref.cached_message or await self.bot.get_channel(ref.channel_id).fetch_message(ref.message_id)
            return replied.attachments and replied.attachments[0].content_type.startswith('image/')

        return False


    @staticmethod
    def _get_token_limit(model) -> int:
        limit = 7000

        if 'gemini-2' in model or 'gpt-4.1' in model or 'llama-4.1' in model:
            limit = 1000000
        if 'gpt-5' in model:
            limit = 390000
        if "gpt-4o" in model or "llama-3.1" in model or "llama-3.2" in model or 'grok-3' in model:
            limit = 123000
        if "100k" in model or "claude" in model:
            limit = 98000
        if "16k" in model:
            limit = 15000
        if "32k" in model:
            limit = 31000

        model = model.split("/")[-1].split(":")[0]
        if model in OTHER_MODELS_LIMITS:
            limit = OTHER_MODELS_LIMITS.get(model, limit)

        return limit

async def create_messages_thread(
    cog: MixinMeta,
    ctx: commands.Context,
    prompt: Optional[str] = None,
    history: bool = True
) -> MessagesThread:
    setup = ThreadSetup(cog, ctx)
    return await setup.create_thread(prompt, history)