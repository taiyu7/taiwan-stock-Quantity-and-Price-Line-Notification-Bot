# 台股量價 LINE 通知機器人

這是一個可部署到雲端的 LINE Messaging API 機器人。使用者可以透過 LINE 圖文選單和對話新增台股價格或成交量提醒；服務會在台股開盤期間每 30 秒檢查一次，條件觸發時推播 LINE 通知。

## 功能

- LINE Webhook：接收使用者訊息與圖文選單 postback。
- 圖文選單：價格提醒、成交量提醒、提醒清單、說明。
- 提醒規則：支援 `>=`、`<=`、`>`、`<`、`=`。
- 台股資料：查詢上市與上櫃即時報價。
- 背景檢查：台北時間週一到週五 09:00-13:30，每 30 秒檢查一次。
- 雲端部署：提供 Dockerfile 與 Procfile。

## 使用方式

1. 到 LINE Developers 建立 Messaging API channel。
2. 複製 `.env.example` 為 `.env`，填入：

```env
LINE_CHANNEL_ACCESS_TOKEN=...
LINE_CHANNEL_SECRET=...
APP_BASE_URL=https://your-cloud-domain.example.com
```

3. 建立虛擬環境、安裝套件並啟動服務：

```bash
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python -m uvicorn app.main:app --reload --port 8000
```

4. 在 LINE Developers 後台設定 Webhook URL：

```text
https://your-cloud-domain.example.com/line/webhook
```

5. 建立並啟用圖文選單：

```bash
.venv\Scripts\python scripts/create_rich_menu.py
```

## LINE 對話格式

價格提醒：

```text
2330 >= 600
```

成交量提醒：

```text
2330 >= 50000
```

查看提醒：

```text
清單
```

刪除提醒：

```text
刪除 12
```

## 部署

### Docker

```bash
docker build -t line-stock-alert-bot .
docker run --env-file .env -p 8000:8000 line-stock-alert-bot
```

### Render / Railway / Fly.io

使用本專案的 `Dockerfile` 或 `Procfile` 部署即可。正式環境建議將 `DATABASE_URL` 換成 PostgreSQL，例如：

```env
DATABASE_URL=postgresql+psycopg://user:password@host:5432/dbname
```

本專案已包含 PostgreSQL driver，可以直接使用 `postgresql+psycopg://...` 形式的 `DATABASE_URL`。

## 注意事項

- 目前交易日只判斷週一到週五與盤中時間，尚未串接台灣證交所休市日曆。
- 提醒觸發後會自動停用，避免同一條件每 30 秒重複通知。
- 成交量單位依即時報價來源回傳值顯示，實務部署前建議用目標標的盤中資料確認單位是否符合你的通知習慣。
