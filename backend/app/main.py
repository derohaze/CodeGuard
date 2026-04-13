from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.core.error_handlers import register_error_handlers
from app.core.logging import configure_logging
from app.infrastructure.database.mongo import close_mongo, initialize_mongo
from app.infrastructure.database.mongo_manager import ensure_backend_bootstrap
from app.infrastructure.learning.bootstrap import ensure_learning_bootstrap
from app.infrastructure.queue.redis import close_redis, initialize_redis
from app.presentation.api.v1.routes import health, learning, remediation, scans, sessions


settings = get_settings()
configure_logging()


@asynccontextmanager
async def lifespan(_: FastAPI):
    await initialize_mongo()
    await initialize_redis()
    await ensure_backend_bootstrap()
    await ensure_learning_bootstrap()
    yield
    await close_redis()
    await close_mongo()


app = FastAPI(title=settings.app_name, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.app_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, prefix="/api/v1", tags=["health"])
app.include_router(scans.router, prefix="/api/v1", tags=["scans"])
app.include_router(sessions.router, prefix="/api/v1", tags=["sessions"])
app.include_router(remediation.router, prefix="/api/v1", tags=["remediation"])
app.include_router(learning.router, prefix="/api/v1", tags=["learning"])
register_error_handlers(app)
