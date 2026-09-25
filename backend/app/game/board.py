"""Gomoku board and win detection. Pure logic, no framework dependencies."""

from enum import IntEnum

# 横、竖、主对角线（↘）、副对角线（↗）
DIRECTIONS: tuple[tuple[int, int], ...] = ((1, 0), (0, 1), (1, 1), (1, -1))


class Stone(IntEnum):
    EMPTY = 0
    BLACK = 1
    WHITE = 2

    @property
    def opponent(self) -> "Stone":
        if self is Stone.EMPTY:
            raise ValueError("EMPTY has no opponent")
        return Stone.WHITE if self is Stone.BLACK else Stone.BLACK


class InvalidMoveError(ValueError):
    pass


class Board:
    """Square board addressed by (x, y): x is the column, y is the row, both 0-based."""

    def __init__(self, size: int = 15, win_length: int = 5) -> None:
        if size < win_length:
            raise ValueError("board size must be >= win_length")
        self.size = size
        self.win_length = win_length
        self._grid: list[list[Stone]] = [[Stone.EMPTY] * size for _ in range(size)]
        self._stone_count = 0

    def in_bounds(self, x: int, y: int) -> bool:
        return 0 <= x < self.size and 0 <= y < self.size

    def get(self, x: int, y: int) -> Stone:
        return self._grid[y][x]

    def place(self, x: int, y: int, stone: Stone) -> None:
        if stone is Stone.EMPTY:
            raise ValueError("cannot place EMPTY")
        if not self.in_bounds(x, y):
            raise InvalidMoveError(f"({x}, {y}) is out of bounds")
        if self._grid[y][x] is not Stone.EMPTY:
            raise InvalidMoveError(f"({x}, {y}) is already occupied")
        self._grid[y][x] = stone
        self._stone_count += 1

    def is_full(self) -> bool:
        return self._stone_count == self.size * self.size

    def find_winning_line(self, x: int, y: int) -> list[tuple[int, int]] | None:
        """Return the connected line (>= win_length) through (x, y), or None.

        Only lines through the given point are checked, so call this right after a move.
        Freestyle rule: five *or more* in a row wins.
        """
        stone = self.get(x, y)
        if stone is Stone.EMPTY:
            return None
        for dx, dy in DIRECTIONS:
            line = [(x, y)]
            for sign in (1, -1):
                cx, cy = x + dx * sign, y + dy * sign
                while self.in_bounds(cx, cy) and self.get(cx, cy) is stone:
                    line.append((cx, cy))
                    cx, cy = cx + dx * sign, cy + dy * sign
            if len(line) >= self.win_length:
                return sorted(line, key=lambda p: (p[0] * dx + p[1] * dy))
        return None

    def to_list(self) -> list[list[int]]:
        return [[int(s) for s in row] for row in self._grid]
