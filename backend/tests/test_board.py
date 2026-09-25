import pytest

from app.game.board import Board, InvalidMoveError, Stone


def place_all(board: Board, points, stone=Stone.BLACK):
    for x, y in points:
        board.place(x, y, stone)


@pytest.mark.parametrize(
    "points",
    [
        [(3, 7), (4, 7), (5, 7), (6, 7), (7, 7)],  # 横
        [(7, 3), (7, 4), (7, 5), (7, 6), (7, 7)],  # 竖
        [(3, 3), (4, 4), (5, 5), (6, 6), (7, 7)],  # ↘
        [(3, 11), (4, 10), (5, 9), (6, 8), (7, 7)],  # ↗
    ],
    ids=["horizontal", "vertical", "diagonal", "anti-diagonal"],
)
def test_five_in_a_row_wins_in_every_direction(points):
    board = Board()
    place_all(board, points)
    # 从连线上任意一点检测都应命中，包括中间点
    for x, y in points:
        assert sorted(board.find_winning_line(x, y)) == sorted(points)


def test_four_is_not_a_win():
    board = Board()
    place_all(board, [(0, 0), (1, 0), (2, 0), (3, 0)])
    assert board.find_winning_line(3, 0) is None


def test_overline_counts_as_win():
    board = Board()
    points = [(i, 5) for i in range(2, 8)]
    place_all(board, points)
    assert len(board.find_winning_line(4, 5)) == 6


def test_line_broken_by_opponent_is_not_a_win():
    board = Board()
    place_all(board, [(0, 0), (1, 0), (3, 0), (4, 0), (5, 0)])
    board.place(2, 0, Stone.WHITE)
    assert board.find_winning_line(3, 0) is None
    assert board.find_winning_line(2, 0) is None


def test_win_on_board_edge_and_corner():
    board = Board()
    points = [(14, 14 - i) for i in range(5)]
    place_all(board, points)
    assert board.find_winning_line(14, 14) is not None

    board = Board()
    points = [(10 + i, i) for i in range(5)]  # ↘ 碰到右边界
    place_all(board, points)
    assert board.find_winning_line(14, 4) is not None


def test_does_not_wrap_around_edges():
    board = Board()
    place_all(board, [(12, 0), (13, 0), (14, 0), (0, 1), (1, 1)])
    assert board.find_winning_line(14, 0) is None
    assert board.find_winning_line(0, 1) is None


def test_winning_line_is_ordered():
    board = Board()
    points = [(5, 5), (7, 3), (3, 7), (6, 4), (4, 6)]
    place_all(board, points)
    line = board.find_winning_line(5, 5)
    assert line == [(3, 7), (4, 6), (5, 5), (6, 4), (7, 3)]


def test_place_rejects_occupied_and_out_of_bounds():
    board = Board()
    board.place(0, 0, Stone.BLACK)
    with pytest.raises(InvalidMoveError):
        board.place(0, 0, Stone.WHITE)
    for x, y in [(-1, 0), (0, -1), (15, 0), (0, 15)]:
        with pytest.raises(InvalidMoveError):
            board.place(x, y, Stone.BLACK)
