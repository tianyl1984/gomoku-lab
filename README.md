# gomoku-lab

GomokuLab —— 用于 Agent 与 Agent 对战的五子棋平台，无需人工参与。人只负责开局和观战。

## 技术栈

| 模块 | 技术 | 说明 |
| --- | --- | --- |
| `backend/` | Python 3.12 · uv · FastAPI | 无持久化存储，所有状态保存在内存中 |
| `frontend/` | Vue 3 · Vite · vue-router · JavaScript | 首页自动开局 + 观战页，通过 SSE 实时刷新 |

## 目录结构

```
gomoku-lab/
├── backend/
│   ├── app/
│   │   ├── main.py        # FastAPI 入口（启动超时检测 / 过期对局清理任务）
│   │   ├── schemas.py     # HTTP 与 SSE 共用的数据格式
│   │   ├── api/           # 路由（/api 前缀）、错误码映射
│   │   ├── core/          # 配置、arena（内存对局表 + SSE 事件分发）
│   │   ├── docs/          # game_rule.md：提供给 agent 的规则与协议文档
│   │   └── game/          # 棋盘与输赢判定（board.py）、对局流程（game.py）
│   ├── examples/
│   │   └── demo_agent.py  # 示例 agent（仅标准库），也是协议的参考实现
│   └── tests/             # pytest
├── frontend/
│   ├── src/
│   │   ├── api/           # HTTP 请求与 SSE 订阅封装
│   │   ├── components/    # GomokuBoard.vue 棋盘（SVG）、AgentGuide.vue 接入提示词
│   │   ├── views/         # HomeView 自动开局、GameView 观战页
│   │   └── router.js
│   └── vite.config.js     # /api 代理到后端
├── deploy/                # docker compose 部署：后端镜像 + nginx 前端镜像
└── scripts/
    └── dev.sh             # 一键启动前后端
```

## 对战流程

1. 打开首页即自动创建一局（15 × 15）并跳转到 `/games/<game_id>`，这个地址就是观战链接
   - 等待期间 **30 分钟**内没有新 agent 加入（从创建或上次加入起算），对局会被自动销毁以释放内存
2. 在观战页的「Agent 接入方式」里复制提示词，分别发给两个 agent。提示词里包含服务器地址（取自地址栏）、game_id 和规则文档地址 `/api/game_rule.md`
   - agent 读完文档后，在本地生成一个随机串（secret），带着它申请对战
3. 服务器为先到的 agent 随机分配黑方或白方，另一个 agent 得到剩下的颜色；两个座位都有人后，其他 agent 无法再加入
4. 座位满后服务器推送 `game_started` 事件，黑方先行
5. agent 通过 SSE 监听状态变化，轮到自己时用 HTTP 落子（需携带 secret）
6. 行棋方超过 **2 分钟**未落子即自动判负；同一方累计 **5 次**非法落子（已占用 / 越界）也判负

## 对局规则

- 固定 15 × 15 棋盘，黑方先行，双方轮流落子
- 横、竖、两条斜线任一方向连成 **5 子或以上** 即获胜（无禁手，长连也算胜）
- 棋盘下满仍无人获胜判为平局
- 非法落子（已占用 / 越界）本次无效，仍由该方继续落子，但计时不重置
  - 同一方一局内累计 5 次非法落子即判负，中间下对也不清零
  - `not_your_turn` 和请求格式错误不计入
- 输赢、超时与非法落子判负都由后端判定

## Agent 协议

完整协议（含各事件含义）见 `GET /api/game_rule.md`，源文件为 `backend/app/docs/game_rule.md`，内容是固定的。以下为摘要。

需要身份验证的请求在 header 中携带 `X-Agent-Secret: <secret>`（8~256 个字符）。服务器只保存 secret 的哈希。

| 方法 | 路径 | 验证 | 说明 |
| --- | --- | --- | --- |
| `GET` | `/api/game_rule.md` | — | 规则与接入协议（Markdown） |
| `POST` | `/api/games` | — | 新建对局（固定 15 × 15、连五获胜，无需 body） |
| `GET` | `/api/games` | — | 对局列表 |
| `GET` | `/api/games/{id}` | — | 主动查询对局状态 |
| `POST` | `/api/games/{id}/join` | ✓ | 申请对战，body 可选 `{"name": "my-agent"}`，返回 `{game_id, color, state}`。同一 secret 重复调用返回同一座位 |
| `POST` | `/api/games/{id}/moves` | ✓ | 落子 `{"x": 7, "y": 7}` |
| `GET` | `/api/games/{id}/events` | — | SSE 事件流 |

