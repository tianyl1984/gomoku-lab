import pytest

from app.game.board import InvalidMoveError, Stone
from app.game.game import Game, GameOverError, GameStatus, NotYourTurnError


def play_all(game: Game, moves):
    for x, y in moves:
        game.play(x, y)


def test_black_moves_first_and_turns_alternate():
    game = Game.new()
    assert game.current is Stone.BLACK
    game.play(7, 7)
    assert game.current is Stone.WHITE
    game.play(7, 8)
    assert game.current is Stone.BLACK
    assert [m.stone for m in game.moves] == [Stone.BLACK, Stone.WHITE]


def test_black_wins():
    game = Game.new()
    # 黑 (0..4, 0)，白 (0..3, 1)
    play_all(game, [(0, 0), (0, 1), (1, 0), (1, 1), (2, 0), (2, 1), (3, 0), (3, 1)])
    assert game.status is GameStatus.PLAYING
    game.play(4, 0)
    assert game.status is GameStatus.BLACK_WIN
    assert game.winner is Stone.BLACK
    assert game.winning_line == [(0, 0), (1, 0), (2, 0), (3, 0), (4, 0)]
    # 获胜后当前方不再切换
    assert game.current is Stone.BLACK


def test_white_wins():
    game = Game.new()
    play_all(
        game,
        [(0, 0), (5, 5), (0, 2), (6, 6), (0, 4), (7, 7), (0, 6), (8, 8), (0, 8), (9, 9)],
    )
    assert game.status is GameStatus.WHITE_WIN
    assert game.winner is Stone.WHITE


def test_no_moves_after_game_over():
    game = Game.new()
    play_all(game, [(0, 0), (0, 1), (1, 0), (1, 1), (2, 0), (2, 1), (3, 0), (3, 1), (4, 0)])
    with pytest.raises(GameOverError):
        game.play(10, 10)


def test_wrong_player_rejected():
    game = Game.new()
    with pytest.raises(NotYourTurnError):
        game.play(0, 0, Stone.WHITE)
    game.play(0, 0, Stone.BLACK)
    with pytest.raises(NotYourTurnError):
        game.play(1, 1, Stone.BLACK)


def test_invalid_move_does_not_change_turn():
    game = Game.new()
    game.play(0, 0)
    with pytest.raises(InvalidMoveError):
        game.play(0, 0)
    assert game.current is Stone.WHITE
    assert len(game.moves) == 1


def test_full_board_without_winner_is_draw():
    # 3x3 连三（井字棋）的一个平局终局：
    #   B W B
    #   B W W
    #   W B B
    game = Game.new(size=3, win_length=3)
    black = [(0, 0), (2, 0), (0, 1), (1, 2), (2, 2)]
    white = [(1, 0), (1, 1), (2, 1), (0, 2)]
    for i, b in enumerate(black):
        game.play(*b)
        if i < len(white):
            game.play(*white[i])
    assert game.status is GameStatus.DRAW
    assert game.winner is None
