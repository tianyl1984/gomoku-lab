import os


class Settings:
    app_name: str = "Gomoku Lab"
    api_prefix: str = "/api"
    cors_origins: list[str] = os.getenv(
        "CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
    ).split(",")


settings = Settings()
