#!/usr/bin/env bash
# 本地开发：同时启动后端 (FastAPI) 与前端 (Vite)，Ctrl+C 一并退出。
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_PORT="${BACKEND_PORT:-8000}"
FRONTEND_PORT="${FRONTEND_PORT:-5173}"

command -v uv >/dev/null || { echo "uv 未安装：https://docs.astral.sh/uv/" >&2; exit 1; }
command -v npm >/dev/null || { echo "npm 未安装" >&2; exit 1; }

echo "==> 安装依赖"
(cd "$ROOT_DIR/backend" && uv sync --quiet)
[ -d "$ROOT_DIR/frontend/node_modules" ] || (cd "$ROOT_DIR/frontend" && npm install)

# 开启作业控制：每个后台服务独立成进程组，退出时按组整体结束（含 uv/npm 派生的子进程）
set -m

pids=()
cleanup() {
  local code=$?
  trap - INT TERM EXIT
  echo
  echo "==> 停止服务"
  for pid in ${pids[@]+"${pids[@]}"}; do
    kill -TERM -- "-$pid" 2>/dev/null || true
  done
  wait 2>/dev/null || true
  exit "$code"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

# 为每行输出加前缀，区分两个服务的日志
prefix() { sed -u "s/^/[$1] /"; }

echo "==> 启动后端 http://127.0.0.1:${BACKEND_PORT}"
(cd "$ROOT_DIR/backend" && exec uv run uvicorn app.main:app --reload \
  --host 127.0.0.1 --port "$BACKEND_PORT") > >(prefix backend) 2>&1 &
pids+=($!)

echo "==> 启动前端 http://localhost:${FRONTEND_PORT}"
(cd "$ROOT_DIR/frontend" && BACKEND_URL="http://127.0.0.1:${BACKEND_PORT}" \
  exec npm run dev -- --port "$FRONTEND_PORT" --strictPort) > >(prefix frontend) 2>&1 &
pids+=($!)

# 任意一个进程退出则全部退出
while :; do
  for pid in "${pids[@]}"; do
    kill -0 "$pid" 2>/dev/null || { echo "==> 进程 $pid 已退出"; exit 1; }
  done
  sleep 1
done
