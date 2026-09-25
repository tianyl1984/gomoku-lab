"""Reference gomoku agent: join a game, follow it over SSE, and play with a simple heuristic.

Standard library only, so it doubles as protocol documentation:

    1. generate a local secret           -> identifies this agent for the whole game
    2. POST /api/games/{id}/join         -> server assigns a color (header X-Agent-Secret)
    3. GET  /api/games/{id}/events       -> SSE; every event carries the full game state
    4. POST /api/games/{id}/moves        -> when state.current_player == my color

Usage (from backend/):
    uv run python examples/demo_agent.py <game_id> [--name NAME] [--delay 0.5]
    uv run python examples/demo_agent.py <game_id> --idle   # join but never move (timeout test)
"""

import argparse
import json
import random
import secrets
import sys
import time
import urllib.error
import urllib.request
from collections.abc import Iterator

DIRECTIONS = ((1, 0), (0, 1), (1, 1), (1, -1))


def request(method: str, url: str, secret: str, body: dict | None = None) -> dict:
    req = urllib.request.Request(
        url,
        method=method,
        data=json.dumps(body or {}).encode(),
        headers={"Content-Type": "application/json", "X-Agent-Secret": secret},
    )
    with urllib.request.urlopen(req) as res:
        return json.load(res)


def sse_events(url: str) -> Iterator[tuple[str, dict]]:
    """Yield (event_type, data) from an SSE stream until the server closes it."""
    with urllib.request.urlopen(url) as res:
        event, data = "message", []
        for raw in res:
            line = raw.decode().rstrip("\r\n")
            if not line:
                if data:
                    yield event, json.loads("\n".join(data))
                event, data = "message", []
            elif line.startswith(":"):
                continue  # keepalive comment
            else:
                key, _, value = line.partition(":")
                value = value.removeprefix(" ")
                if key == "event":
                    event = value
                elif key == "data":
                    data.append(value)


def line_score(board: list[list[int]], x: int, y: int, stone: int, win_length: int) -> int:
    """How good it would be for `stone` to occupy (x, y)."""
    size = len(board)
    total = 0
    for dx, dy in DIRECTIONS:
        count, open_ends = 1, 0
        for sign in (1, -1):
            cx, cy = x + dx * sign, y + dy * sign
            while 0 <= cx < size and 0 <= cy < size and board[cy][cx] == stone:
                count += 1
                cx, cy = cx + dx * sign, cy + dy * sign
            if 0 <= cx < size and 0 <= cy < size and board[cy][cx] == 0:
                open_ends += 1
        if count >= win_length:
            return 10**9
        if open_ends:
            total += 10 ** (count * 2 + open_ends - 2)
    return total


def choose_move(state: dict, color: str) -> tuple[int, int]:
    board, size = state["board"], state["size"]
    me = 1 if color == "black" else 2
    opp = 3 - me
    if not state["moves"]:
        return size // 2, size // 2

    # 只考虑已有棋子周围两格内的空位
    candidates = {
        (x + dx, y + dy)
        for y in range(size)
        for x in range(size)
        if board[y][x]
        for dx in range(-2, 3)
        for dy in range(-2, 3)
        if 0 <= x + dx < size and 0 <= y + dy < size and not board[y + dy][x + dx]
    }

    # 进攻权重 2：自己能连五 (1e9*2) 仍优先于一切，堵对方连五 (1e9) 仍优先于自己做活四 (1e8*2)；
    # 权重过低时双方只顾防守，常常下满棋盘平局
    def score(p: tuple[int, int]) -> float:
        attack = line_score(board, *p, me, state["win_length"])
        defense = line_score(board, *p, opp, state["win_length"])
        return attack * 2 + defense + random.random()

    return max(candidates, key=score)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument("game_id")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--name", default=None)
    parser.add_argument("--delay", type=float, default=0.5, help="seconds to wait before each move")
    parser.add_argument("--idle", action="store_true", help="join but never move")
    args = parser.parse_args()

    api = f"{args.base_url.rstrip('/')}/api/games/{args.game_id}"
    secret = secrets.token_hex(16)
    name = args.name or f"demo-{secret[:4]}"

    try:
        joined = request("POST", f"{api}/join", secret, {"name": name})
    except urllib.error.HTTPError as e:
        sys.exit(f"[{name}] join failed: {e.code} {e.read().decode()}")
    color = joined["color"]
    print(f"[{name}] joined as {color}")

    acted_at = -1  # 已针对第几手局面落过子，避免同一局面重复落子
    for event, data in sse_events(f"{api}/events"):
        state = data["state"]
        if event == "game_started":
            print(f"[{name}] game started")
        if event == "game_expired":
            print(f"[{name}] game expired: no opponent joined in time")
            return
        if state["status"] not in ("waiting", "playing"):
            result = "draw" if state["winner"] is None else f"{state['winner']} wins"
            outcome = "WIN" if state["winner"] == color else "LOSS" if state["winner"] else "DRAW"
            print(f"[{name}] {outcome}: {result} ({state['end_reason']}, {len(state['moves'])} moves)")
            return
        if args.idle or state["current_player"] != color or len(state["moves"]) == acted_at:
            continue

        acted_at = len(state["moves"])
        time.sleep(args.delay)
        x, y = choose_move(state, color)
        try:
            request("POST", f"{api}/moves", secret, {"x": x, "y": y})
        except urllib.error.HTTPError as e:
            print(f"[{name}] move ({x}, {y}) rejected: {e.code} {e.read().decode()}")


if __name__ == "__main__":
    main()
