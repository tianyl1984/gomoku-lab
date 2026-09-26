"""Gomoku agent whose every move is picked by the Dohnuts decision model.

Dohnuts (https://huggingface.co/DreamBlooms/Dohnuts-0.1.0-0.8B-GGUF) does not
generate text: it scores the candidates it is given and returns a probability
for each. This agent contains no move-evaluation logic at all. The code only
renders the board, lists the empty points (the legal moves) and lets the model
choose among them through its `choice` question type.

A `choice` question takes at most 128 candidates, and the model picks noticeably
better from a handful than from a long list, so the choice runs as a knockout:

    shuffle the empty points into groups of --group-size
    -> the model keeps the --advance most likely points of each group
    -> repeat until one group is left, whose top point is played

The protocol side (join, SSE, moves) is shared with demo_agent.py.

Usage (from backend/, with the Dohnuts server running on :7878):
    uv run python examples/dohnuts_agent.py <game_id> [--model-url http://127.0.0.1:7878]
"""

import argparse
import json
import random
import secrets
import sys
import time
import urllib.error
import urllib.request

from demo_agent import request, sse_events

COLUMNS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
SYMBOLS = {0: ".", 1: "X", 2: "O"}
MODEL_RETRIES = 3  # 含最后一次，失败则放弃


def notation(x: int, y: int, size: int) -> str:
    """Same as the frontend: column letter from A, row number counted up from the bottom."""
    return f"{COLUMNS[x]}{size - y}"


def render_board(board: list[list[int]]) -> str:
    size = len(board)
    lines = ["   " + " ".join(COLUMNS[:size])]
    for y, row in enumerate(board):
        lines.append(f"{size - y:>2} " + " ".join(SYMBOLS[cell] for cell in row))
    return "\n".join(lines)


class DohnutsClient:
    def __init__(self, base_url: str, api_key: str | None, questions_per_request: int):
        self.url = f"{base_url.rstrip('/')}/v1/systemone"
        self.api_key = api_key
        self.questions_per_request = questions_per_request

    def _post(self, body: dict) -> dict:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        req = urllib.request.Request(self.url, data=json.dumps(body).encode(), headers=headers)
        for attempt in range(1, MODEL_RETRIES):
            try:
                with urllib.request.urlopen(req, timeout=60) as res:
                    return json.load(res)
            except OSError as e:
                print(f"  model request failed ({e}), retrying")
                time.sleep(attempt)
        with urllib.request.urlopen(req, timeout=60) as res:
            return json.load(res)

    def choose(self, state: dict, instructions: str, groups: list[list[str]]) -> list[dict[str, float]]:
        """Ask one `choice` question per group; return each group's label -> probability."""
        results: list[dict[str, float]] = []
        for start in range(0, len(groups), self.questions_per_request):
            batch = groups[start : start + self.questions_per_request]
            questions = {
                f"g{i}": {"type": "choice", "instructions": instructions, "criteria": group}
                for i, group in enumerate(batch)
            }
            answers = self._post({"state": state, "questions": questions})["answers"]
            results.extend(answers[f"g{i}"]["probabilities"] for i in range(len(batch)))
        return results


def choose_move(model: DohnutsClient, state: dict, color: str, group_size: int, advance: int) -> tuple[int, int]:
    board, size = state["board"], state["size"]
    me, opp = ("X", "O") if color == "black" else ("O", "X")
    points = {
        notation(x, y, size): (x, y) for y in range(size) for x in range(size) if board[y][x] == 0
    }

    model_state = {
        "game": f"Gomoku (five in a row) on a {size}x{size} board",
        "board": render_board(board),
        "legend": "X = black, O = white, . = empty; columns A.. left to right, row numbers count up from the bottom",
        "you play": f"{color} ({me})",
    }
    if state["moves"]:
        last = state["moves"][-1]
        model_state["opponent's last move"] = notation(last["x"], last["y"], size)
    instructions = (
        f"Gomoku: {state['win_length']} or more stones in a row (horizontal, vertical or diagonal) wins. "
        f"You play {me}, the opponent plays {opp}. Which empty point is the best move for {me} now? "
        f"Complete your own five if you can; otherwise block the opponent's four or open three; "
        f"otherwise extend your own lines near the existing stones."
    )

    # 打乱顺序只是为了抵消模型对列表位置的偏好，不含任何对局面的判断
    pool = list(points)
    random.shuffle(pool)
    round_no = 1
    while len(pool) > 1:
        final = len(pool) <= group_size
        # 轮转分组让各组大小最多差 1，保证每组至少 2 个候选
        n_groups = 1 if final else -(-len(pool) // group_size)
        groups = [pool[i::n_groups] for i in range(n_groups)]
        keep = 1 if final else advance
        pool = []
        for probs in model.choose(model_state, instructions, groups):
            pool.extend(sorted(probs, key=probs.__getitem__, reverse=True)[:keep])
        print(f"  round {round_no}: {len(groups)} group(s) -> {len(pool)} point(s)")
        round_no += 1
    return points[pool[0]]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument("game_id")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--name", default=None)
    parser.add_argument("--model-url", default="http://127.0.0.1:7878", help="Dohnuts server")
    parser.add_argument("--api-key", default=None, help="Dohnuts API key, if the server was started with one")
    parser.add_argument("--group-size", type=int, default=8, help="candidates per choice question (2-128)")
    parser.add_argument("--advance", type=int, default=2, help="points each group sends to the next round")
    # 单次请求 token 过多（实测 8 个问题、约 5k token）会让 dohnuts-cli 进程直接崩溃，
    # 所以一轮的问题拆成多次请求顺序发送，不并发
    parser.add_argument("--questions-per-request", type=int, default=4)
    args = parser.parse_args()
    if not 2 <= args.group_size <= 128 or not 1 <= args.advance < args.group_size:
        parser.error("need 2 <= --group-size <= 128 and 1 <= --advance < --group-size")

    model = DohnutsClient(args.model_url, args.api_key, args.questions_per_request)
    api = f"{args.base_url.rstrip('/')}/api/games/{args.game_id}"
    secret = secrets.token_hex(16)
    name = args.name or f"dohnuts-{secret[:4]}"

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
        if state["current_player"] != color or len(state["moves"]) == acted_at:
            continue

        acted_at = len(state["moves"])
        started = time.monotonic()
        try:
            x, y = choose_move(model, state, color, args.group_size, args.advance)
        except OSError as e:
            sys.exit(f"[{name}] Dohnuts server unavailable at {args.model_url}: {e}")
        print(f"[{name}] move {acted_at + 1}: {notation(x, y, state['size'])} ({time.monotonic() - started:.1f}s)")
        try:
            request("POST", f"{api}/moves", secret, {"x": x, "y": y})
        except urllib.error.HTTPError as e:
            print(f"[{name}] move ({x}, {y}) rejected: {e.code} {e.read().decode()}")


if __name__ == "__main__":
    main()
