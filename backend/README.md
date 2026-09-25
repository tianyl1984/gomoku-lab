# gomoku-lab backend

FastAPI 服务，所有状态保存在内存中（进程重启即丢失）。

```bash
uv sync
uv run uvicorn app.main:app --reload --port 8000
```

- 健康检查：`GET /api/health`
- 接口文档：http://localhost:8000/docs
