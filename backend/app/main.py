from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .database import Base, engine
from .routers import catalogue
from .seed import seed


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Runs once when the server starts: create tables and fill the fixed seniority levels.
    Base.metadata.create_all(engine)
    seed()
    yield


app = FastAPI(
    title="Group 6 External Recruiting API",
    version="0.1.0",
    description="Sprint 1: role catalogue (US-01).",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(catalogue.router)


@app.get("/health", tags=["Operations"])
def health():
    """Health endpoint (course requirement: observability)."""
    return {"status": "ok"}
