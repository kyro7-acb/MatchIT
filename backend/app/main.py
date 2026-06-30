"""
backend/app/main.py
--------------------
FastAPI application entry point.
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import CORS_ORIGINS
from app.db.session import init_db
from app.api.upload import router as upload_router
from app.api.match  import router as match_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Create DB tables on startup."""
    await init_db()
    yield


app = FastAPI(
    title       = "matchIT API",
    description = "Automated Invoice-to-Ledger Matching Engine",
    version     = "1.0.0",
    lifespan    = lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins     = CORS_ORIGINS,
    allow_credentials = True,
    allow_methods     = ["*"],
    allow_headers     = ["*"],
)

app.include_router(upload_router, prefix="/api", tags=["Upload"])
app.include_router(match_router,  prefix="/api", tags=["Match"])


@app.get("/health")
async def health():
    return {"status": "ok", "service": "matchIT"}
