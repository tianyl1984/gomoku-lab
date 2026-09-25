from datetime import timedelta

import pytest

from app.game.board import InvalidMoveError, Stone
from app.game.game import (
    EndReason,
    Game,
    GameFullError,
    GameNotStartedError,
    GameOverError,
    GameStatus,
    NotAPlayerError,
    NotYourTurnError,
)

TIMEOUT = timedelta(minutes=2)


def started_game(**kwargs):
    """A game with both seats taken. Returns (game, {Stone: secret})."""
    game = Game.new(move_timeout=TIMEOUT, **kwargs)
    secrets = {}
    for secret in ("secret-aaaa", "secret-bbbb"):
        secrets[game.join(secret)] = secret
    return game, secrets


def play_all(game, secrets, moves):
    for x, y in moves:
        game.play(secrets[game.current], x, y)


def test_join_assigns_both_colors_and_starts():
    game = Game.new()
    first = game.join("secret-aaaa", "alpha")
    assert game.status is GameStatus.WAITING
    assert game.turn_deadline is None
    second = game.join("secret-bbbb", "beta")
    assert {first, second} == {Stone.BLACK, Stone.WHITE}
    assert game.status is GameStatus.PLAYING
    assert game.current is Stone.BLACK
    assert game.players[first].name == "alpha"
    assert game.turn_deadline == game.started_at + game.move_timeout


def test_rejoin_with_same_secret_is_idempotent():
    game = Game.new()
    first = game.join("secret-aaaa")
    assert game.join("secret-aaaa") is first
    assert len(game.players) == 1
    assert game.status is GameStatus.WAITING


def test_third_agent_cannot_join():
    game, secrets = started_game()
    with pytest.raises(GameFullError):
        game.join("secret-cccc")
    # 已入座的 agent 仍可重复 join 拿回自己的颜色
    assert game.join(secrets[Stone.WHITE]) is Stone.WHITE


def test_cannot_play_before_start():
    game = Game.new()
    game.join("secret-aaaa")
    with pytest.raises(GameNotStartedError):
        game.play("secret-aaaa", 7, 7)


def test_unknown_secret_rejected():
    game, _ = started_game()
    with pytest.raises(NotAPlayerError):
        game.play("secret-zzzz", 7, 7)


def test_turn_order_enforced_by_secret():
    game, secrets = started_game()
    with pytest.raises(NotYourTurnError):
        game.play(secrets[Stone.WHITE], 7, 7)
    game.play(secrets[Stone.BLACK], 7, 7)
    with pytest.raises(NotYourTurnError):
        game.play(secrets[Stone.BLACK], 8, 8)
    game.play(secrets[Stone.WHITE], 8, 8)
    assert [m.stone for m in game.moves] == [Stone.BLACK, Stone.WHITE]


def test_black_wins_with_five():
    game, secrets = started_game()
    play_all(game, secrets, [(0, 0), (0, 1), (1, 0), (1, 1), (2, 0), (2, 1), (3, 0), (3, 1)])
    assert game.status is GameStatus.PLAYING
    game.play(secrets[Stone.BLACK], 4, 0)
    assert game.status is GameStatus.BLACK_WIN
    assert game.winner is Stone.BLACK
    assert game.end_reason is EndReason.FIVE
    assert game.winning_line == [(0, 0), (1, 0), (2, 0), (3, 0), (4, 0)]
    assert game.ended_at is not None
    assert game.turn_deadline is None
    with pytest.raises(GameOverError):
        game.play(secrets[Stone.WHITE], 10, 10)
    with pytest.raises(GameOverError):
        game.join("secret-cccc")


def test_white_wins_with_five():
    game, secrets = started_game()
    play_all(
        game,
        secrets,
        [(0, 0), (5, 5), (0, 2), (6, 6), (0, 4), (7, 7), (0, 6), (8, 8), (0, 8), (9, 9)],
    )
    assert game.status is GameStatus.WHITE_WIN


def test_invalid_move_keeps_turn_and_clock():
    game, secrets = started_game()
    game.play(secrets[Stone.BLACK], 0, 0)
    started = game.turn_started_at
    with pytest.raises(InvalidMoveError):
        game.play(secrets[Stone.WHITE], 0, 0)
    assert game.current is Stone.WHITE
    assert game.turn_started_at == started


