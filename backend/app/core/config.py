import os


class Settings:
    app_name: str = "Gomoku Lab"
    api_prefix: str = "/api"
    cors_origins: list[str] = os.getenv(
        "CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
    ).split(",")
    # 行棋方超过该时长未落子即判负
    move_timeout_seconds: float = float(os.getenv("MOVE_TIMEOUT_SECONDS", "120"))
    # 同一方累计非法落子（已占用 / 越界）达到该次数即判负
    max_invalid_moves: int = int(os.getenv("MAX_INVALID_MOVES", "5"))
    # 等待中的对局超过该时长没有新 agent 加入即被销毁，释放内存
    join_timeout_seconds: float = float(os.getenv("JOIN_TIMEOUT_SECONDS", "1800"))


settings = Settings()
