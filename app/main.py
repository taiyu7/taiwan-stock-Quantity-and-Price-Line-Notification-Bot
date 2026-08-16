from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from sqlalchemy.orm import Session

from app.bot import BotService
from app.config import get_settings
from app.db import SessionLocal, init_db
from app.line_client import LineClient
from app.scheduler import AlertScheduler


settings = get_settings()
bot = BotService()
line = LineClient()
scheduler = AlertScheduler()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    if settings.enable_scheduler:
        scheduler.start()
    yield
    if settings.enable_scheduler:
        await scheduler.stop()


app = FastAPI(title="Taiwan Stock LINE Alert Bot", lifespan=lifespan)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/line/webhook")
async def line_webhook(
    request: Request,
    x_line_signature: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    body = await request.body()
    if not line.verify_signature(body, x_line_signature):
        raise HTTPException(status_code=403, detail="Invalid LINE signature")

    payload = await request.json()
    for event in payload.get("events", []):
        bot.handle_event(db, event)
    return {"status": "ok"}
