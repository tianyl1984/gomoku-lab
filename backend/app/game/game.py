"""A single gomoku match between two agents: seats, turn order, move clock and result."""

import hashlib
import hmac
import random
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import NoReturn

from app.game.board import Board, InvalidMoveError, Stone


def _now() -> datetime:
    return datetime.now(UTC)


def _hash_secret(secret: str) -> str:
    return hashlib.sha256(secret.encode()).hexdigest()


class GameStatus(StrEnum):
    WAITING = "waiting"  # 座位未满，等待 agent 加入
    PLAYING = "playing"
    BLACK_WIN = "black_win"
    WHITE_WIN = "white_win"
    DRAW = "draw"

    @property
    def is_over(self) -> bool:
        return self in (GameStatus.BLACK_WIN, GameStatus.WHITE_WIN, GameStatus.DRAW)


class EndReason(StrEnum):
    FIVE = "five"  # 连成五子
    TIMEOUT = "timeout"  # 行棋方超时，判负
    BOARD_FULL = "board_full"  # 棋盘下满，平局
    INVALID_MOVES = "invalid_moves"  # 行棋方累计非法落子达到上限，判负


class GameError(Exception):
    pass


class GameFullError(GameError):
    pass


class GameNotStartedError(GameError):
    pass


class GameOverError(GameError):
    pass


class NotAPlayerError(GameError):
    pass


class NotYourTurnError(GameError):
    pass


@dataclass
class Player:
    name: str
    secret_hash: str
    joined_at: datetime
    # 累计非法落子次数（已占用 / 越界）
    invalid_moves: int = 0

    def matches(self, secret: str) -> bool:
        return hmac.compare_digest(self.secret_hash, _hash_secret(secret))


@dataclass(frozen=True)
class Move:
    x: int
    y: int
    stone: Stone


@dataclass
class Game:
    board: Board
    move_timeout: timedelta
    max_invalid_moves: int = 5
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    status: GameStatus = GameStatus.WAITING
    players: dict[Stone, Player] = field(default_factory=dict)
    current: Stone = Stone.BLACK
    moves: list[Move] = field(default_factory=list)
    winning_line: list[tuple[int, int]] | None = None
    end_reason: EndReason | None = None
    created_at: datetime = field(default_factory=_now)
    started_at: datetime | None = None
    ended_at: datetime | None = None
    # 当前行棋方开始计时的时刻；超过 move_timeout 未落子即判负
    turn_started_at: datetime | None = None

    @classmethod
    def new(
        cls,
        size: int = 15,
        win_length: int = 5,
        move_timeout: timedelta = timedelta(minutes=2),
        max_invalid_moves: int = 5,
    ) -> "Game":
        return cls(
            board=Board(size, win_length),
            move_timeout=move_timeout,
            max_invalid_moves=max_invalid_moves,
        )

    @property
    def winner(self) -> Stone | None:
        return {
            GameStatus.BLACK_WIN: Stone.BLACK,
            GameStatus.WHITE_WIN: Stone.WHITE,
        }.get(self.status)

    @property
    def turn_deadline(self) -> datetime | None:
        if self.status is not GameStatus.PLAYING or self.turn_started_at is None:
            return None
        return self.turn_started_at + self.move_timeout

    def seat_of(self, secret: str) -> Stone | None:
        for stone, player in self.players.items():
            if player.matches(secret):
                return stone
        return None

    def join(self, secret: str, name: str | None = None, now: datetime | None = None) -> Stone:
        """Seat an agent on a random free color; the game starts once both seats are taken.

        Re-joining with the same secret returns the already assigned seat, so retries are safe.
        """
        seat = self.seat_of(secret)
        if seat is not None:
            return seat
        if self.status.is_over:
            raise GameOverError(f"game is over: {self.status}")
        if self.status is not GameStatus.WAITING:
            raise GameFullError("both seats are already taken")

        now = now or _now()
        stone = random.choice([s for s in (Stone.BLACK, Stone.WHITE) if s not in self.players])
        self.players[stone] = Player(
            name=name or f"agent-{stone.name.lower()}",
            secret_hash=_hash_secret(secret),
            joined_at=now,
        )
        if len(self.players) == 2:
            self.status = GameStatus.PLAYING
            self.started_at = now
            self.turn_started_at = now
        return stone

    def play(self, secret: str, x: int, y: int, now: datetime | None = None) -> Move:
        stone = self.seat_of(secret)
        if stone is None:
            raise NotAPlayerError("secret does not match any player in this game")
        if self.status is GameStatus.WAITING:
            raise GameNotStartedError("game has not started yet")
        if self.status.is_over:
            raise GameOverError(f"game is over: {self.status}")
        if stone is not self.current:
            raise NotYourTurnError(f"it is {self.current.name.lower()}'s turn")

        now = now or _now()
        try:
            self.board.place(x, y, stone)
        except InvalidMoveError as e:
            self._record_invalid_move(stone, str(e), now)
        move = Move(x, y, stone)
        self.moves.append(move)

        line = self.board.find_winning_line(x, y)
        if line is not None:
            self.winning_line = line
            self._finish(self._win_status(stone), EndReason.FIVE, now)
        elif self.board.is_full():
            self._finish(GameStatus.DRAW, EndReason.BOARD_FULL, now)
        else:
            self.current = stone.opponent
            self.turn_started_at = now
        return move

    def check_timeout(self, now: datetime | None = None) -> bool:
        """End the game if the side to move has exceeded its move clock. Returns True if it did."""
        deadline = self.turn_deadline
        now = now or _now()
        if deadline is None or now < deadline:
            return False
        self._finish(self._win_status(self.current.opponent), EndReason.TIMEOUT, now)
        return True

    def _record_invalid_move(self, stone: Stone, reason: str, now: datetime) -> NoReturn:
        """Count an illegal placement; reaching max_invalid_moves loses the game. Always raises.

        The move clock is not reset, so an agent retrying bad moves still runs down its time.
        """
        player = self.players[stone]
        player.invalid_moves += 1
        count = f"{player.invalid_moves}/{self.max_invalid_moves}"
        if player.invalid_moves >= self.max_invalid_moves:
            self._finish(self._win_status(stone.opponent), EndReason.INVALID_MOVES, now)
            raise InvalidMoveError(f"{reason}; invalid moves {count}, you lose")
        raise InvalidMoveError(f"{reason} (invalid moves {count})")

    @staticmethod
    def _win_status(stone: Stone) -> GameStatus:
        return GameStatus.BLACK_WIN if stone is Stone.BLACK else GameStatus.WHITE_WIN

    def _finish(self, status: GameStatus, reason: EndReason, now: datetime) -> None:
        self.status = status
        self.end_reason = reason
        self.ended_at = now
        self.turn_started_at = None
