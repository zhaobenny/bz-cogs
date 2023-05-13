class Cache(dict):
    def __init__(self, limit: int):
        super().__init__()
        self.limit = limit
        self.keys = []

    def __setitem__(self, key, value):
        if key in self:
            self.keys.remove(key)
            self.keys.append(key)
        else:
            if len(self) >= self.limit:
                oldest_key = self.keys.pop(0)
                del self[oldest_key]
            self.keys.append(key)
        super().__setitem__(key, value)

    def __getitem__(self, key):
        if key in self:
            self.keys.remove(key)
            self.keys.append(key)
            return super().__getitem__(key)
        else:
            return None
