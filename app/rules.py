from __future__ import annotations

import re
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AlertRule, UserState
from app.twse_client import TwseClient


RULE_RE = re.compile(
    r"^\s*(?P<code>\d{4,6})\s*(?:(?P<metric>price|價格|volume|量|成交量)\s*)?"
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
) -> str:
    match = RULE_RE.match(text)
    if not match:
        metric_word = "價格" if default_metric == "price" else "成交量"
        return (
            f"格式我還讀不懂。請輸入像這樣：\n"
            f"2330 >= 600\n"
            f"如果是{metric_word}提醒，按選單後直接輸入股票代號、條件和門檻即可。"
        )

    code = match.group("code")
    metric = normalize_metric(match.group("metric"), default_metric)
    operator = normalize_operator(match.group("operator"))
    threshold = float(match.group("threshold"))

    quote = twse.fetch_quote(code)
    if quote is None:
        return f"找不到 {code} 的即時資料，請確認股票代號是否正確。"

    rule = AlertRule(
        line_user_id=user_id,
        stock_code=code,
        stock_name=quote.name,
        market=quote.market,
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
        f"已建立提醒：{quote.name}({code})\n"
        f"{label} {operator} {format_number(threshold)} {unit}\n"
        f"目前{label}：{format_number(rule.last_value or 0)} {unit}"
    )


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


def normalize_metric(metric: str | None, default_metric: str) -> str:
    if metric is None:
        return default_metric
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
