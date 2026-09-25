"""Map domain exceptions to HTTP responses: {"detail": <message>, "code": <machine-readable>}."""

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.core.arena import GameNotFoundError
from app.game.board import InvalidMoveError
from app.game.game import (
    GameFullError,
    GameNotStartedError,
    GameOverError,
    NotAPlayerError,
    NotYourTurnError,
)


class MissingSecretError(Exception):
    pass


class InvalidSecretError(Exception):
    pass


ERRORS: dict[type[Exception], tuple[int, str]] = {
    MissingSecretError: (401, "missing_secret"),
    InvalidSecretError: (422, "invalid_secret"),
    NotAPlayerError: (403, "not_a_player"),
    GameNotFoundError: (404, "game_not_found"),
    InvalidMoveError: (400, "invalid_move"),
    GameFullError: (409, "game_full"),
    GameNotStartedError: (409, "game_not_started"),
    GameOverError: (409, "game_over"),
    NotYourTurnError: (409, "not_your_turn"),
}


def _handler(status: int, code: str):
    async def handle(_: Request, exc: Exception) -> JSONResponse:
        return JSONResponse({"detail": str(exc), "code": code}, status_code=status)

    return handle


# 请求体 / 参数校验失败（如 x 不是整数、缺少字段），由 FastAPI 在进入路由前抛出
INVALID_REQUEST = (422, "invalid_request")


async def _validation_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
    def describe(err: dict) -> str:
        loc = ".".join(str(p) for p in err["loc"] if p != "body")
        return f"{loc}: {err['msg']}" if loc else err["msg"]

    status, code = INVALID_REQUEST
    detail = "; ".join(describe(e) for e in exc.errors())
    return JSONResponse({"detail": detail, "code": code}, status_code=status)


def register_error_handlers(app: FastAPI) -> None:
    for exc_type, (status, code) in ERRORS.items():
        app.add_exception_handler(exc_type, _handler(status, code))
    app.add_exception_handler(RequestValidationError, _validation_handler)
