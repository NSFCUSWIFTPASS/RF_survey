class GenericNullObject:
    """
    A generic null object that silently swallows all method calls
    and attribute accesses, returning itself to allow for chaining.
    """
    def __init__(self, log_on_call: bool = False):
        self._log_on_call = log_on_call

    def __getattr__(self, name: str):
        return self._null_callable

    def __call__(self, *args, **kwargs):
        return self._null_callable(self, *args, **kwargs)

    async def _null_callable(self, *args, **kwargs):
        return self
