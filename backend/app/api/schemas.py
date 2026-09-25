from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.game.board import Stone
from app.game.game import Game, GameStatus, Move

Player = Literal["black", "white"]


def stone_name(stone: Stone) -> Player:
    return "black" if stone is Stone.BLACK else "white"


def parse_player(player: Player) -> Stone:
    return Stone.BLACK if player == "black" else Stone.WHITE


class GameCreate(BaseModel):
    size: int = Field(15, ge=5, le=25, description="棋盘边长")
    win_length: int = Field(5, ge=3, le=10, description="连成几子获胜")


class MoveRequest(BaseModel):
    x: int = Field(..., description="列，从 0 开始")
    y: int = Field(..., description="行，从 0 开始")
    player: Player | None = Field(
        None, description="落子方；传入时会校验是否轮到该方，不传则默认当前方"
    )


class MoveOut(BaseModel):
    x: int
    y: int
    player: Player

    @classmethod
    def of(cls, move: Move) -> "MoveOut":
        return cls(x=move.x, y=move.y, player=stone_name(move.stone))


class GameState(BaseModel):
    id: str
    size: int
    win_length: int
    board: list[list[int]] = Field(description="board[y][x]：0 空，1 黑，2 白")
    current_player: Player
    status: GameStatus
    winner: Player | None
    winning_line: list[tuple[int, int]] | None = Field(description="获胜连线坐标 (x, y)")
    moves: list[MoveOut]
    created_at: datetime

    @classmethod
    def of(cls, game: Game) -> "GameState":
        return cls(
            id=game.id,
            size=game.board.size,
            win_length=game.board.win_length,
            board=game.board.to_list(),
            current_player=stone_name(game.current),
            status=game.status,
            winner=stone_name(game.winner) if game.winner else None,
            winning_line=game.winning_line,
            moves=[MoveOut.of(m) for m in game.moves],
            created_at=game.created_at,
        )


class GameSummary(BaseModel):
    id: str
    size: int
    status: GameStatus
    move_count: int
    created_at: datetime

    @classmethod
    def of(cls, game: Game) -> "GameSummary":
        return cls(
            id=game.id,
            size=game.board.size,
            status=game.status,
            move_count=len(game.moves),
            created_at=game.created_at,
        )
