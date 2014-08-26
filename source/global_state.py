class GlobalState(object):
    """
        Store data we need during the run.
    """
    state = {}

    @classmethod
    def reset(cls):
        cls.state = {}

    def __getattr__(self, item):
        if item in self.state:
            return self.state
        raise AttributeError

    def __setattr(self, key, value):
        self.state[key] = value