from collections import OrderedDict

class Cache(OrderedDict):
    def __init__(self, limit: int):
        super().__init__()
        self.limit = limit

    def __getitem__(self, key):
        if key not in self:
            return None
        self.move_to_end(key)
        return super().__getitem__(key)

    def __setitem__(self, key, value):
        super().__setitem__(key, value)
        self.move_to_end(key)
        if len(self) > self.limit:
            self.popitem(last=False)
