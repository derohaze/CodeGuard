import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.core.error_handlers import register_error_handlers
from app.core.logging import configure_logging
from app.infrastructure.coverage.store import CoverageStore
from app.infrastructure.database.mongo import close_mongo, initialize_mongo
from app.infrastructure.database.mongo_manager import ensure_backend_bootstrap
from app.infrastructure.intelligence.continuous.store import IntelligenceStore
from app.infrastructure.learning.bootstrap import ensure_learning_bootstrap
from app.infrastructure.queue.redis import close_redis, initialize_redis
from app.infrastructure.skills.registry import SkillRegistry
from app.presentation.api.v1.routes import (
    coverage,
    health,
    learning,
    remediation,
    scans,
    sessions,
    settings as settings_routes,
    skills,
)


settings = get_settings()
configure_logging()

_skill_registry: SkillRegistry | None = None
_coverage_store: CoverageStore | None = None
_intelligence_store: IntelligenceStore | None = None


def get_skill_registry() -> SkillRegistry:
    global _skill_registry
    return _skill_registry


def get_coverage_store() -> CoverageStore:
    global _coverage_store
    return _coverage_store


def get_intelligence_store() -> IntelligenceStore:
    global _intelligence_store
    return _intelligence_store


@asynccontextmanager
async def lifespan(_: FastAPI):
    await initialize_mongo()
    await initialize_redis()
    await ensure_backend_bootstrap()
    await ensure_learning_bootstrap()

    global _skill_registry, _coverage_store, _intelligence_store

    reg = SkillRegistry()
    reg.load_builtin_skills()
    _skill_registry = reg
    skills.init_skills(reg)

    artifacts = settings.artifacts_dir
    os.makedirs(artifacts, exist_ok=True)
    _coverage_store = CoverageStore(os.path.join(artifacts, "coverage.json"))
    _coverage_store.load()
    coverage.init_coverage(artifacts)

    _intelligence_store = IntelligenceStore(project_dir=artifacts)

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
app.include_router(settings_routes.router, prefix="/api/v1", tags=["settings"])
app.include_router(skills.router, prefix="/api/v1", tags=["skills"])
app.include_router(coverage.router, prefix="/api/v1", tags=["coverage"])
register_error_handlers(app)
