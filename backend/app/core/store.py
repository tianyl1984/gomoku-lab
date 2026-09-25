"""In-memory state store. Everything lives in process memory; nothing is persisted."""

from threading import Lock
from typing import Any


class MemoryStore:
    def __init__(self) -> None:
        self._lock = Lock()
        self._games: dict[str, Any] = {}

    @property
    def lock(self) -> Lock:
        return self._lock

    @property
    def games(self) -> dict[str, Any]:
        return self._games


store = MemoryStore()
