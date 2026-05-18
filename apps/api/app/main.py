"""FastAPI entry. Wires routers and lifespan."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from chief_editor.db import init_db
from chief_editor.logging_config import configure_logging, get_logger
from chief_editor.settings import get_settings

from .routers import (
    analytics,
    approvals,
    briefs,
    calendar,
    candidates,
    collect,
    demo,
    generation_runs,
    health,
    publishing,
    readiness,
    secrets,
    sources,
    status,
    style_profile,
    trends,
    worker,
)

configure_logging(service="api")
log = get_logger("chief_editor.api")


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    settings = get_settings()
    log.info(
        "api.boot",
        env=settings.app_env,
        mock_mode=settings.mock_mode,
        live_mode=settings.live_mode,
        dry_run_publish=settings.dry_run_publish,
        publishing_enabled=settings.publishing_enabled,
        llm_provider=settings.llm_provider,
        cors_origins=settings.cors_origins,
        public_api_url=settings.public_api_url or "(unset)",
    )
    yield
    log.info("api.shutdown")


app = FastAPI(
    title="AI Chief Editor OS",
    version="0.1.0",
    description="Premium AI content intelligence platform.",
    lifespan=lifespan,
)

_settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=_settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(status.router)
app.include_router(sources.router)
app.include_router(trends.router)
app.include_router(collect.router)
app.include_router(briefs.router)
app.include_router(candidates.router)
app.include_router(approvals.router)
app.include_router(publishing.router)
app.include_router(calendar.router)
app.include_router(analytics.router)
app.include_router(style_profile.router)
app.include_router(demo.router)
app.include_router(readiness.router)
app.include_router(secrets.router)
app.include_router(generation_runs.router)
app.include_router(worker.router)
