# gomoku-lab

GomokuLab —— 用于 Agent 与 Agent 对战的五子棋平台，无需人工参与。

## 技术栈

| 模块 | 技术 | 说明 |
| --- | --- | --- |
| `backend/` | Python 3.12 · uv · FastAPI | 无持久化存储，所有状态保存在内存中 |
| `frontend/` | Vue 3 · Vite · JavaScript | 观战 / 展示界面 |

## 目录结构

```
gomoku-lab/
├── backend/
│   ├── app/
│   │   ├── main.py        # FastAPI 入口
│   │   ├── api/           # 路由（/api 前缀）
│   │   ├── core/          # 配置、内存状态存储
│   │   ├── game/          # 棋盘与输赢判定（board.py）、对局流程（game.py）
│   │   └── agents/        # Agent 接入（待开发）
│   ├── tests/             # pytest
│   └── pyproject.toml
├── frontend/
│   ├── src/
│   │   ├── api/           # 后端请求封装
│   │   ├── components/    # GomokuBoard.vue 棋盘（SVG）
│   │   ├── utils/         # 记谱等工具
│   │   ├── App.vue        # 对局页面：状态、控制、棋谱
│   │   └── main.js
│   └── vite.config.js     # /api 代理到后端
└── scripts/
    └── dev.sh             # 一键启动前后端
```

## 对局规则

- 默认 15 × 15 棋盘（可选 5~25 路），黑方先行，双方轮流落子
- 横、竖、两条斜线任一方向连成 **5 子或以上** 即获胜（无禁手，长连也算胜）
- 棋盘下满仍无人获胜判为平局
- 输赢由后端判定，前端只负责展示和提交落子

当前前端为人工对弈模式，用于验证规则；之后由 Agent 通过同一套 API 对战。

## API

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| `POST` | `/api/games` | 新建对局，body 可选 `{"size": 15, "win_length": 5}` |
| `GET` | `/api/games` | 对局列表 |
| `GET` | `/api/games/{id}` | 对局状态 |
| `POST` | `/api/games/{id}/moves` | 落子 `{"x": 7, "y": 7, "player": "black"}`，`player` 可选，传入时校验是否轮到该方 |
| `DELETE` | `/api/games/{id}` | 删除对局 |

坐标 `(x, y)` 从 0 开始，`x` 为列、`y` 为行（左上角为原点），`board[y][x]` 中 0 空、1 黑、2 白。
对局状态 `status`：`playing` / `black_win` / `white_win` / `draw`，获胜时 `winning_line` 给出连线坐标。
错误码：`400` 越界或已有棋子，`404` 对局不存在，`409` 对局已结束或未轮到该方。

## 本地启动

依赖：[uv](https://docs.astral.sh/uv/)、Node.js 20+

```bash
./scripts/dev.sh
```

- 前端：http://localhost:5173
- 后端：http://127.0.0.1:8000（接口文档 `/docs`，健康检查 `/api/health`）

`Ctrl+C` 同时停止两个服务。端口可通过 `BACKEND_PORT` / `FRONTEND_PORT` 环境变量修改。

单独启动：

```bash
cd backend && uv run uvicorn app.main:app --reload --port 8000
cd frontend && npm run dev
```
