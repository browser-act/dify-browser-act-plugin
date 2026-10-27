from collections import OrderedDict
from collections.abc import Callable
from copy import deepcopy
from hashlib import sha256
from threading import Lock
from time import monotonic

from dify_plugin.entities import ParameterOption


class OptionCache:
    """Bounded process-local cache of validated selector options, never task data."""

    def __init__(self):
        self._entries = OrderedDict()
        self._lock = Lock()

    def get(
        self,
        api_key: str,
        user_id: str | None,
        source: str,
        load: Callable[[], list[ParameterOption]],
    ) -> list[ParameterOption]:
        key = (sha256(api_key.strip().encode()).digest(), user_id, source)
        with self._lock:
            now = monotonic()
            for expired in [k for k, (expires, _) in self._entries.items() if expires <= now]:
                del self._entries[expired]
            if key in self._entries:
                return deepcopy(self._entries[key][1])

        # Network I/O must not hold the cache lock or block other accounts.
        # Concurrent misses may load independently; exceptions are never cached.
        options = load()
        with self._lock:
            self._entries[key] = (monotonic() + 60, deepcopy(options))
            self._entries.move_to_end(key)
            while len(self._entries) > 128:
                self._entries.popitem(last=False)
        return options


option_cache = OptionCache()
