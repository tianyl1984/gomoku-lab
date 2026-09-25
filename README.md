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
│   │   ├── game/          # 棋盘与规则（待开发）
│   │   └── agents/        # Agent 接入（待开发）
│   └── pyproject.toml
├── frontend/
│   ├── src/
│   │   ├── api/           # 后端请求封装
│   │   ├── App.vue
│   │   └── main.js
│   └── vite.config.js     # /api 代理到后端
└── scripts/
    └── dev.sh             # 一键启动前后端
```

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
