from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .database import Base, engine
from .routers import catalogue, group7, rates, suppliers, versions
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
    description=(
        "Sprint 1: role catalogue (US-01), suppliers and framework contracts incl. take-over from Group 7 (US-02), "
        "contract versions with rates and comparison (US-03), maximum daily rates per role and level (US-04)."
    ),
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(catalogue.router)
app.include_router(suppliers.router)
app.include_router(group7.router)
app.include_router(versions.router)
app.include_router(rates.router)


@app.get("/health", tags=["Operations"])
def health():
    """Health endpoint (course requirement: observability)."""
    return {"status": "ok"}
