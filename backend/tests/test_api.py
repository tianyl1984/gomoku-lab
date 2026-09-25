import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def game_id(client):
    return client.post("/api/games").json()["id"]


def move(client, game_id, x, y, **extra):
    return client.post(f"/api/games/{game_id}/moves", json={"x": x, "y": y, **extra})


def test_create_game_defaults(client):
    res = client.post("/api/games")
    assert res.status_code == 201
    data = res.json()
    assert data["size"] == 15
    assert data["status"] == "playing"
    assert data["current_player"] == "black"
    assert len(data["board"]) == 15 and all(len(r) == 15 for r in data["board"])


def test_create_game_custom_size(client):
    data = client.post("/api/games", json={"size": 19}).json()
    assert data["size"] == 19
    assert client.post("/api/games", json={"size": 4}).status_code == 422


def test_play_until_black_wins(client, game_id):
    for x in range(4):
        assert move(client, game_id, x, 0).status_code == 200
        assert move(client, game_id, x, 1).status_code == 200
    data = move(client, game_id, 4, 0).json()
    assert data["status"] == "black_win"
    assert data["winner"] == "black"
    assert data["winning_line"] == [[0, 0], [1, 0], [2, 0], [3, 0], [4, 0]]
    assert data["board"][0][:5] == [1, 1, 1, 1, 1]
    assert data["board"][1][:4] == [2, 2, 2, 2]
    assert len(data["moves"]) == 9

    res = move(client, game_id, 10, 10)
    assert res.status_code == 409


def test_move_errors(client, game_id):
    assert move(client, game_id, 7, 7).status_code == 200
    assert move(client, game_id, 7, 7).status_code == 400
    assert move(client, game_id, 15, 0).status_code == 400
    assert move(client, game_id, 0, 0, player="black").status_code == 409
    assert move(client, game_id, 0, 0, player="white").status_code == 200
    assert move(client, "nope", 0, 0).status_code == 404


def test_get_list_delete(client, game_id):
    assert client.get(f"/api/games/{game_id}").json()["id"] == game_id
    assert game_id in [g["id"] for g in client.get("/api/games").json()]
    assert client.delete(f"/api/games/{game_id}").status_code == 204
    assert client.get(f"/api/games/{game_id}").status_code == 404
