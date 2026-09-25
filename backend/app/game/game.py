"""A single gomoku match: turn order, move history and result."""

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum

from app.game.board import Board, Stone


class GameStatus(StrEnum):
    PLAYING = "playing"
    BLACK_WIN = "black_win"
    WHITE_WIN = "white_win"
    DRAW = "draw"


class GameOverError(Exception):
    pass


class NotYourTurnError(Exception):
    pass


@dataclass(frozen=True)
class Move:
    x: int
    y: int
    stone: Stone


@dataclass
class Game:
    board: Board
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    current: Stone = Stone.BLACK
    moves: list[Move] = field(default_factory=list)
    status: GameStatus = GameStatus.PLAYING
    winning_line: list[tuple[int, int]] | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    @classmethod
    def new(cls, size: int = 15, win_length: int = 5) -> "Game":
        return cls(board=Board(size, win_length))

    @property
    def winner(self) -> Stone | None:
        return {
            GameStatus.BLACK_WIN: Stone.BLACK,
            GameStatus.WHITE_WIN: Stone.WHITE,
        }.get(self.status)

    def play(self, x: int, y: int, stone: Stone | None = None) -> Move:
        """Place a stone for the side to move. `stone`, if given, must match that side."""
        if self.status is not GameStatus.PLAYING:
            raise GameOverError(f"game is over: {self.status}")
        if stone is not None and stone is not self.current:
            raise NotYourTurnError(f"it is {self.current.name.lower()}'s turn")

        self.board.place(x, y, self.current)
        move = Move(x, y, self.current)
        self.moves.append(move)

        line = self.board.find_winning_line(x, y)
        if line is not None:
            self.winning_line = line
            self.status = (
                GameStatus.BLACK_WIN if self.current is Stone.BLACK else GameStatus.WHITE_WIN
            )
        elif self.board.is_full():
            self.status = GameStatus.DRAW
        else:
            self.current = self.current.opponent
        return move

