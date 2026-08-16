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
2330 價 >= 600
```

成交量提醒：

```text
2330 量 >= 50000
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

### Railway

建議第一版先部署在 Railway，因為這個機器人需要一個常駐 Webhook 服務，同時背景每 30 秒檢查一次條件。

1. 將 GitHub repo 連到 Railway。
2. 新增 PostgreSQL service。
3. 在 Web service 設定環境變數：

```env
LINE_CHANNEL_ACCESS_TOKEN=...
LINE_CHANNEL_SECRET=...
APP_BASE_URL=https://your-railway-domain.up.railway.app
DATABASE_URL=${{Postgres.DATABASE_URL}}
CHECK_INTERVAL_SECONDS=30
ALERT_COOLDOWN_SECONDS=300
TIMEZONE=Asia/Taipei
ENABLE_SCHEDULER=true
```

LINE 的 `LINE_CHANNEL_ACCESS_TOKEN` 是機器人呼叫 LINE API 的通行憑證，例如用來回覆訊息、推播通知、建立圖文選單。`LINE_CHANNEL_SECRET` 是 LINE webhook 簽章驗證用的密鑰，用來確認打進 `/line/webhook` 的請求真的來自 LINE。

不要把 token 或 secret 貼到 README、GitHub issue、聊天紀錄或任何公開地方；只放在 Railway Variables、正式環境 secret manager 或本機 `.env`。

Railway 畫面可能會從 `.env.example` 顯示 Suggested Variables。請把預設值換成正式值：

- `LINE_CHANNEL_ACCESS_TOKEN`: LINE Developers 的 Channel access token。
- `LINE_CHANNEL_SECRET`: LINE Developers 的 Channel secret。
- `APP_BASE_URL`: Railway 產生的公開網址，例如 `https://web-production-xxxx.up.railway.app`。
- `DATABASE_URL`: 建議使用 PostgreSQL service 的 `${{Postgres.DATABASE_URL}}`，正式環境不要使用 SQLite。

4. 產生公開網域後，到 LINE Developers 設定 Webhook URL：

```text
https://your-railway-domain.up.railway.app/line/webhook
```

LINE 有兩個後台容易混淆：LINE Official Account Manager 和 LINE Developers。這個機器人的 webhook 必須在 LINE Developers 的 Messaging API channel 裡設定，並開啟 `Use webhook`。只在 Official Account Manager 設定 webhook 不會讓這個程式收到使用者訊息或圖文選單 postback。

專案已包含 `railway.toml`，Railway 會使用 Dockerfile 建置，並以 `/health` 作為部署健康檢查。

#### Railway 疑難排解

如果 Deployments 顯示 `Network > Healthcheck` 失敗，先點該 deployment 的 `View logs`，再看 `Deploy Logs`。Build 成功但 healthcheck 失敗，通常代表容器啟動後 app 沒有成功監聽 Railway 指定的 port，或啟動時發生 exception。

曾遇過的錯誤：

```text
Error: Invalid value for '--port': '${PORT:-8000}' is not a valid integer.
```

原因是 Railway 使用到舊的 start command，把 `${PORT:-8000}` 原封不動傳給 `uvicorn --port`。目前專案已改成 `python -m app.server`，由 Python 讀取 `PORT`。如果 Railway 還出現這個錯誤，到 service 的 Settings 檢查 Start Command，清掉舊指令或設定為：

```text
python -m app.server
```

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
