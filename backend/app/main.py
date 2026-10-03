from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import inspect, text

from app.api.router import api_router
from app.config import settings
from app.database import Base, SessionLocal, engine
from app.services.seed import seed_if_empty


def _ensure_lane_blocked_column() -> None:
    """Databases created before lane blocking lack the column; add it once."""
    with engine.begin() as conn:
        cols = {c["name"] for c in inspect(conn).get_columns("lanes")}
        if "blocked" not in cols:
            conn.execute(text("ALTER TABLE lanes ADD COLUMN blocked BOOLEAN NOT NULL DEFAULT FALSE"))


@asynccontextmanager
async def lifespan(_app: FastAPI):
    Base.metadata.create_all(bind=engine)
    _ensure_lane_blocked_column()
    if settings.seed_on_empty:
        db = SessionLocal()
        try:
            seed_if_empty(db)
        finally:
            db.close()
    yield


app = FastAPI(title="VendFill", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(api_router, prefix="/api")
