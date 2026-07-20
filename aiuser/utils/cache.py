import threading
from collections import OrderedDict
from typing import Tuple


def tool_calls_cache_key(channel_id: int, message_id: int) -> Tuple[str, int, int]:
    """Context-cache key linking a sent bot message to its tool-call entries.

    Written by response.orchestrator after sending, read back by
    context.assembler when rebuilding history.
    """
    return ("tool_calls", channel_id, message_id)


def memory_cache_key(channel_id: int, message_id: int) -> Tuple[str, int, int]:
    """Context-cache key linking a user message to the memory retrieved for it.

    Written by response.orchestrator after sending, read back by
    context.assembler when rebuilding history.
    """
    return ("memory", channel_id, message_id)


class Cache(OrderedDict):
    def __init__(self, limit: int):
        super().__init__()
        self.limit = limit
        self.lock = threading.RLock()
        self._popping = False

    def __getitem__(self, key):
        with self.lock:
            if key not in self:
                return None
            if not self._popping:
                self.move_to_end(key)
            return super().__getitem__(key)

    def __setitem__(self, key, value):
        with self.lock:
            super().__setitem__(key, value)
            self.move_to_end(key)
            if len(self) > self.limit:
                self.popitem(last=False)

    def popitem(self, last=True):
        with self.lock:
            self._popping = True
            try:
                return super().popitem(last=last)
            finally:
                self._popping = False
