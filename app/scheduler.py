from __future__ import annotations

import asyncio
from datetime import datetime, time
from zoneinfo import ZoneInfo

from sqlalchemy import select

from app.config import get_settings
from app.db import SessionLocal
from app.line_client import LineClient
from app.models import AlertRule
from app.rules import compare, format_number
from app.twse_client import TwseClient


class AlertScheduler:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.line = LineClient()
        self.twse = TwseClient()
        self._task: asyncio.Task[None] | None = None
        self._stopping = asyncio.Event()

    def start(self) -> None:
        if self._task is None:
            self._task = asyncio.create_task(self._run())

    async def stop(self) -> None:
        self._stopping.set()
        if self._task:
            await self._task

    async def _run(self) -> None:
        while not self._stopping.is_set():
            if is_market_open(self.settings.timezone):
                await asyncio.to_thread(self.check_once)
            try:
                await asyncio.wait_for(
                    self._stopping.wait(),
                    timeout=max(5, self.settings.check_interval_seconds),
                )
            except asyncio.TimeoutError:
                pass

    def check_once(self) -> None:
        with SessionLocal() as db:
            rules = db.scalars(
                select(AlertRule).where(AlertRule.active.is_(True)).order_by(AlertRule.id)
            ).all()
            for rule in rules:
                quote = self.twse.fetch_quote(rule.stock_code, rule.market)
                if quote is None:
                    continue

                value = quote.price if rule.metric == "price" else quote.volume
                rule.last_checked_at = datetime.utcnow()
                rule.last_value = value

                if compare(value, rule.operator, rule.threshold):
                    rule.active = False
                    rule.triggered_at = datetime.utcnow()
                    db.commit()
                    self.line.push_text(rule.line_user_id, build_alert_message(rule, value))
                else:
                    db.commit()


def is_market_open(timezone: str) -> bool:
    now = datetime.now(ZoneInfo(timezone))
    if now.weekday() >= 5:
        return False
    return time(9, 0) <= now.time() <= time(13, 30)


def build_alert_message(rule: AlertRule, value: float) -> str:
    label = "價格" if rule.metric == "price" else "成交量"
    unit = "元" if rule.metric == "price" else "張"
    return (
        f"台股提醒觸發\n"
        f"{rule.stock_name}({rule.stock_code})\n"
        f"{label}目前 {format_number(value)} {unit}\n"
        f"條件：{label} {rule.operator} {format_number(rule.threshold)} {unit}"
    )