def test_full_board_without_winner_is_draw():
    # 3x3 连三（井字棋）的一个平局终局：
    #   B W B
    #   B W W
    #   W B B
    game, secrets = started_game(size=3, win_length=3)
    black = [(0, 0), (2, 0), (0, 1), (1, 2), (2, 2)]
    white = [(1, 0), (1, 1), (2, 1), (0, 2)]
    for i, b in enumerate(black):
        game.play(secrets[Stone.BLACK], *b)
        if i < len(white):
            game.play(secrets[Stone.WHITE], *white[i])
    assert game.status is GameStatus.DRAW
    assert game.end_reason is EndReason.BOARD_FULL
    assert game.winner is None


class TestTimeout:
    def test_side_to_move_loses_after_timeout(self):
        game, _ = started_game()
        deadline = game.turn_deadline
        assert not game.check_timeout(deadline - timedelta(seconds=1))
        assert game.status is GameStatus.PLAYING
        assert game.check_timeout(deadline)
        assert game.status is GameStatus.WHITE_WIN  # 黑方先行却一直不下
        assert game.end_reason is EndReason.TIMEOUT
        assert game.winning_line is None
        assert not game.check_timeout(deadline + TIMEOUT)  # 只判一次

    def test_clock_resets_after_each_move(self):
        game, secrets = started_game()
        start = game.turn_started_at
        later = start + timedelta(seconds=90)
        game.play(secrets[Stone.BLACK], 7, 7, now=later)
        assert game.turn_deadline == later + TIMEOUT
        # 离开局已超过 2 分钟，但白方的计时刚开始
        assert not game.check_timeout(start + timedelta(seconds=150))
        assert game.check_timeout(later + TIMEOUT)
        assert game.status is GameStatus.BLACK_WIN

    def test_no_timeout_while_waiting(self):
        game = Game.new(move_timeout=TIMEOUT)
        game.join("secret-aaaa")
        assert not game.check_timeout(game.created_at + timedelta(days=1))
        assert game.status is GameStatus.WAITING


class TestInvalidMoves:
    def test_invalid_moves_are_counted_per_player(self):
        game, secrets = started_game()
        black, white = secrets[Stone.BLACK], secrets[Stone.WHITE]
        game.play(black, 7, 7)
        with pytest.raises(InvalidMoveError, match=r"occupied \(invalid moves 1/5\)"):
            game.play(white, 7, 7)
        with pytest.raises(InvalidMoveError, match=r"out of bounds \(invalid moves 2/5\)"):
            game.play(white, 15, 0)
        assert game.players[Stone.WHITE].invalid_moves == 2
        assert game.players[Stone.BLACK].invalid_moves == 0
        # 下对一手后计数不清零
        game.play(white, 8, 8)
        game.play(black, 9, 9)
        with pytest.raises(InvalidMoveError, match="3/5"):
            game.play(white, 9, 9)

    def test_fifth_invalid_move_loses(self):
        game, secrets = started_game()
        black = secrets[Stone.BLACK]
        game.play(black, 7, 7)
        game.play(secrets[Stone.WHITE], 8, 8)
        for _ in range(4):
            with pytest.raises(InvalidMoveError):
                game.play(black, 7, 7)
        assert game.status is GameStatus.PLAYING
        with pytest.raises(InvalidMoveError, match="invalid moves 5/5, you lose"):
            game.play(black, 8, 8)
        assert game.status is GameStatus.WHITE_WIN
        assert game.end_reason is EndReason.INVALID_MOVES
        assert game.turn_deadline is None
        assert len(game.moves) == 2
        with pytest.raises(GameOverError):
            game.play(black, 0, 0)

    def test_other_errors_are_not_counted(self):
        game, secrets = started_game()
        white = secrets[Stone.WHITE]
        for _ in range(6):
            with pytest.raises(NotYourTurnError):
                game.play(white, 7, 7)
        assert game.players[Stone.WHITE].invalid_moves == 0
        assert game.status is GameStatus.PLAYING

    def test_limit_is_configurable(self):
        game = Game.new(max_invalid_moves=1)
        game.join("secret-aaaa")
        game.join("secret-bbbb")
        black = "secret-aaaa" if game.seat_of("secret-aaaa") is Stone.BLACK else "secret-bbbb"
        with pytest.raises(InvalidMoveError, match="you lose"):
            game.play(black, -1, 0)
        assert game.end_reason is EndReason.INVALID_MOVES
