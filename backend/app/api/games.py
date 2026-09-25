# Every endpoint that touches the arena is `async def` so it runs on the event loop thread;
# see app/core/arena.py for why that matters.
from collections.abc import AsyncIterable
from typing import Annotated

from fastapi import APIRouter, Depends, Header, status
from fastapi.sse import EventSourceResponse, ServerSentEvent

from app.api.errors import InvalidSecretError, MissingSecretError
from app.core.arena import arena
from app.game.game import Game
from app.schemas import (
    GameState,
    GameSummary,
    JoinRequest,
    JoinResponse,
    MoveRequest,
    color_of,
)

router = APIRouter(prefix="/games", tags=["games"])

SECRET_HEADER = "X-Agent-Secret"
SECRET_MIN, SECRET_MAX = 8, 256


async def agent_secret(
    x_agent_secret: Annotated[
        str | None, Header(description="agent 本地生成的随机串，加入对局及后续落子时携带")
    ] = None,
) -> str:
    if not x_agent_secret:
        raise MissingSecretError(f"{SECRET_HEADER} header is required")
    if not SECRET_MIN <= len(x_agent_secret) <= SECRET_MAX:
        raise InvalidSecretError(f"{SECRET_HEADER} must be {SECRET_MIN}-{SECRET_MAX} characters")
    return x_agent_secret


async def existing_game(game_id: str) -> Game:
    return arena.get(game_id)


Secret = Annotated[str, Depends(agent_secret)]
ExistingGame = Annotated[Game, Depends(existing_game)]


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_game() -> GameState:
    """新建对局，棋盘固定 15 × 15、连五获胜。"""
    return GameState.of(arena.create())


@router.get("")
async def list_games() -> list[GameSummary]:
    games = sorted(arena.list(), key=lambda g: g.created_at, reverse=True)
    return [GameSummary.of(g) for g in games]


@router.get("/{game_id}")
async def get_game(game: ExistingGame) -> GameState:
    return GameState.of(game)


@router.post("/{game_id}/join")
async def join_game(game_id: str, secret: Secret, body: JoinRequest | None = None) -> JoinResponse:
    """申请对战：服务器随机分配颜色；座位已满后其他 agent 无法加入。同一 secret 重复调用返回同一座位。"""
    game, stone = arena.join(game_id, secret, body.name if body else None)
    return JoinResponse(game_id=game.id, color=color_of(stone), state=GameState.of(game))


@router.post("/{game_id}/moves")
async def play_move(game_id: str, secret: Secret, body: MoveRequest) -> GameState:
    return GameState.of(arena.play(game_id, secret, body.x, body.y))


@router.get("/{game_id}/events", response_class=EventSourceResponse)
async def game_events(game: ExistingGame) -> AsyncIterable[ServerSentEvent]:
    """SSE：先推送一次 snapshot，之后每次状态变化推送一个事件（均携带完整状态），
    game_over 或 game_expired 后关闭。"""
    queue = arena.subscribe(game.id)
    try:
        while True:
            event = await queue.get()
            yield ServerSentEvent(data=event, event=event.type, id=str(event.seq))
            if event.is_terminal:
                return
    finally:
        arena.unsubscribe(game.id, queue)
