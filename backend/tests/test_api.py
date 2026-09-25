import json
from datetime import timedelta
from typing import get_args

import pytest
from fastapi.testclient import TestClient

from app.api.errors import ERRORS, INVALID_REQUEST
from app.core.arena import arena
from app.game.game import EndReason, GameStatus
from app.main import app
from app.schemas import EventType


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture
def game_id(client):
    return client.post("/api/games").json()["id"]


def join(client, game_id, secret, **body):
    return client.post(f"/api/games/{game_id}/join", headers={"X-Agent-Secret": secret}, json=body)


def move(client, game_id, secret, x, y):
    return client.post(
        f"/api/games/{game_id}/moves", headers={"X-Agent-Secret": secret}, json={"x": x, "y": y}
    )


@pytest.fixture
def seats(client, game_id):
    """Both agents joined. Returns {"black": secret, "white": secret}."""
    colors = {}
    for secret, name in (("secret-aaaa", "alpha"), ("secret-bbbb", "beta")):
        colors[join(client, game_id, secret, name=name).json()["color"]] = secret
    return colors


def parse_sse(text):
    events = []
    for block in text.strip().split("\n\n"):
        fields = dict(line.split(": ", 1) for line in block.splitlines() if not line.startswith(":"))
        if fields:
            events.append({**fields, "data": json.loads(fields["data"])})
    return events


def test_create_game(client):
    res = client.post("/api/games", json={"size": 19})
    assert res.status_code == 201
    data = res.json()
    assert data["size"] == 19
    assert data["status"] == "waiting"
    assert data["players"] == {"black": None, "white": None}
    assert data["current_player"] is None
    assert data["move_timeout_seconds"] == 120
    assert client.post("/api/games", json={"size": 4}).status_code == 422
    assert client.post("/api/games", json={"size": 5, "win_length": 6}).status_code == 422


def test_join_flow(client, game_id):
    first = join(client, game_id, "secret-aaaa", name="alpha").json()
    assert first["game_id"] == game_id
    assert first["state"]["status"] == "waiting"
    assert first["state"]["players"][first["color"]]["name"] == "alpha"

    again = join(client, game_id, "secret-aaaa").json()
    assert again["color"] == first["color"]

    second = join(client, game_id, "secret-bbbb", name="beta").json()
    assert {first["color"], second["color"]} == {"black", "white"}
    assert second["state"]["status"] == "playing"
    assert second["state"]["turn_deadline"] is not None

    res = join(client, game_id, "secret-cccc")
    assert res.status_code == 409
    assert res.json()["code"] == "game_full"


def test_secret_required(client, game_id):
    res = client.post(f"/api/games/{game_id}/join")
    assert res.status_code == 401
    assert res.json()["code"] == "missing_secret"
    res = join(client, game_id, "short")
    assert res.status_code == 422
    assert res.json()["code"] == "invalid_secret"


def test_move_errors(client, game_id):
    assert move(client, game_id, "secret-aaaa", 7, 7).json()["code"] == "not_a_player"
    join(client, game_id, "secret-aaaa")
    res = move(client, game_id, "secret-aaaa", 7, 7)
    assert (res.status_code, res.json()["code"]) == (409, "game_not_started")


def test_play_until_win(client, game_id, seats):
    black, white = seats["black"], seats["white"]
    res = move(client, game_id, white, 7, 7)
    assert (res.status_code, res.json()["code"]) == (409, "not_your_turn")
    res = move(client, game_id, "secret-zzzz", 7, 7)
    assert (res.status_code, res.json()["code"]) == (403, "not_a_player")

    for x in range(4):
        assert move(client, game_id, black, x, 0).status_code == 200
        assert move(client, game_id, white, x, 1).status_code == 200
    res = move(client, game_id, black, 0, 0)
    assert (res.status_code, res.json()["code"]) == (400, "invalid_move")

    data = move(client, game_id, black, 4, 0).json()
    assert data["status"] == "black_win"
    assert data["end_reason"] == "five"
    assert data["winning_line"] == [[0, 0], [1, 0], [2, 0], [3, 0], [4, 0]]
    assert data["moves"][0] == {"x": 0, "y": 0, "color": "black"}

    res = move(client, game_id, white, 10, 10)
    assert (res.status_code, res.json()["code"]) == (409, "game_over")

    # 主动查询状态无需 secret
    assert client.get(f"/api/games/{game_id}").json()["status"] == "black_win"
    summary = next(g for g in client.get("/api/games").json() if g["id"] == game_id)
    assert summary["move_count"] == 9
    assert summary["players"]["black"]["name"] in ("alpha", "beta")


