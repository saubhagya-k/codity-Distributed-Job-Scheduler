from fastapi import FastAPI
from app.api.health import router as health_router
from app.api.auth import router as auth_router
from app.api.projects import router as projects_router
from app.api.queues import router as queues_router
from app.api.jobs import router as jobs_router

app = FastAPI(title="Distributed Job Scheduler", version="0.1.0")

app.include_router(health_router, prefix="/api/v1")
app.include_router(auth_router, prefix="/api/v1")
app.include_router(projects_router, prefix="/api/v1")
app.include_router(queues_router, prefix="/api/v1")
app.include_router(jobs_router, prefix="/api/v1")  