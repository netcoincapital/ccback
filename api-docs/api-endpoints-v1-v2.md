# Coinceeper API — Endpoints فعال (V1 & V2)

> تاریخ: ۱۹ ژوئن ۲۰۲۶  
> این فایل تمام API‌های فعال و قابل استفاده در سرور را مستند کرده است.

---

## فهرست مطالب

- [نسخه V2 (Non-Custodial / Cache) — مدرن](#v2-api-non-custodial--cache-proxy)
- [نسخه V1 (Custodial / Legacy) — سنتی](#v1-api-custodial--legacy)
  - [Wallet (کیف پول)](#wallet)
  - [Currencies & Prices (ارزها و قیمت‌ها)](#currencies--prices)
  - [Chart (نمودار)](#chart)
  - [Transactions (تراکنش‌ها)](#transactions)
  - [Balance (موجودی)](#balance)
  - [Send / Transfer (ارسال و انتقال)](#send--transfer)
  - [Receive (دریافت)](#receive)
  - [Gas Fees (کارمزد شبکه)](#gas-fees)
  - [Fee Estimator (تخمین کارمزد)](#fee-estimator)
  - [Notifications & Price Alerts (اعلان‌ها و هشدار قیمت)](#notifications--price-alerts)
  - [App Version (نسخه اپلیکیشن)](#app-version)
  - [Shop (فروشگاه)](#shop)
  - [Chat / DM (چت و پیام خصوصی)](#chat--dm)
  - [Report & Block (گزارش و مسدودسازی)](#report--block)
  - [Moderation (مدیریت محتوا — ادمین)](#moderation-admin)
  - [Webhook](#webhook)
  - [System & Health (سیستم و سلامت)](#system--health)
- [WebSocket Events](#websocket-events)

---

## V2 API (Non-Custodial / Cache Proxy)

API‌های مدرن و توصیه‌شده که **نیاز به UserID ندارند**. همه endpoints زیر پیشوند `/api/v2` دارند.

### Prices & Coins

| Method | Endpoint | توضیحات | Query Params |
|--------|----------|---------|--------------|
| GET | `/api/v2/prices` | قیمت لحظه‌ای همه ارزهای پشتیبانی‌شده | — |
| GET | `/api/v2/prices/<symbol>` | قیمت یک ارز خاص (مثلاً BTC) | — |
| GET | `/api/v2/chart` | داده‌های نمودار تاریخی | `symbol`, `days` (مثلاً 7, 30, 365) |
| GET | `/api/v2/coins` | لیست ارزها با صفحه‌بندی | `search`, `page`, `per_page` |
| GET | `/api/v2/token-metadata` | متادیتای توکن (symbol, decimals, name) | — |

### Gas Fees

| Method | Endpoint | توضیحات | Query Params |
|--------|----------|---------|--------------|
| GET | `/api/v2/gas` | کارمزد گاز شبکه‌های پشتیبانی‌شده | `chain` (اختیاری) |

### Explorer (کاوشگر بلاکچین)

| Method | Endpoint | توضیحات | Body |
|--------|----------|---------|------|
| POST | `/api/v2/explorer/tx-history` | تاریخچه تراکنش‌های یک آدرس | `{ "address": "..." }` |
| POST | `/api/v2/explorer/internal-tx` | تراکنش‌های داخلی (فقط EVM) | `{ "address": "..." }` |
| POST | `/api/v2/explorer/token-tx` | تاریخچه انتقال توکن (ERC20/TRC20) | `{ "address": "..." }` |

### Balance

| Method | Endpoint | توضیحات | Body |
|--------|----------|---------|------|
| POST | `/api/v2/balance/native` | موجودی کوین اصلی (Native) | `{ "address": "...", "chain": "..." }` |
| POST | `/api/v2/balance/token` | موجودی توکن (ERC20/TRC20) | `{ "address": "...", "chain": "...", "contract": "..." }` |

### RPC & Broadcast

| Method | Endpoint | توضیحات |
|--------|----------|---------|
| POST | `/api/v2/rpc/<chain>` | فراخوانی مستقیم JSON-RPC خواندنی (EVM) |
| POST | `/api/v2/broadcast` | پخش تراکنش امضا شده در شبکه (EVM) |

### Notifications

| Method | Endpoint | توضیحات |
|--------|----------|---------|
| GET | `/api/v2/notifications` | اعلان‌های تراکنش بر اساس آدرس‌ها (query: `addresses`) |

### System & Health

| Method | Endpoint | توضیحات |
|--------|----------|---------|
| GET | `/api/v2/health` | وضعیت سلامت کش |
| GET | `/api/v2/proxy-health` | بررسی سلامت کامل همه providers |
| GET | `/api/v2/metrics` | متریک‌های Prometheus / JSON counters |
| POST | `/api/v2/admin/reload-keys` | بارگذاری مجدد API keys بدون ری‌استارت |

---

## V1 API (Custodial / Legacy)

API‌های سنتی که نیاز به **UserID** دارند. همه endpoints زیر پیشوند `/api/` دارند.

### Wallet

| Method | Endpoint | توضیحات |
|--------|----------|---------|
| POST | `/api/generate-wallet` | ساخت کیف پول جدید (synchronous) |
| POST | `/api/generate-wallet-v1` | ساخت کیف پول (blueprint v1) |
| POST | `/api/import_wallet` | import کیف پول با عبارت mnemonic |
| POST | `/api/validate_mnemonic` | اعتبارسنجی عبارت mnemonic بدون import |

---

### Currencies & Prices

| Method | Endpoint | توضیحات |
|--------|----------|---------|
| GET | `/api/all-currencies` | دریافت همه ارزها یکجا |
| POST | `/api/prices` | دریافت قیمت ارزها از دیتابیس |
| POST | `/api/update-prices` | بروزرسانی قیمت ارزها |
| GET | `/api/price-stats` | آمار قیمت‌ها |
| GET | `/api/key-stats` | آمار کلیدها |
| POST | `/api/historical-prices` | قیمت‌های تاریخی |
| POST | `/api/historical-prices-bulk` | قیمت‌های تاریخی bulk |
| POST | `/api/historical-prices-auto` | دریافت خودکار قیمت‌های تاریخی |
| POST | `/api/update-historical-prices` | بروزرسانی قیمت‌های تاریخی |

---

### Chart

| Method | Endpoint | توضیحات |
|--------|----------|---------|
| POST | `/api/chart-data` | دریافت داده‌های نمودار |
| POST | `/api/chart-live-update` | بروزرسانی لحظه‌ای نمودار |

---

### Transactions

| Method | Endpoint | توضیحات |
|--------|----------|---------|
| POST | `/api/transactions` | دریافت تراکنش‌های کاربر |
| GET | `/api/transactions` | دریافت تراکنش‌های کاربر (GET) |
| GET | `/api/transactions/status` | وضعیت سرویس تراکنش‌ها |
| POST | `/api/transactions/debug` | دیباگ تراکنش‌ها و کانفیگ دیتابیس |

---

### Balance

| Method | Endpoint | توضیحات |
|--------|----------|---------|
| POST | `/api/balance` | دریافت موجودی کیف پول |
| POST | `/api/update-balance` | بروزرسانی موجودی کیف پول |
| GET | `/api/health-check` | بررسی سلامت سرویس balance |
| GET | `/api/debug` | دیباگ balance |
| POST | `/api/test-update-balance` | تست بروزرسانی موجودی |
| POST | `/api/rebuild-holdings` | بازسازی مجدد دارایی‌های کاربر |

---

### Send / Transfer

#### Generic

| Method | Endpoint | توضیحات |
|--------|----------|---------|
| POST | `/api/send/prepare` | آماده‌سازی تراکنش ارسال (generic) |
| POST | `/api/send/confirm` | تأیید و پخش تراکنش ارسال |

#### Ethereum

| Method | Endpoint | توضیحات |
|--------|----------|---------|
| POST | `/api/send/ethereum/prepare` | آماده‌سازی تراکنش اتریوم |
| POST | `/api/send/ethereum/confirm` | تأیید تراکنش اتریوم |

#### BSC

| Method | Endpoint | توضیحات |
|--------|----------|---------|
| POST | `/api/send/bsc/prepare` | آماده‌سازی تراکنش BSC |
| POST | `/api/send/bsc/confirm` | تأیید تراکنش BSC |

#### Tron

| Method | Endpoint | توضیحات |
|--------|----------|---------|
| POST | `/api/send/tron/prepare` | آماده‌سازی تراکنش ترون |
| POST | `/api/send/tron/confirm` | تأیید تراکنش ترون |

#### Bitcoin

| Method | Endpoint | توضیحات |
|--------|----------|---------|
| POST | `/api/send/bitcoin/prepare` | آماده‌سازی تراکنش بیت‌کوین |
| POST | `/api/send/bitcoin/confirm` | تأیید تراکنش بیت‌کوین |

#### Polygon

| Method | Endpoint | توضیحات |
|--------|----------|---------|
| POST | `/api/send/polygon/prepare` | آماده‌سازی تراکنش پالیگان |
| POST | `/api/send/polygon/confirm` | تأیید تراکنش پالیگان |

#### Debug & Test (Send)

| Method | Endpoint | توضیحات |
|--------|----------|---------|
| GET | `/api/send/test` | تست send endpoint |
| GET | `/api/send/debug-transactions` | دیباگ تراکنش‌ها |
| GET | `/api/send/debug-storage` | دیباگ storage |
| GET | `/api/send/debug-transaction/<transaction_id>` | دیباگ تراکنش مشخص |
| POST | `/api/send/debug-blockchain-detection` | دیباگ تشخیص بلاکچین |
| POST | `/api/send/force-bsc` | اجبار تراکنش BSC |
| POST | `/api/send/debug-wallet` | دیباگ کیف پول |
| POST | `/api/send/detect-blockchain` | تشخیص بلاکچین از روی آدرس |
| GET | `/api/send/test-broadcast-capability` | تست قابلیت broadcast |
| GET | `/api/send/check-mempool-visibility/<tx_hash>` | بررسی visibility در ممپول |

---

### Receive

| Method | Endpoint | توضیحات |
|--------|----------|---------|
| POST | `/api/Recive` | دریافت تراکنش ورودی |
| POST | `/api/record-deposit` | ثبت واریز |

---

### Gas Fees

| Method | Endpoint | توضیحات |
|--------|----------|---------|
| GET | `/api/gasfee` | کارمزد گاز همه شبکه‌ها |

---

### Fee Estimator

| Method | Endpoint | توضیحات |
|--------|----------|---------|
| POST | `/api/estimate-fee` | تخمین کارمزد تراکنش برای هر بلاکچین |
| GET | `/api/supported-chains` | لیست بلاکچین‌های پشتیبانی‌شده |
| GET | `/api/chain-info/<blockchain>` | اطلاعات یک بلاکچین مشخص |
| GET | `/api/estimate-fee/health` | بررسی سلامت سرویس تخمین کارمزد |

---

### Notifications & Price Alerts

#### Device Registration

| Method | Endpoint | توضیحات |
|--------|----------|---------|
| POST | `/api/notifications/register-device` | ثبت دستگاه برای اعلان‌های push |
| POST | `/api/notifications/simple-register-device` | ثبت دستگاه با حفظ حریم خصوصی (پشتیبانی DeviceID) |
| POST | `/api/notifications/test` | ارسال اعلان تستی به دستگاه |
| POST | `/api/notifications/test-notify` | تست مستقیم تابع notify |

#### Security Notifications

| Method | Endpoint | توضیحات |
|--------|----------|---------|
| POST | `/api/notifications/security/login` | اعلان ورود از دستگاه جدید |
| POST | `/api/notifications/security/change` | اعلان تغییرات امنیتی (رمز، ۲FA) |
| POST | `/api/notifications/security/suspicious` | اعلان فعالیت مشکوک |

#### Price Alerts

| Method | Endpoint | توضیحات |
|--------|----------|---------|
| POST | `/api/notifications/price-alert` | ایجاد هشدار قیمت جدید |
| GET | `/api/notifications/price-alerts/<user_id>` | دریافت هشدارهای قیمت کاربر |
| DELETE | `/api/notifications/price-alert` | حذف هشدار قیمت |
| GET | `/api/notifications/price-alerts/prices` | bulk قیمت برای بررسی هشدارها |

#### Admin Broadcast

| Method | Endpoint | توضیحات |
|--------|----------|---------|
| POST | `/api/admin/notifications/broadcast` | ارسال اعلان همگانی به همه کاربران |
| POST | `/api/admin/notifications/new-listing` | اعلان لیست شدن ارز جدید |
| POST | `/api/admin/notifications/breaking-news` | ارسال اخبار فوری |
| POST | `/api/admin/notifications/app-update` | اعلان بروزرسانی اپلیکیشن |
| POST | `/api/admin/notifications/portfolio-summary/<user_id>` | خلاصه پورتفولیو |
| POST | `/api/admin/notifications/reward` | اعلان جایزه/ایردراپ |
| POST | `/api/admin/notifications/network-status` | وضعیت شبکه |
| POST | `/api/admin/notifications/network-upgrade` | ارتقاء شبکه |

---

### App Version

| Method | Endpoint | توضیحات |
|--------|----------|---------|
| GET | `/api/app/version` | دریافت نسخه مورد نیاز اپ برای هر پلتفرم |
| POST | `/api/app/version/update-config` | بروزرسانی کانفیگ نسخه (ادمین) |

---

### Shop

| Method | Endpoint | توضیحات |
|--------|----------|---------|
| GET | `/api/shop/products` | لیست محصولات (query: `category`, `is_active`) |
| POST | `/api/shop/products` | ایجاد محصول جدید |
| GET | `/api/shop/products/<product_id>` | دریافت یک محصول |

---

### Chat / DM

| Method | Endpoint | توضیحات |
|--------|----------|---------|
| GET | `/api/chat/conversations` | دریافت مکالمات کاربر (query: `UserID`) |
| GET | `/api/chat/conversations/<conversation_id>/messages` | دریافت پیام‌های یک مکالمه |
| POST | `/api/chat/messages` | ارسال پیام جدید |
| PUT | `/api/chat/messages/<message_id>` | ویرایش پیام |
| DELETE | `/api/chat/messages/<message_id>` | حذف نرم پیام |
| DELETE | `/api/chat/conversations/<conversation_id>` | حذف نرم مکالمه |

---

### Report & Block

| Method | Endpoint | توضیحات |
|--------|----------|---------|
| POST | `/api/chat/report` | گزارش کاربر/پیام |
| GET | `/api/chat/reports` | گزارش‌های کاربر |
| POST | `/api/chat/block` | مسدود کردن کاربر |
| DELETE | `/api/chat/block` | رفع مسدودیت کاربر |
| GET | `/api/chat/blocked-users` | لیست کاربران مسدود شده |

---

### Moderation (Admin)

| Method | Endpoint | توضیحات |
|--------|----------|---------|
| GET | `/api/chat/moderation/reports` | دریافت همه گزارش‌ها (moderator) |
| POST | `/api/chat/moderation/reports/<report_id>/resolve` | حل و فصل گزارش |
| POST | `/api/chat/moderation/users/<user_id>/ban` | بن کاربر (موقت/دائم) |
| POST | `/api/chat/moderation/users/<user_id>/unban` | رفع بن کاربر |
| GET | `/api/chat/moderation/users/<user_id>/status` | وضعیت moderation کاربر |

---

### Webhook

| Method | Endpoint | توضیحات |
|--------|----------|---------|
| POST | `/webhook/tatum/transaction` | دریافت webhook از Tatum برای رویدادهای بلاکچین |
| GET | `/webhook/update-transaction/<blockchain>/<tx_hash>` | بروزرسانی دستی تراکنش |
| GET | `/webhook/test` | تست مسیرهای webhook |
| GET, POST | `/webhook/test-tatum` | تست فرمت پاسخ Tatum |

---

### System & Health

| Method | Endpoint | توضیحات |
|--------|----------|---------|
| GET | `/` | صفحه اصلی / index.html |
| GET | `/test-api` | تست پایه API |
| GET | `/api/test-db` | تست اتصال دیتابیس |
| GET | `/api/ping` | چک سبک connectivity |
| GET | `/api/app-health` | بررسی سلامت اپلیکیشن |
| GET | `/api/database-test` | تست جزئیات دیتابیس |
| GET | `/api/config-test` | تست متغیرهای کانفیگ |
| GET | `/api/historical-scheduler-status` | وضعیت scheduler داده‌های تاریخی |
| POST | `/api/historical-scheduler-control` | start/stop/restart scheduler تاریخی |
| GET | `/debug-api` | اطلاعات دیباگ (blueprints, routes) |
| GET | `/ads/` | لیست تبلیغات |

### API Documentation

| Method | Endpoint | توضیحات |
|--------|----------|---------|
| GET | `/api/docs` | Swagger UI |
| GET | `/api/swagger.json` | مشخصات Swagger JSON |
| GET | `/api-docs` | مستندات API |
| GET | `/api-docs/<path:filename>` | فایل‌های استاتیک مستندات |

---

## WebSocket Events

اتصال از طریق Socket.IO (در `chat/websocket_handler.py`)

### Client → Server

| Event | توضیحات |
|-------|---------|
| `connect` | اتصال کلاینت (نیازمند `user_id` در auth) |
| `disconnect` | قطع اتصال کلاینت |
| `join_conversation` | ورود به اتاق مکالمه |
| `leave_conversation` | خروج از اتاق مکالمه |
| `send_message` | ارسال پیام جدید (باعث پخش `new_message` می‌شود) |
| `edit_message` | ویرایش پیام (باعث پخش `message_edited` می‌شود) |
| `delete_message` | حذف پیام (باعث پخش `message_deleted` می‌شود) |
| `typing_start` / `typing_stop` | اندیکاتور تایپ کردن |

### Server → Client

| Event | توضیحات |
|-------|---------|
| `new_message` | پیام جدید در اتاق مکالمه |
| `message_edited` | ویرایش پیام در اتاق |
| `message_deleted` | حذف پیام در اتاق |
| `user_typing` | بروزرسانی اندیکاتور تایپ |

---

## خلاصه آماری

| بخش | تعداد Endpoints |
|-----|----------------|
| **V2** (Cache Proxy) | 18 |
| **V1 - Wallet** | 4 |
| **V1 - Currencies & Prices** | 9 |
| **V1 - Chart** | 2 |
| **V1 - Transactions** | 4 |
| **V1 - Balance** | 6 |
| **V1 - Send / Transfer** | 20 |
| **V1 - Receive** | 2 |
| **V1 - Gas Fees** | 1 |
| **V1 - Fee Estimator** | 4 |
| **V1 - Notifications & Price Alerts** | 15 |
| **V1 - App Version** | 2 |
| **V1 - Shop** | 3 |
| **V1 - Chat / DM** | 6 |
| **V1 - Report & Block** | 5 |
| **V1 - Moderation (Admin)** | 5 |
| **V1 - Webhook** | 4 |
| **V1 - System & Health** | 11 |
| **V1 - API Documentation** | 5 |
| **WebSocket Events** | 8 Client → Server |
| **جمع کل (HTTP)** | **~126 endpoint** |