def test_events_stream_format(client, game_id, seats):
    # 流在 game_over 后关闭，所以先让对局结束，再读取已结束对局的 snapshot
    game = arena.get(game_id)
    arena.expire_timeouts(game.turn_deadline + timedelta(seconds=1))
    with client.stream("GET", f"/api/games/{game_id}/events") as res:
        assert res.status_code == 200
        assert res.headers["content-type"].startswith("text/event-stream")
        body = res.read().decode()
    [event] = parse_sse(body)
    assert event["event"] == "snapshot"
    assert event["data"]["type"] == "snapshot"
    assert event["id"] == str(event["data"]["seq"])
    assert event["data"]["state"]["status"] == "white_win"
    assert event["data"]["state"]["end_reason"] == "timeout"
    assert arena.subscriber_count(game_id) == 0


def test_not_found(client):
    for res in (
        client.get("/api/games/nope"),
        client.get("/api/games/nope/events"),
        join(client, "nope", "secret-aaaa"),
        move(client, "nope", "secret-aaaa", 0, 0),
    ):
        assert (res.status_code, res.json()["code"]) == (404, "game_not_found")


def test_game_rule_doc(client):
    res = client.get("/api/game_rule.md")
    assert res.status_code == 200
    assert res.headers["content-type"].startswith("text/markdown")
    doc = res.text
    assert doc.startswith("# Gomoku Lab")
    # 文档是手写的固定内容，确保它覆盖了协议中的每个事件、状态、结束原因和错误码
    for name in [*get_args(EventType), *GameStatus, *EndReason]:
        assert f"`{name}`" in doc, name
    for _, code in [*ERRORS.values(), INVALID_REQUEST]:
        assert f"`{code}`" in doc, code


def test_malformed_body_uses_unified_error_format(client, game_id, seats):
    for body, field in (({"x": "a", "y": 1}, "x"), ({"y": 1}, "x")):
        res = client.post(
            f"/api/games/{game_id}/moves", headers={"X-Agent-Secret": seats["black"]}, json=body
        )
        assert res.status_code == 422
        data = res.json()
        assert data["code"] == "invalid_request"
        assert data["detail"].startswith(f"{field}: ")
    assert client.post("/api/games", json={"size": "big"}).json()["code"] == "invalid_request"
    # 格式错误不计入非法落子
    state = client.get(f"/api/games/{game_id}").json()
    assert state["players"]["black"]["invalid_moves"] == 0


def test_five_invalid_moves_lose(client, game_id, seats):
    black = seats["black"]
    assert client.get(f"/api/games/{game_id}").json()["max_invalid_moves"] == 5
    for i in range(1, 5):
        res = move(client, game_id, black, -1, 0)
        assert (res.status_code, res.json()["code"]) == (400, "invalid_move")
        assert f"invalid moves {i}/5" in res.json()["detail"]
    state = client.get(f"/api/games/{game_id}").json()
    assert state["status"] == "playing"
    assert state["players"]["black"]["invalid_moves"] == 4

    res = move(client, game_id, black, 15, 15)
    assert (res.status_code, res.json()["code"]) == (400, "invalid_move")
    assert "you lose" in res.json()["detail"]
    state = client.get(f"/api/games/{game_id}").json()
    assert (state["status"], state["end_reason"], state["winner"]) == (
        "white_win",
        "invalid_moves",
        "white",
    )
    assert move(client, game_id, black, 7, 7).json()["code"] == "game_over"
