from datetime import timedelta

import pytest

from app.core.arena import Arena, GameNotFoundError
from app.game.board import InvalidMoveError


@pytest.fixture
def arena():
    return Arena(timedelta(minutes=2))


def drain(queue):
    events = []
    while not queue.empty():
        events.append(queue.get_nowait())
    return events


def join_both(arena, game_id):
    colors = {}
    for secret in ("secret-aaaa", "secret-bbbb"):
        _, stone = arena.join(game_id, secret, None)
        colors[stone.name.lower()] = secret
    return colors


def test_subscriber_gets_snapshot_then_lifecycle_events(arena):
    game = arena.create()
    queue = arena.subscribe(game.id)
    [snapshot] = drain(queue)
    assert snapshot.type == "snapshot"
    assert snapshot.state.status == "waiting"

    colors = join_both(arena, game.id)
    events = drain(queue)
    assert [e.type for e in events] == ["player_joined", "player_joined", "game_started"]
    assert {e.color for e in events[:2]} == {"black", "white"}
    assert events[-1].state.status == "playing"
    assert events[-1].state.current_player == "black"
    assert [e.seq for e in events] == [1, 2, 3]

    arena.play(game.id, colors["black"], 7, 7)
    [move] = drain(queue)
    assert move.type == "move"
    assert move.move.model_dump() == {"x": 7, "y": 7, "color": "black"}
    assert move.state.board[7][7] == 1
    assert move.state.current_player == "white"


def test_rejoin_does_not_publish(arena):
    game = arena.create()
    queue = arena.subscribe(game.id)
    arena.join(game.id, "secret-aaaa", None)
    arena.join(game.id, "secret-aaaa", None)
    assert [e.type for e in drain(queue)] == ["snapshot", "player_joined"]


def test_winning_move_publishes_move_then_game_over(arena):
    game = arena.create()
    colors = join_both(arena, game.id)
    queue = arena.subscribe(game.id)
    drain(queue)
    for x in range(4):
        arena.play(game.id, colors["black"], x, 0)
        arena.play(game.id, colors["white"], x, 1)
    drain(queue)
    arena.play(game.id, colors["black"], 4, 0)
    move, over = drain(queue)
    assert (move.type, over.type) == ("move", "game_over")
    assert not move.is_terminal and over.is_terminal
    assert over.state.winner == "black"
    assert over.state.end_reason == "five"


def test_expire_timeouts_publishes_game_over(arena):
    game = arena.create()
    join_both(arena, game.id)
    queue = arena.subscribe(game.id)
    drain(queue)
    arena.expire_timeouts(game.turn_deadline - timedelta(seconds=1))
    assert drain(queue) == []
    arena.expire_timeouts(game.turn_deadline)
    [over] = drain(queue)
    assert over.type == "game_over"
    assert over.state.winner == "white"
    assert over.state.end_reason == "timeout"


def test_snapshot_of_finished_game_is_terminal(arena):
    game = arena.create()
    join_both(arena, game.id)
    arena.expire_timeouts(game.turn_deadline)
    [snapshot] = drain(arena.subscribe(game.id))
    assert snapshot.type == "snapshot" and snapshot.is_terminal


def test_unsubscribe(arena):
    game = arena.create()
    queue = arena.subscribe(game.id)
    assert arena.subscriber_count(game.id) == 1
    arena.unsubscribe(game.id, queue)
    assert arena.subscriber_count(game.id) == 0
    arena.join(game.id, "secret-aaaa", None)  # 退订后不再收到事件
    assert [e.type for e in drain(queue)] == ["snapshot"]


def test_unknown_game(arena):
    with pytest.raises(GameNotFoundError):
        arena.get("nope")
    with pytest.raises(GameNotFoundError):
        arena.subscribe("nope")


def test_invalid_move_publishes_nothing_until_it_loses(arena):
    game = arena.create()
    colors = join_both(arena, game.id)
    queue = arena.subscribe(game.id)
    drain(queue)
    for _ in range(4):
        with pytest.raises(InvalidMoveError):
            arena.play(game.id, colors["black"], 99, 99)
    assert drain(queue) == []
    with pytest.raises(InvalidMoveError):
        arena.play(game.id, colors["black"], 99, 99)
    [over] = drain(queue)
    assert over.type == "game_over"
    assert over.state.winner == "white"
    assert over.state.end_reason == "invalid_moves"
    assert over.state.players.black.invalid_moves == 5


def test_expire_abandoned_publishes_game_expired_and_frees_the_game(arena):
    game = arena.create()
    queue = arena.subscribe(game.id)
    drain(queue)
    arena.expire_abandoned(game.join_deadline - timedelta(seconds=1))
    assert drain(queue) == []
    assert arena.get(game.id) is game

    arena.expire_abandoned(game.join_deadline)
    [expired] = drain(queue)
    assert expired.type == "game_expired" and expired.is_terminal
    assert expired.state.status == "waiting"
    with pytest.raises(GameNotFoundError):
        arena.get(game.id)
    assert arena.list() == []
    assert arena.subscriber_count(game.id) == 0
    arena.unsubscribe(game.id, queue)  # SSE 生成器的 finally 仍会调用，不能报错


def test_expire_abandoned_keeps_started_games(arena):
    started, waiting = arena.create(), arena.create()
    join_both(arena, started.id)
    arena.expire_abandoned(waiting.join_deadline)
    assert arena.list() == [started]
