from __future__ import annotations

import re
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AlertRule, UserState
from app.stock_master import ResolveResult, Stock, StockMasterClient
from app.twse_client import TwseClient


RULE_RE = re.compile(
    r"^\s*(?P<identifier>.+?)\s*(?P<metric>價|價格|price|量|成交量|volume)\s*"
    r"(?P<operator>>=|<=|>|<|=)\s*(?P<threshold>\d+(?:\.\d+)?)\s*$",
    re.IGNORECASE,
)


def set_mode(db: Session, user_id: str, mode: str) -> None:
    state = db.get(UserState, user_id)
    if state is None:
        state = UserState(line_user_id=user_id)
        db.add(state)
    state.mode = mode
    state.updated_at = datetime.utcnow()
    db.commit()


def get_mode(db: Session, user_id: str) -> str:
    state = db.get(UserState, user_id)
    return state.mode if state else ""


def clear_mode(db: Session, user_id: str) -> None:
    set_mode(db, user_id, "")


def create_rule_from_text(
    db: Session,
    user_id: str,
    text: str,
    default_metric: str,
    twse: TwseClient,
    stock_master: StockMasterClient | None = None,
) -> str:
    match = RULE_RE.match(text)
    if not match:
        return (
            f"格式我還讀不懂。請輸入像這樣：\n"
            f"2330 價 >= 600\n"
            f"2330 量 >= 50000\n"
            f"目前需要明確寫出「價」或「量」。"
        )

    identifier = match.group("identifier").strip()
    metric = normalize_metric(match.group("metric"))
    operator = normalize_operator(match.group("operator"))
    threshold = float(match.group("threshold"))

    stock_result = resolve_stock(db, identifier, stock_master)
    if stock_result.status == "ambiguous":
        return build_ambiguous_message(identifier, stock_result.candidates)
    if stock_result.status == "not_found":
        return f"找不到「{identifier}」對應的股票，請確認股名或股號是否正確。"

    stock = stock_result.stock
    if stock is None:
        return f"找不到「{identifier}」對應的股票，請確認股名或股號是否正確。"

    quote = twse.fetch_quote(stock.code, stock.market or None)
    if quote is None:
        return f"找不到 {stock.display_name} 的即時資料，請確認標的是否仍可交易。"

    rule = AlertRule(
        line_user_id=user_id,
        stock_code=stock.code,
        stock_name=stock.name or quote.name,
        market=stock.market or quote.market,
        metric=metric,
        operator=operator,
        threshold=threshold,
        last_value=quote.price if metric == "price" else quote.volume,
    )
    db.add(rule)
    db.commit()

    label = "價格" if metric == "price" else "成交量"
    unit = "元" if metric == "price" else "張"
    clear_mode(db, user_id)
    return (
        f"已建立提醒：{rule.stock_name}({rule.stock_code})\n"
        f"{label} {operator} {format_number(threshold)} {unit}\n"
        f"目前{label}：{format_number(rule.last_value or 0)} {unit}"
    )


def resolve_stock(db: Session, identifier: str, stock_master: StockMasterClient | None) -> ResolveResult:
    if stock_master:
        result = stock_master.resolve(identifier, db)
        if result.status == "found" or not re.fullmatch(r"\d{4,6}", identifier):
            return result
    if re.fullmatch(r"\d{4,6}", identifier):
        return ResolveResult.found(Stock(code=identifier, name="", market=""))
    return ResolveResult.not_found()


def build_ambiguous_message(identifier: str, candidates: tuple[Stock, ...]) -> str:
    lines = [f"「{identifier}」找到多個可能標的，請改用股票代號："]
    for stock in candidates[:10]:
        lines.append(f"- {stock.display_name}")
    return "\n".join(lines)


def list_rules(db: Session, user_id: str) -> str:
    rules = db.scalars(
        select(AlertRule)
        .where(AlertRule.line_user_id == user_id)
        .order_by(AlertRule.active.desc(), AlertRule.created_at.desc())
    ).all()
    if not rules:
        return "目前沒有提醒。可以從下方圖文選單新增價格或成交量提醒。"

    lines = ["你的提醒："]
    for rule in rules:
        status = "啟用" if rule.active else "已觸發"
        label = "價格" if rule.metric == "price" else "成交量"
        unit = "元" if rule.metric == "price" else "張"
        lines.append(
            f"#{rule.id} {status} {rule.stock_name}({rule.stock_code}) "
            f"{label} {rule.operator} {format_number(rule.threshold)} {unit}"
        )
    lines.append("\n要刪除請輸入：刪除 12")
    return "\n".join(lines)


def delete_rule(db: Session, user_id: str, text: str) -> str | None:
    match = re.match(r"^\s*(?:刪除|delete|del)\s+#?(?P<id>\d+)\s*$", text, re.IGNORECASE)
    if not match:
        return None
    rule = db.get(AlertRule, int(match.group("id")))
    if rule is None or rule.line_user_id != user_id:
        return "找不到這筆提醒。"
    db.delete(rule)
    db.commit()
    return f"已刪除 #{match.group('id')}。"


def normalize_metric(metric: str) -> str:
    return "volume" if metric.lower() in {"volume", "量", "成交量"} else "price"


def normalize_operator(operator: str) -> str:
    return "==" if operator == "=" else operator


def compare(value: float, operator: str, threshold: float) -> bool:
    if operator == ">=":
        return value >= threshold
    if operator == "<=":
        return value <= threshold
    if operator == ">":
        return value > threshold
    if operator == "<":
        return value < threshold
    return value == threshold


def format_number(value: float) -> str:
    return f"{value:,.2f}".rstrip("0").rstrip(".")
