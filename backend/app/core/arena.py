"""In-memory game registry with per-game event fan-out to SSE subscribers.

Concurrency model: every method here is synchronous and must only be called from the
event loop thread (async endpoints and the timeout loop). Nothing awaits in the middle of
a mutation, so each call is atomic without locks. Never call these from a sync (`def`)
endpoint, which FastAPI would run in a worker thread.
"""

import asyncio
from datetime import datetime, timedelta

from app.core.config import settings
from app.game.board import InvalidMoveError, Stone
from app.game.game import Game
from app.schemas import EventType, GameEvent, GameState, MoveOut, color_of


class GameNotFoundError(Exception):
    pass


class Arena:
    def __init__(
        self,
        move_timeout: timedelta,
        max_invalid_moves: int = 5,
        join_timeout: timedelta = timedelta(minutes=30),
    ) -> None:
        self.move_timeout = move_timeout
        self.max_invalid_moves = max_invalid_moves
        self.join_timeout = join_timeout
        self._games: dict[str, Game] = {}
        self._seq: dict[str, int] = {}
        self._subscribers: dict[str, set[asyncio.Queue[GameEvent]]] = {}

    def create(self) -> Game:
        """Board size (15) and win length (5) are fixed for every game."""
        game = Game.new(
            move_timeout=self.move_timeout,
            max_invalid_moves=self.max_invalid_moves,
            join_timeout=self.join_timeout,
        )
        self._games[game.id] = game
        self._seq[game.id] = 0
        self._subscribers[game.id] = set()
        return game

    def get(self, game_id: str) -> Game:
        game = self._games.get(game_id)
        if game is None:
            raise GameNotFoundError(f"game {game_id} not found")
        return game

    def list(self) -> list[Game]:
        return list(self._games.values())

    def join(self, game_id: str, secret: str, name: str | None) -> tuple[Game, Stone]:
        game = self.get(game_id)
        seated = len(game.players)
        stone = game.join(secret, name)
        if len(game.players) > seated:
            self._publish(game, "player_joined", color=color_of(stone))
            if len(game.players) == 2:
                self._publish(game, "game_started")
        return game, stone

    def play(self, game_id: str, secret: str, x: int, y: int) -> Game:
        game = self.get(game_id)
        try:
            move = game.play(secret, x, y)
        except InvalidMoveError:
            # 非法落子本身不广播；只有因此判负时才推送 game_over
            if game.status.is_over:
                self._publish(game, "game_over")
            raise
        self._publish(game, "move", move=MoveOut.of(move))
        if game.status.is_over:
            self._publish(game, "game_over")
        return game

    def expire_timeouts(self, now: datetime | None = None) -> None:
        for game in self._games.values():
            if game.check_timeout(now):
                self._publish(game, "game_over")

    def expire_abandoned(self, now: datetime | None = None) -> None:
        """Destroy waiting games no agent has joined within join_timeout, freeing their memory.

        Subscribers get a final game_expired event; afterwards the game id answers 404.
        """
        for game in [g for g in self._games.values() if g.is_abandoned(now)]:
            self._publish(game, "game_expired")
            del self._games[game.id], self._seq[game.id], self._subscribers[game.id]

    async def run_timeout_loop(self, interval: float = 0.5) -> None:
        while True:
            self.expire_timeouts()
            self.expire_abandoned()
            await asyncio.sleep(interval)

    def subscribe(self, game_id: str) -> asyncio.Queue[GameEvent]:
        """Register a listener. Its queue starts with a snapshot of the current state."""
        game = self.get(game_id)
        queue: asyncio.Queue[GameEvent] = asyncio.Queue()
        queue.put_nowait(self._event(game, "snapshot", seq=self._seq[game_id]))
        self._subscribers[game_id].add(queue)
        return queue

    def unsubscribe(self, game_id: str, queue: asyncio.Queue[GameEvent]) -> None:
        self._subscribers.get(game_id, set()).discard(queue)

    def subscriber_count(self, game_id: str) -> int:
        return len(self._subscribers.get(game_id, ()))

    def _event(self, game: Game, type: EventType, seq: int, **extra) -> GameEvent:
        return GameEvent(type=type, seq=seq, state=GameState.of(game), **extra)

    def _publish(self, game: Game, type: EventType, **extra) -> None:
        self._seq[game.id] += 1
        event = self._event(game, type, seq=self._seq[game.id], **extra)
        for queue in self._subscribers[game.id]:
            queue.put_nowait(event)


arena = Arena(
    timedelta(seconds=settings.move_timeout_seconds),
    settings.max_invalid_moves,
    timedelta(seconds=settings.join_timeout_seconds),
)
