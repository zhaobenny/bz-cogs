import json
import logging
from typing import Any, Dict, List, Optional, Set

from aiuser.context.entry import MessageEntry
from aiuser.utils.utilities import encode_text_to_tokens

logger = logging.getLogger("red.bz_cogs.aiuser.context")

LOW_DETAIL_IMAGE_TOKEN_COST = 512
HIGH_DETAIL_IMAGE_TOKEN_COST = 2500


class Conversation:
    """An ordered list of chat messages (oldest first) plus a token budget.

    This is a dumb container: it knows nothing about Discord, config, or how
    the conversation is assembled. The only mutators are ``append``/``prepend``
    (and their role-specific helpers), so message ordering is always explicit
    at the call site — no index arithmetic.
    """

    def __init__(self, model: str, token_limit: int):
        self.model = model
        self.token_limit = token_limit
        self.tokens = 0
        self.entries: List[MessageEntry] = []
        self.turn_context_entries: List[MessageEntry] = []
        self.seen_message_ids: Set[int] = set()
        self.can_reply = True
        self._entry_tokens: List[int] = []

    def __len__(self) -> int:
        return len(self.entries)

    def __repr__(self) -> str:
        return json.dumps(self.to_chat_payload(), indent=4)

    def is_full(self) -> bool:
        return self.tokens > self.token_limit

    # --- mutators ---

    async def append(self, entry: MessageEntry) -> MessageEntry:
        cost = await self._entry_cost(entry)
        self.entries.append(entry)
        self._entry_tokens.append(cost)
        self.tokens += cost
        return entry

    async def prepend(self, entry: MessageEntry) -> MessageEntry:
        cost = await self._entry_cost(entry)
        self.entries.insert(0, entry)
        self._entry_tokens.insert(0, cost)
        self.tokens += cost
        return entry

    async def append_system(
        self, content: str, name: Optional[str] = None
    ) -> MessageEntry:
        await self.prune_oldest_if_over_limit()
        return await self.append(MessageEntry("system", content, name=name))

    async def prepend_system(
        self, content: str, name: Optional[str] = None
    ) -> MessageEntry:
        return await self.prepend(MessageEntry("system", content, name=name))

    async def append_assistant(
        self,
        content: str = "",
        tool_calls: Optional[list] = None,
        assistant_extra_fields: Optional[Dict[str, Any]] = None,
    ) -> MessageEntry:
        await self.prune_oldest_if_over_limit()
        return await self.append(
            MessageEntry(
                "assistant",
                content,
                tool_calls=tool_calls or [],
                assistant_extra_fields=assistant_extra_fields or {},
            )
        )

    async def append_tool_result(self, content: str, tool_call_id: str) -> MessageEntry:
        await self.prune_oldest_if_over_limit()
        return await self.append(
            MessageEntry("tool", content, tool_call_id=tool_call_id)
        )

    async def prune_oldest_if_over_limit(self):
        """Drop oldest entries until back under the token limit (keeps >= 2)."""
        while self.tokens > self.token_limit and len(self.entries) > 2:
            self.entries.pop(0)
            self.tokens -= self._entry_tokens.pop(0)

    # --- output ---

    def to_chat_payload(self) -> List[dict]:
        """Serialize to the chat-completions wire format."""
        payload = []
        for entry in self.entries:
            message = {"role": entry.role, "content": entry.content}
            if entry.tool_calls:
                message["tool_calls"] = [
                    tc.model_dump(mode="json") if hasattr(tc, "model_dump") else tc
                    for tc in entry.tool_calls
                ]
            if entry.tool_call_id:
                message["tool_call_id"] = entry.tool_call_id
            if entry.name:
                message["name"] = entry.name
            if entry.role == "assistant" and entry.assistant_extra_fields:
                message.update(entry.assistant_extra_fields)
            payload.append(message)
        return payload

    # --- internals ---

    @staticmethod
    async def _entry_cost(entry: MessageEntry) -> int:
        content = entry.content
        if isinstance(content, list):
            cost = 0
            for item in content:
                if not isinstance(item, dict):
                    continue
                if item.get("type") == "text":
                    cost += await encode_text_to_tokens(item.get("text", ""))
                elif item.get("type") == "image_url":
                    detail = (item.get("image_url") or {}).get("detail")
                    cost += (
                        LOW_DETAIL_IMAGE_TOKEN_COST
                        if detail == "low"
                        else HIGH_DETAIL_IMAGE_TOKEN_COST
                    )
            return cost
        return await encode_text_to_tokens(str(content))
