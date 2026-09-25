# 构建上下文为仓库根目录（见 docker-compose.yml）

FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS build
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=0
WORKDIR /app
# 先只装依赖，源码变动时可复用这一层
COPY backend/pyproject.toml backend/uv.lock backend/.python-version ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project
COPY backend/app ./app

# 运行镜像不带 uv；两者的 python 都在 /usr/local/bin，.venv 可直接复用
FROM python:3.12-slim-bookworm
RUN useradd --system --no-create-home app
WORKDIR /app
COPY --from=build /app /app
ENV PATH="/app/.venv/bin:$PATH" PYTHONUNBUFFERED=1
USER app
EXPOSE 8000
# 必须单进程：对局状态保存在进程内存中，多个 worker 会各自持有一份对局表。
# SSE 长连接会拖住优雅退出，限定 5 秒后强制关闭。
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--timeout-graceful-shutdown", "5"]
