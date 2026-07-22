import json
import logging
from typing import Any, Dict, List, Optional

from aiuser.context.entry import MessageEntry
from aiuser.utils.utilities import encode_text_to_tokens

logger = logging.getLogger("red.bz_cogs.aiuser.context")

LOW_DETAIL_IMAGE_TOKEN_COST = 512
HIGH_DETAIL_IMAGE_TOKEN_COST = 2500


class Conversation:
    """An ordered list of chat messages (oldest first) plus a token budget."""

    def __init__(self, model: str, token_limit: int):
        self.model = model
        self.token_limit = token_limit
        self.tokens = 0
        self.entries: List[MessageEntry] = []
        self.memory_entries: List[MessageEntry] = []
        self.from_message_context = False
        self._entry_tokens: List[int] = []
        self._entry_protected: List[bool] = []

    def __len__(self) -> int:
        return len(self.entries)

    def __repr__(self) -> str:
        return json.dumps(self.to_chat_payload(), indent=4)

    # --- mutators ---

    async def append(
        self,
        entry: MessageEntry,
        *,
        protected: bool = False,
    ) -> MessageEntry:
        await self.prune_oldest_if_over_limit()
        cost = await self._entry_cost(entry)
        self.entries.append(entry)
        self._entry_tokens.append(cost)
        self._entry_protected.append(protected)
        self.tokens += cost
        if entry.role == "tool":
            self._drop_orphaned_tool_results()
        return entry

    async def append_system(
        self,
        content: str,
        *,
        protected: bool = False,
    ) -> MessageEntry:
        return await self.append(
            MessageEntry("system", content),
            protected=protected,
        )

    async def append_assistant(
        self,
        content: str = "",
        tool_calls: Optional[list] = None,
        assistant_extra_fields: Optional[Dict[str, Any]] = None,
    ) -> MessageEntry:
        return await self.append(
            MessageEntry(
                "assistant",
                content,
                tool_calls=tool_calls or [],
                assistant_extra_fields=assistant_extra_fields or {},
            )
        )

    async def append_tool_result(self, content: str, tool_call_id: str) -> MessageEntry:
        return await self.append(
            MessageEntry("tool", content, tool_call_id=tool_call_id)
        )

    async def prune_oldest_if_over_limit(self):
        """Drop the oldest entries until back under the token limit
        while preserving the active prompt and newest entry (keeps >= 2)."""
        pruned = False
        while self.tokens > self.token_limit and len(self.entries) > 2:
            index = next(
                (
                    i
                    for i in range(len(self.entries) - 1)
                    if not self._entry_protected[i]
                ),
                None,
            )
            if index is None:
                break
            self.entries.pop(index)
            self.tokens -= self._entry_tokens.pop(index)
            self._entry_protected.pop(index)
            pruned = True
        if pruned:
            self._drop_orphaned_tool_results()

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
            if entry.role == "assistant" and entry.assistant_extra_fields:
                message.update(entry.assistant_extra_fields)
            payload.append(message)
        return payload

    # --- internals ---

    def _drop_orphaned_tool_results(self):
        in_tool_exchange = False
        orphaned_indexes = []
        for index, entry in enumerate(self.entries):
            if entry.role == "assistant" and entry.tool_calls:
                in_tool_exchange = True
            elif entry.role == "tool":
                if not in_tool_exchange:
                    orphaned_indexes.append(index)
            else:
                in_tool_exchange = False

        for index in reversed(orphaned_indexes):
            self.entries.pop(index)
            self.tokens -= self._entry_tokens.pop(index)
            self._entry_protected.pop(index)

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
