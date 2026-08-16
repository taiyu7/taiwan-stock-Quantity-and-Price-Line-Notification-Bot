from __future__ import annotations

from dataclasses import dataclass

import requests


TWSE_MIS_URL = "https://mis.twse.com.tw/stock/api/getStockInfo.jsp"


@dataclass(frozen=True)
class Quote:
    code: str
    name: str
    market: str
    price: float
    volume: float
    raw_time: str


class TwseClient:
    def fetch_quote(self, code: str, market: str | None = None) -> Quote | None:
        markets = [market] if market else ["tse", "otc"]
        for candidate in markets:
            quote = self._fetch_one(code, candidate)
            if quote:
                return quote
        return None

    def _fetch_one(self, code: str, market: str) -> Quote | None:
        ex_ch = f"{market}_{code}.tw"
        response = requests.get(
            TWSE_MIS_URL,
            params={"ex_ch": ex_ch, "json": "1", "delay": "0"},
            headers={"User-Agent": "line-stock-alert-bot/1.0"},
            timeout=10,
        )
        response.raise_for_status()
        data = response.json()
        rows = data.get("msgArray") or []
        if not rows:
            return None

        row = rows[0]
        price = self._parse_float(row.get("z")) or self._parse_float(row.get("y"))
        volume = self._parse_float(row.get("v"))
        if price is None or volume is None:
            return None

        return Quote(
            code=code,
            name=row.get("n") or code,
            market=market,
            price=price,
            volume=volume,
            raw_time=row.get("t") or "",
        )

    @staticmethod
    def _parse_float(value: object) -> float | None:
        if value in (None, "", "-", "--"):
            return None
        try:
            return float(str(value).replace(",", ""))
        except ValueError:
            return None
