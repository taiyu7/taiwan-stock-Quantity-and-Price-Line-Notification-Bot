import base64
import hashlib
import hmac
import logging
from typing import Any

import requests

from app.config import get_settings


LINE_API_BASE = "https://api.line.me/v2/bot"
logger = logging.getLogger(__name__)


class LineClient:
    def __init__(self) -> None:
        self.settings = get_settings()

    def verify_signature(self, body: bytes, signature: str | None) -> bool:
        if not self.settings.line_channel_secret or not signature:
            return False
        digest = hmac.new(
            self.settings.line_channel_secret.encode("utf-8"),
            body,
            hashlib.sha256,
        ).digest()
        expected = base64.b64encode(digest).decode("utf-8")
        return hmac.compare_digest(expected, signature)

    def reply_text(self, reply_token: str, text: str) -> None:
        self._post(
            "/message/reply",
            {"replyToken": reply_token, "messages": [{"type": "text", "text": text}]},
        )

    def push_text(self, user_id: str, text: str) -> None:
        self._post(
            "/message/push",
            {"to": user_id, "messages": [{"type": "text", "text": text}]},
        )

    def _post(self, path: str, payload: dict[str, Any]) -> None:
        if not self.settings.line_channel_access_token:
            raise RuntimeError("LINE_CHANNEL_ACCESS_TOKEN is not configured")
        response = requests.post(
            f"{LINE_API_BASE}{path}",
            headers={
                "Authorization": f"Bearer {self.settings.line_channel_access_token}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=15,
        )
        if response.status_code >= 400:
            logger.error("LINE API request failed path=%s status=%s body=%s", path, response.status_code, response.text)
        response.raise_for_status()
