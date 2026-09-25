import asyncio
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.errors import register_error_handlers
from app.api.router import api_router
from app.core.arena import arena
from app.core.config import settings


@asynccontextmanager
async def lifespan(_: FastAPI):
    timeout_task = asyncio.create_task(arena.run_timeout_loop())
    yield
    timeout_task.cancel()
    with suppress(asyncio.CancelledError):
        await timeout_task


app = FastAPI(title=settings.app_name, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

register_error_handlers(app)
app.include_router(api_router, prefix=settings.api_prefix)
