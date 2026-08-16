from __future__ import annotations

import json
import sys
from pathlib import Path

import requests
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.config import get_settings


LINE_API_BASE = "https://api.line.me/v2/bot"
OUT = ROOT / "data" / "rich-menu.png"


def main() -> None:
    settings = get_settings()
    if not settings.line_channel_access_token:
        raise RuntimeError("LINE_CHANNEL_ACCESS_TOKEN is not configured")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    build_image(OUT)

    rich_menu_id = create_rich_menu(settings.line_channel_access_token)
    upload_image(settings.line_channel_access_token, rich_menu_id, OUT)
    set_default(settings.line_channel_access_token, rich_menu_id)
    print(f"Created and activated rich menu: {rich_menu_id}")


def build_image(path: Path) -> None:
    image = Image.new("RGB", (2500, 843), "#f7f7f2")
    draw = ImageDraw.Draw(image)
    font_large = load_font(82)
    font_small = load_font(46)
    items = [
        ("價格提醒", "設定股價到價通知", "#0f766e"),
        ("成交量提醒", "設定成交量門檻", "#b45309"),
        ("提醒清單", "查看或刪除提醒", "#1d4ed8"),
        ("說明", "查看使用範例", "#374151"),
    ]
    width = 625
    for index, (title, subtitle, color) in enumerate(items):
        x0 = width * index
        draw.rectangle((x0, 0, x0 + width, 843), fill=color)
        draw.text((x0 + 88, 292), title, fill="white", font=font_large)
        draw.text((x0 + 88, 410), subtitle, fill="white", font=font_small)
    image.save(path)


def load_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        "C:/Windows/Fonts/msjh.ttc",
        "C:/Windows/Fonts/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for candidate in candidates:
        if Path(candidate).exists():
            return ImageFont.truetype(candidate, size=size)
    return ImageFont.load_default()


def create_rich_menu(token: str) -> str:
    payload = {
        "size": {"width": 2500, "height": 843},
        "selected": True,
        "name": "台股提醒選單",
        "chatBarText": "台股提醒",
        "areas": [
            area(0, "action=add_price"),
            area(625, "action=add_volume"),
            area(1250, "action=list"),
            area(1875, "action=help"),
        ],
    }
    response = requests.post(
        f"{LINE_API_BASE}/richmenu",
        headers=auth_headers(token),
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        timeout=15,
    )
    response.raise_for_status()
    return response.json()["richMenuId"]


def area(x: int, data: str) -> dict:
    return {
        "bounds": {"x": x, "y": 0, "width": 625, "height": 843},
        "action": {"type": "postback", "data": data},
    }


def upload_image(token: str, rich_menu_id: str, image_path: Path) -> None:
    response = requests.post(
        f"https://api-data.line.me/v2/bot/richmenu/{rich_menu_id}/content",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "image/png",
        },
        data=image_path.read_bytes(),
        timeout=30,
    )
    response.raise_for_status()


def set_default(token: str, rich_menu_id: str) -> None:
    response = requests.post(
        f"{LINE_API_BASE}/user/all/richmenu/{rich_menu_id}",
        headers=auth_headers(token),
        timeout=15,
    )
    response.raise_for_status()


def auth_headers(token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }


if __name__ == "__main__":
    main()
