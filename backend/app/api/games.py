from fastapi import APIRouter, HTTPException, status

from app.api.schemas import GameCreate, GameState, GameSummary, MoveRequest, parse_player
from app.core.store import GameNotFoundError, store
from app.game.board import InvalidMoveError
from app.game.game import Game, GameOverError, NotYourTurnError

router = APIRouter(prefix="/games", tags=["games"])


def _not_found(game_id: str) -> HTTPException:
    return HTTPException(status.HTTP_404_NOT_FOUND, f"game {game_id} not found")


@router.post("", status_code=status.HTTP_201_CREATED)
def create_game(body: GameCreate | None = None) -> GameState:
    body = body or GameCreate()
    if body.win_length > body.size:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "win_length must be <= size")
    return GameState.of(store.create(body.size, body.win_length))


@router.get("")
def list_games() -> list[GameSummary]:
    return [GameSummary.of(g) for g in store.list()]


@router.get("/{game_id}")
def get_game(game_id: str) -> GameState:
    try:
        return GameState.of(store.get(game_id))
    except GameNotFoundError:
        raise _not_found(game_id) from None


@router.delete("/{game_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_game(game_id: str) -> None:
    try:
        store.delete(game_id)
    except GameNotFoundError:
        raise _not_found(game_id) from None


@router.post("/{game_id}/moves")
def play_move(game_id: str, body: MoveRequest) -> GameState:
    stone = parse_player(body.player) if body.player else None

    def apply(game: Game) -> GameState:
        game.play(body.x, body.y, stone)
        return GameState.of(game)

    try:
        return store.mutate(game_id, apply)
    except GameNotFoundError:
        raise _not_found(game_id) from None
    except InvalidMoveError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e)) from None
    except (GameOverError, NotYourTurnError) as e:
        raise HTTPException(status.HTTP_409_CONFLICT, str(e)) from None
