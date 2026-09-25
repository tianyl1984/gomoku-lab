"""Wire format shared by the HTTP API and the SSE stream."""

from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.game.board import Stone
from app.game.game import EndReason, Game, GameStatus, Move, Player

Color = Literal["black", "white"]
EventType = Literal[
    "snapshot", "player_joined", "game_started", "move", "game_over", "game_expired"
]


def color_of(stone: Stone) -> Color:
    return "black" if stone is Stone.BLACK else "white"


class JoinRequest(BaseModel):
    name: str | None = Field(None, max_length=40, description="agent 显示名称")


class MoveRequest(BaseModel):
    x: int = Field(..., description="列，从 0 开始")
    y: int = Field(..., description="行，从 0 开始")


class MoveOut(BaseModel):
    x: int
    y: int
    color: Color

    @classmethod
    def of(cls, move: Move) -> "MoveOut":
        return cls(x=move.x, y=move.y, color=color_of(move.stone))


class PlayerOut(BaseModel):
    name: str
    joined_at: datetime
    invalid_moves: int = Field(description="累计非法落子次数")

    @classmethod
    def of(cls, player: Player | None) -> "PlayerOut | None":
        if player is None:
            return None
        return cls(name=player.name, joined_at=player.joined_at, invalid_moves=player.invalid_moves)


class Players(BaseModel):
    black: PlayerOut | None
    white: PlayerOut | None

    @classmethod
    def of(cls, game: Game) -> "Players":
        return cls(
            black=PlayerOut.of(game.players.get(Stone.BLACK)),
            white=PlayerOut.of(game.players.get(Stone.WHITE)),
        )


class GameState(BaseModel):
    id: str
    size: int
    win_length: int
    board: list[list[int]] = Field(description="board[y][x]：0 空，1 黑，2 白")
    status: GameStatus
    players: Players
    current_player: Color | None = Field(description="行棋方，仅 playing 时有值")
    winner: Color | None
    end_reason: EndReason | None
    winning_line: list[tuple[int, int]] | None = Field(description="获胜连线坐标 (x, y)")
    moves: list[MoveOut]
    move_timeout_seconds: float
    max_invalid_moves: int = Field(description="累计非法落子达到该次数即判负")
    turn_deadline: datetime | None = Field(description="当前行棋方的落子截止时间")
    join_deadline: datetime | None = Field(
        description="仅 waiting 时有值：到该时刻仍无新 agent 加入，对局将被销毁"
    )
    created_at: datetime
    started_at: datetime | None
    ended_at: datetime | None
    server_time: datetime = Field(description="生成该状态时的服务器时间，用于校准倒计时")

    @classmethod
    def of(cls, game: Game) -> "GameState":
        return cls(
            id=game.id,
            size=game.board.size,
            win_length=game.board.win_length,
            board=game.board.to_list(),
            status=game.status,
            players=Players.of(game),
            current_player=color_of(game.current) if game.status is GameStatus.PLAYING else None,
            winner=color_of(game.winner) if game.winner else None,
            end_reason=game.end_reason,
            winning_line=game.winning_line,
            moves=[MoveOut.of(m) for m in game.moves],
            move_timeout_seconds=game.move_timeout.total_seconds(),
            max_invalid_moves=game.max_invalid_moves,
            turn_deadline=game.turn_deadline,
            join_deadline=game.join_deadline,
            created_at=game.created_at,
            started_at=game.started_at,
            ended_at=game.ended_at,
            server_time=datetime.now(UTC),
        )


class GameSummary(BaseModel):
    id: str
    size: int
    status: GameStatus
    players: Players
    move_count: int
    created_at: datetime

    @classmethod
    def of(cls, game: Game) -> "GameSummary":
        return cls(
            id=game.id,
            size=game.board.size,
            status=game.status,
            players=Players.of(game),
            move_count=len(game.moves),
            created_at=game.created_at,
        )


class JoinResponse(BaseModel):
    game_id: str
    color: Color = Field(description="服务器分配给该 agent 的颜色")
    state: GameState


class GameEvent(BaseModel):
    type: EventType
    seq: int = Field(description="该对局内单调递增的事件序号")
    state: GameState = Field(description="事件发生后的完整对局状态")
    move: MoveOut | None = Field(None, description="type=move 时的这一手")
    color: Color | None = Field(None, description="type=player_joined 时加入的一方")

    @property
    def is_terminal(self) -> bool:
        """Last event of a stream: game_over, game_expired, or a snapshot of a finished game."""
        if self.type in ("game_over", "game_expired"):
            return True
        return self.type == "snapshot" and self.state.status.is_over
