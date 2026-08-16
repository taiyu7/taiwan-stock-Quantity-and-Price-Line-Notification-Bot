from typing import Any

from sqlalchemy.orm import Session

from app.line_client import LineClient
from app.rules import create_rule_from_text, delete_rule, get_mode, list_rules, set_mode
from app.twse_client import TwseClient


HELP_TEXT = (
    "可以用下方圖文選單設定提醒。\n\n"
    "價格提醒範例：2330 >= 600\n"
    "成交量提醒範例：2330 >= 50000\n"
    "刪除提醒範例：刪除 12\n\n"
    "機器人會在台股開盤時段約每 30 秒檢查一次，觸發後會通知你並停用該提醒。"
)


class BotService:
    def __init__(self) -> None:
        self.line = LineClient()
        self.twse = TwseClient()

    def handle_event(self, db: Session, event: dict[str, Any]) -> None:
        event_type = event.get("type")
        reply_token = event.get("replyToken")
        user_id = (event.get("source") or {}).get("userId")
        if not reply_token or not user_id:
            return

        if event_type == "postback":
            self._handle_postback(db, user_id, reply_token, event.get("postback") or {})
            return

        if event_type == "message" and (event.get("message") or {}).get("type") == "text":
            text = (event["message"].get("text") or "").strip()
            self._handle_text(db, user_id, reply_token, text)

    def _handle_postback(
        self,
        db: Session,
        user_id: str,
        reply_token: str,
        postback: dict[str, Any],
    ) -> None:
        data = postback.get("data") or ""
        if data == "action=add_price":
            set_mode(db, user_id, "price")
            self.line.reply_text(reply_token, "請輸入價格提醒，例如：2330 >= 600")
        elif data == "action=add_volume":
            set_mode(db, user_id, "volume")
            self.line.reply_text(reply_token, "請輸入成交量提醒，例如：2330 >= 50000")
        elif data == "action=list":
            self.line.reply_text(reply_token, list_rules(db, user_id))
        else:
            self.line.reply_text(reply_token, HELP_TEXT)

    def _handle_text(self, db: Session, user_id: str, reply_token: str, text: str) -> None:
        deleted = delete_rule(db, user_id, text)
        if deleted:
            self.line.reply_text(reply_token, deleted)
            return

        lowered = text.lower()
        if lowered in {"help", "說明", "幫助", "開始", "start"}:
            self.line.reply_text(reply_token, HELP_TEXT)
            return
        if lowered in {"list", "清單", "提醒"}:
            self.line.reply_text(reply_token, list_rules(db, user_id))
            return

        mode = get_mode(db, user_id) or "price"
        message = create_rule_from_text(db, user_id, text, mode, self.twse)
        self.line.reply_text(reply_token, message)
