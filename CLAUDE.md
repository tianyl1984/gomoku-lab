# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

Gomoku (五子棋) platform for **agent-vs-agent** play with no human involvement. Humans only create games and spectate in the browser. Agents are external programs that join over HTTP and follow the game over SSE. Agents learn the rules and protocol from `GET /api/game_rule.md`, which serves the hand-written, fixed-content `backend/app/docs/game_rule.md`. The spectator page's「Agent 接入方式」section generates a copyable prompt containing the server address (`window.location.origin`), the game_id, and the link to that document. `backend/examples/demo_agent.py` is a runnable reference implementation of the protocol. Docs and UI text are in Chinese.

## Commands

```bash
./scripts/dev.sh                      # start backend (:8000) + frontend (:5173) together; Ctrl+C stops both
BACKEND_PORT=9000 FRONTEND_PORT=5174 ./scripts/dev.sh
MOVE_TIMEOUT_SECONDS=6 ./scripts/dev.sh                # short move clock for testing timeouts

# backend (run inside backend/)
uv sync
uv run uvicorn app.main:app --reload --port 8000
uv run pytest                                          # all tests
uv run pytest tests/test_board.py::test_overline_counts_as_win   # single test
uv run python examples/demo_agent.py <game_id>         # run twice (two terminals) for a full game
uv run python examples/demo_agent.py <game_id> --idle  # joins but never moves -> timeout loss
uv add <pkg> / uv add --dev <pkg>                      # manage deps (never pip install)

# frontend (run inside frontend/)
npm run dev
npm run build
```

There is no linter or formatter configured yet, and no frontend tests.

## Architecture

**The backend is the single source of truth.** It decides seating, turn order, legality, wins and timeouts. The frontend is a read-only spectator that re-renders whatever state the server sends.

Backend layers (`backend/app/`), from innermost out:
- `game/board.py`: pure board logic. `find_winning_line(x, y)` only scans the 4 directions **through the last-placed stone**, so call it right after each move.
- `game/game.py`: `Game` covers seating, turn order, the move clock and the result, with no framework imports.
  - Agents are identified only by their secret. `Player` stores a SHA-256 hash of it, compared with `hmac.compare_digest`.
  - `join()` gives the first agent a random free color and is idempotent for the same secret.
  - The game starts when both seats are filled.
  - `check_timeout(now)` makes the side to move lose once `turn_started_at + move_timeout` passes. The clock resets after each move and never runs while the game is `waiting`.
  - Illegal placements (occupied or out of bounds) go through `_record_invalid_move`. It increments `Player.invalid_moves` and always re-raises `InvalidMoveError`, with the running count in the message. Reaching `max_invalid_moves` (default 5, cumulative, never reset) ends the game with `EndReason.INVALID_MOVES` before raising. An invalid move leaves the board, turn and clock untouched.
  - Methods take an optional `now` so tests can control time.
- `core/arena.py`: the process-global `arena`, which holds the in-memory game table, per-game SSE subscriber queues and event `seq` counters.
  - `join` / `play` / `expire_timeouts` mutate state and publish events.
  - Invalid moves publish nothing, except the `game_over` from the losing one. `arena.play` catches the `InvalidMoveError`, checks `status.is_over`, publishes, and re-raises.
  - `run_timeout_loop` is started in `main.py`'s lifespan.
- `schemas.py`: pydantic wire models shared by HTTP and SSE. This is the **only** place where `Stone` values are converted to and from `"black"` / `"white"`.
- `api/docs.py`: serves `docs/game_rule.md` as `text/markdown`. The document is a fixed file (it uses `<BASE_URL>` / `<GAME_ID>` placeholders), so **update it whenever the protocol changes**. `test_game_rule_doc` fails if any event type, status, end reason or error code is missing from it.
- `api/games.py`: routes. `api/errors.py` maps each domain exception to an HTTP status plus a machine-readable `code` (`{"detail", "code"}`) that agents branch on. To add an error, add a row to `ERRORS` rather than writing try/except in routes. FastAPI's `RequestValidationError` (malformed bodies or params) is also rewritten into this shape, with code `invalid_request`.

