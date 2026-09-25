from fastapi import APIRouter

from app.api import docs, games, health

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(docs.router)
api_router.include_router(games.router)
