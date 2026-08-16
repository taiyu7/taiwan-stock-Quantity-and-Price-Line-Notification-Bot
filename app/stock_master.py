from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass
from datetime import datetime

import requests
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import StockMasterEntry, SyncState


TWSE_LISTED_URL = "https://openapi.twse.com.tw/v1/opendata/t187ap03_L"
TPEX_LISTED_URL = "https://www.tpex.org.tw/openapi/v1/mopsfin_t187ap03_O"
logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Stock:
    code: str
    name: str
    market: str
    full_name: str = ""

    @property
    def display_name(self) -> str:
        if not self.name:
            return self.code
        return f"{self.name}({self.code})"


@dataclass(frozen=True)
class ResolveResult:
    status: str
    stock: Stock | None = None
    candidates: tuple[Stock, ...] = ()

    @classmethod
    def found(cls, stock: Stock) -> "ResolveResult":
        return cls(status="found", stock=stock)

    @classmethod
    def not_found(cls) -> "ResolveResult":
        return cls(status="not_found")

    @classmethod
    def ambiguous(cls, candidates: list[Stock]) -> "ResolveResult":
        return cls(status="ambiguous", candidates=tuple(candidates))


class StockMasterClient:
    def __init__(self) -> None:
        self.settings = get_settings()
        self._stocks: list[Stock] = []
        self._loaded_at = 0.0

    def resolve(self, identifier: str, db: Session | None = None) -> ResolveResult:
        identifier = normalize_text(identifier)
        if not identifier:
            return ResolveResult.not_found()

        stocks = self._load_stocks(db)
        if re.fullmatch(r"\d{4,6}", identifier):
            for stock in stocks:
                if stock.code == identifier:
                    return ResolveResult.found(stock)
            return ResolveResult.not_found()

        exact = [
            stock
            for stock in stocks
            if normalize_text(stock.name) == identifier
            or normalize_text(stock.full_name) == identifier
        ]
        if len(exact) == 1:
            return ResolveResult.found(exact[0])
        if len(exact) > 1:
            return ResolveResult.ambiguous(exact)

        contains = [
            stock
            for stock in stocks
            if identifier in normalize_text(stock.name)
            or identifier in normalize_text(stock.full_name)
        ]
        if len(contains) == 1:
            return ResolveResult.found(contains[0])
        if len(contains) > 1:
            return ResolveResult.ambiguous(contains[:10])
        return ResolveResult.not_found()

    def _load_stocks(self, db: Session | None = None) -> list[Stock]:
        now = time.time()
        if self._stocks and now - self._loaded_at < self.settings.stock_master_cache_seconds:
            return self._stocks

        if db:
            stored = self._load_from_db(db)
            if stored and self._db_cache_is_fresh(db):
                self._stocks = stored
                self._loaded_at = now
                return self._stocks

        stocks = self._fetch_market(TWSE_LISTED_URL, "tse")
        stocks.extend(self._fetch_market(TPEX_LISTED_URL, "otc"))
        if stocks:
            self._stocks = dedupe_stocks(stocks)
            self._loaded_at = now
            if db:
                self._save_to_db(db, self._stocks)
        elif db:
            stored = self._load_from_db(db)
            if stored:
                self._stocks = stored
                self._loaded_at = now
        return self._stocks

    def _load_from_db(self, db: Session) -> list[Stock]:
        rows = db.scalars(select(StockMasterEntry).order_by(StockMasterEntry.market, StockMasterEntry.code)).all()
        return [
            Stock(code=row.code, name=row.name, market=row.market, full_name=row.full_name)
            for row in rows
        ]

    def _db_cache_is_fresh(self, db: Session) -> bool:
        state = db.get(SyncState, "stock_master")
        if not state:
            return False
        age = datetime.utcnow() - state.updated_at
        return age.total_seconds() < self.settings.stock_master_cache_seconds

    def _save_to_db(self, db: Session, stocks: list[Stock]) -> None:
        db.execute(delete(StockMasterEntry))
        now = datetime.utcnow()
        db.add_all(
            StockMasterEntry(
                code=stock.code,
                name=stock.name,
                market=stock.market,
                full_name=stock.full_name,
                updated_at=now,
            )
            for stock in stocks
        )
        state = db.get(SyncState, "stock_master")
        if state is None:
            state = SyncState(key="stock_master")
            db.add(state)
        state.updated_at = now
        db.commit()

    def _fetch_market(self, url: str, market: str) -> list[Stock]:
        try:
            response = requests.get(
                url,
                headers={"User-Agent": "line-stock-alert-bot/1.0"},
                timeout=15,
            )
            response.raise_for_status()
            rows = response.json()
        except Exception:
            logger.exception("Failed to fetch stock master url=%s", url)
            return []

        stocks: list[Stock] = []
        for row in rows if isinstance(rows, list) else []:
            code = first_value(row, "公司代號", "有價證券代號", "代號", "股票代號")
            name = first_value(row, "公司簡稱", "有價證券名稱", "名稱", "股票名稱")
            full_name = first_value(row, "公司名稱", "有價證券全名", "全名") or name
            if code and name and re.fullmatch(r"\d{4,6}", code):
                stocks.append(
                    Stock(
                        code=code.strip(),
                        name=name.strip(),
                        market=market,
                        full_name=full_name.strip(),
                    )
                )
        return stocks


def first_value(row: dict, *keys: str) -> str:
    for key in keys:
        value = row.get(key)
        if value:
            return str(value)
    return ""


def normalize_text(value: str) -> str:
    return re.sub(r"\s+", "", value).strip().lower()


def dedupe_stocks(stocks: list[Stock]) -> list[Stock]:
    seen: set[tuple[str, str]] = set()
    result: list[Stock] = []
    for stock in stocks:
        key = (stock.market, stock.code)
        if key not in seen:
            seen.add(key)
            result.append(stock)
    return result
