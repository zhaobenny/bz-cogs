import threading
from collections import OrderedDict


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