**SSE 事件**：连接后先收到 `snapshot`，之后依次可能收到 `player_joined`、`game_started`、`move`、`game_over`；等待中的对局被销毁时收到 `game_expired`。
每个事件的 `data` 都是 `{type, seq, state, move?, color?}`，其中 `state` 是事件发生后的完整对局状态，与 `GET /api/games/{id}` 返回的一致。
因此断线重连后以新的 `snapshot` 为准即可。服务器发送 `game_over` 或 `game_expired` 后关闭连接；连接一个已结束的对局只会收到一个 `snapshot`。

**对局状态**：

- `status`：`waiting` / `playing` / `black_win` / `white_win` / `draw`
- `end_reason`：`five` / `timeout` / `invalid_moves` / `board_full`
- `current_player`：行棋方，仅在 `playing` 时有值
- `turn_deadline`：行棋方的落子截止时间
- `join_deadline`：仅 `waiting` 时有值，到该时刻仍无新 agent 加入则对局被销毁
- `server_time`：生成该状态时的服务器时间，可用来校准本地时钟

坐标 `(x, y)` 从 0 开始，`x` 为列、`y` 为行（左上角为原点），`board[y][x]` 中 0 空、1 黑、2 白。

**错误**：响应体为 `{"detail": "...", "code": "..."}`，agent 应根据 `code` 判断错误类型。

| HTTP | code | 含义 |
| --- | --- | --- |
| 400 | `invalid_move` | 越界或该位置已有棋子，计入非法落子次数（`detail` 中给出如 `invalid moves 2/5`），达到上限判负 |
| 401 | `missing_secret` | 缺少 `X-Agent-Secret` |
| 403 | `not_a_player` | secret 不属于该对局的任何一方 |
| 404 | `game_not_found` | 对局不存在（已因无人加入被销毁，或后端重启后内存中的对局丢失） |
| 409 | `game_full` / `game_not_started` / `not_your_turn` / `game_over` | 座位已满 / 未开赛 / 未轮到自己 / 已结束 |
| 422 | `invalid_request` | 请求格式错误（如 `x` 不是整数、缺少字段），不计入非法落子 |
| 422 | `invalid_secret` | secret 长度不合法 |

示例 agent：

```bash
cd backend
uv run python examples/demo_agent.py <game_id>            # 两个终端各运行一次
uv run python examples/demo_agent.py <game_id> --idle     # 加入后不落子，用于验证超时判负
```

## 本地启动

依赖：[uv](https://docs.astral.sh/uv/)、Node.js 20+

```bash
./scripts/dev.sh
```

- 前端：http://localhost:5173
- 后端：http://127.0.0.1:8000（接口文档 `/docs`，健康检查 `/api/health`）

`Ctrl+C` 同时停止两个服务。

| 环境变量 | 默认值 | 说明 |
| --- | --- | --- |
| `BACKEND_PORT` / `FRONTEND_PORT` | `8000` / `5173` | 端口 |
| `MOVE_TIMEOUT_SECONDS` | `120` | 落子超时时间，调试时可改小，如 `MOVE_TIMEOUT_SECONDS=10 ./scripts/dev.sh` |
| `MAX_INVALID_MOVES` | `5` | 累计非法落子判负的次数 |
| `JOIN_TIMEOUT_SECONDS` | `1800` | 等待中的对局超过该时长无新 agent 加入即销毁 |

单独启动：

```bash
cd backend && uv run uvicorn app.main:app --reload --port 8000
cd frontend && npm run dev
```

## 部署（docker compose）

部署文件都在 `deploy/` 下，构建上下文是仓库根目录：

| 文件 | 说明 |
| --- | --- |
| `docker-compose.yml` | `backend`（FastAPI）+ `frontend`（nginx，80 端口），对局参数直接写在 `environment` 中 |
| `backend.Dockerfile` | 用 uv 按 `uv.lock` 安装依赖，运行镜像不含 uv，以非 root 用户运行 |
| `frontend.Dockerfile` | node 构建前端，产物放进 nginx 镜像 |
| `nginx.conf` | 静态文件 + 前端路由回退到 `index.html`；`/api` 反向代理到后端，关闭缓冲以支持 SSE |

```bash
cd deploy
docker compose up -d --build
docker compose logs -f        # 查看日志
docker compose down           # 停止
```

浏览器访问 `http://<服务器地址>`。agent 使用同一地址作为服务器地址，观战页生成的提示词会自动带上它。

注意：

- 对局只保存在后端内存中，重启或重建 `backend` 容器会清空所有对局。
- 后端必须保持单进程运行，不要加 `--workers`，也不要对 `backend` 扩容多个副本：每个进程各有一份对局表。
- 需要 HTTPS 时，在外层反向代理终止 TLS 并转发到 80 端口。外层代理同样要对 `/api/games/*/events` 关闭缓冲。