**Concurrency model (important):** there are no locks. Every arena method is synchronous and is only called from the event loop thread, by `async def` endpoints and the timeout loop. Nothing awaits during a mutation, so each call is atomic. Any endpoint that touches `arena` **must be `async def`**. A plain `def` endpoint would run in FastAPI's threadpool and race with everything else.

**SSE design:**
- `GET /api/games/{id}/events` uses FastAPI's built-in `EventSourceResponse`, which sends keepalive pings automatically.
- On subscribe, the queue is seeded with a `snapshot`. Every event (`player_joined`, `game_started`, `move`, `game_over`) carries the **full `GameState`**, so clients just replace their local state, and reconnecting needs no replay or `Last-Event-ID` handling.
- A winning move publishes `move` followed by `game_over`. The stream ends after `game_over`, or immediately after the snapshot if the game is already over (`GameEvent.is_terminal`).
- The game's existence is checked in a dependency, because an exception raised inside the generator can no longer change the HTTP status.
- The generator's `finally` unsubscribes the queue. It has been verified to run when a client disconnects mid-stream.

Rules: freestyle gomoku with **no forbidden moves**, where five *or more* in a row wins and a full board is a draw. Board size (5–25) and `win_length` are per-game parameters. `MOVE_TIMEOUT_SECONDS` (default 120) sets the move clock, and `MAX_INVALID_MOVES` (default 5) sets the illegal-placement limit.

State is in-memory only. `uvicorn --reload` restarts the process on backend file changes and **wipes all games**. The frontend then shows a "game not found (backend may have restarted)" message.

## Frontend

- Routes: `/` (lobby, which polls `GET /api/games`) and `/games/:id` (spectator page). The game URL is the share link, and Vite's dev server serves `index.html` for it.
- `GameView.vue` first fetches the game with a plain `GET`, because `EventSource` can't surface a 404. It then subscribes through `watchGame()` in `src/api/games.js`.
- `watchGame()` closes the `EventSource` itself on a terminal event. Otherwise the browser would auto-reconnect after the server closes the stream, looping forever.
- The countdown is computed from `turn_deadline` plus a clock offset taken from `state.server_time`. The offset and the local `now` must be sampled at the same moment, or the displayed time briefly goes above the limit.
- `GomokuBoard.vue` is a read-only SVG board.

## Conventions that span both sides

- Coordinates are `(x, y)`, 0-based, with the origin at the top-left: `x` is the column, `y` the row, and the board is `board[y][x]`. This holds for the API, the backend and the tests.
- Human-readable notation (`frontend/src/utils/notation.js`) is different: the column is a letter starting at A, and the row number counts **up from the bottom** (`size - y`). The move history shows both forms.
- The frontend calls the backend only through `/api`, which the Vite dev server proxies to `BACKEND_URL` (default `http://127.0.0.1:8000`). SSE works through the proxy, so agents can use either `:5173` or `:8000` as their base URL.

## scripts/dev.sh gotchas

Keep these properties if you edit the script. Each one fixed a real hang or leak:
- `set -m` puts each service in its own process group, and cleanup kills the **group** (`kill -- -$pid`). `uv run` and `npm run` don't reliably forward signals to their children.
- The log-prefix `sed` processes ignore INT/TERM and exit at EOF. If Ctrl+C kills them first, uvicorn's reloader hangs on shutdown writing to a broken pipe.
- Cleanup waits up to 5 seconds, then sends SIGKILL.
- The script must stay compatible with macOS's bash 3.2: no `wait -n`, and empty arrays are guarded under `set -u`.
- Don't stop it with `pkill -f "scripts/dev.sh"`. That pattern also matches the prefix subshells and reproduces the hang. Send a signal to the oldest matching PID instead: `kill -TERM $(pgrep -o -f "bash ./scripts/dev.sh")`.
