"""In-memory state store. Everything lives in process memory; nothing is persisted."""

from collections.abc import Callable
from threading import Lock
from typing import TypeVar

from app.game.game import Game

T = TypeVar("T")


class GameNotFoundError(KeyError):
    pass


class MemoryStore:
    def __init__(self) -> None:
        self._lock = Lock()
        self._games: dict[str, Game] = {}

    def create(self, size: int, win_length: int) -> Game:
        game = Game.new(size, win_length)
        with self._lock:
            self._games[game.id] = game
        return game

    def get(self, game_id: str) -> Game:
        with self._lock:
            game = self._games.get(game_id)
        if game is None:
            raise GameNotFoundError(game_id)
        return game

    def list(self) -> list[Game]:
        with self._lock:
            return list(self._games.values())

    def delete(self, game_id: str) -> None:
        with self._lock:
            if self._games.pop(game_id, None) is None:
                raise GameNotFoundError(game_id)

    def mutate(self, game_id: str, fn: Callable[[Game], T]) -> T:
        """Run `fn` on a game while holding the store lock, so moves are applied atomically."""
        with self._lock:
            game = self._games.get(game_id)
            if game is None:
                raise GameNotFoundError(game_id)
            return fn(game)


store = MemoryStore()
