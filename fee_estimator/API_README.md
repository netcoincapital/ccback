# راهنمای استفاده از API تخمین کارمزد تراکنش‌ها

این API امکان تخمین کارمزد تراکنش‌ها را برای بلاک‌چین‌های مختلف فراهم می‌کند. این راهنما نحوه راه‌اندازی و استفاده از این API را توضیح می‌دهد.

## نصب و راه‌اندازی

### ۱. نصب وابستگی‌ها

```bash
cd E:\0\coinceeper\backend\coinceeper.com
pip install -r CC/fee_estimator/requirements.txt
pip install flask
```

### ۲. اجرای سرور API

```bash
cd E:\0\coinceeper\backend\coinceeper.com
python -m CC.fee_estimator.run_api --port 5000
```

پارامترهای اختیاری:
- `--host` - آدرس IP که سرور روی آن اجرا می‌شود (پیش‌فرض: `0.0.0.0`)
- `--port` - پورت که سرور روی آن اجرا می‌شود (پیش‌فرض: `5000`)
- `--debug` - فعال‌سازی حالت دیباگ

## نقاط پایانی API (Endpoints)

### ۱. تخمین کارمزد تراکنش

**درخواست**:
- **نوع**: POST
- **URL**: `/api/estimate-fee`
- **بدنه درخواست (JSON)**:

```json
{
    "blockchain": "ethereum",
    "from_address": "0x742d35Cc6634C0532925a3b844Bc454e4438f44e",
    "to_address": "0xAb5801a7D398351b8bE11C439e05C5B3259aeC9B",
    "amount": 0.1,
    "token_contract": "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48"
}
```

پارامترها:
- `blockchain` (الزامی): نام بلاک‌چین (ethereum, bitcoin, tron, و غیره)
- `from_address` (الزامی): آدرس مبدا
- `to_address` (الزامی): آدرس مقصد
- `amount` (الزامی): مقدار انتقال
- `token_contract` (اختیاری): آدرس قرارداد توکن (برای انتقال توکن‌ها)

**پاسخ**:

```json
{
  "fee": 2100000,
  "fee_currency": "ETH",
  "unit": "wei",
  "timestamp": 1685432865,
  "gas_used": 21000,
  "gas_price": 100000000000,
  "priority_options": {
    "slow": {
      "fee": 1890000,
      "fee_eth": 0.00000189
    },
    "average": {
      "fee": 2100000,
      "fee_eth": 0.0000021
    },
    "fast": {
      "fee": 3150000,
      "fee_eth": 0.00000315
    }
  },
  "usd_price": 0.00063
}
```

### ۲. دریافت بلاک‌چین‌های پشتیبانی شده

**درخواست**:
- **نوع**: GET
- **URL**: `/api/supported-chains`

**پاسخ**:

```json
{
  "chains": [
    "bitcoin",
    "ethereum",
    "tron",
    "solana",
    "xrp",
    "cardano",
    "polkadot",
    "cosmos"
  ]
}
```

### ۳. دریافت اطلاعات یک بلاک‌چین خاص

**درخواست**:
- **نوع**: GET
- **URL**: `/api/chain-info/<blockchain>`

**پاسخ**:

```json
{
  "name": "Ethereum",
  "symbol": "ETH",
  "decimals": 18,
  "smallest_unit": "wei",
  "units_per_coin": 1000000000000000000,
  "token_standard": "ERC20",
  "supports_tokens": true
}
```

### ۴. بررسی سلامت API

**درخواست**:
- **نوع**: GET
- **URL**: `/api/health`

**پاسخ**:

```json
{
  "status": "healthy"
}
```

## مثال‌های استفاده

### کرل (cURL)

#### تخمین کارمزد برای انتقال اتریوم:

```bash
curl -X POST http://localhost:5000/api/estimate-fee \
  -H "Content-Type: application/json" \
  -d '{
    "blockchain": "ethereum",
    "from_address": "0x742d35Cc6634C0532925a3b844Bc454e4438f44e",
    "to_address": "0xAb5801a7D398351b8bE11C439e05C5B3259aeC9B",
    "amount": 0.1
  }'
```

#### تخمین کارمزد برای انتقال توکن ERC20:

```bash
curl -X POST http://localhost:5000/api/estimate-fee \
  -H "Content-Type: application/json" \
  -d '{
    "blockchain": "ethereum",
    "from_address": "0x742d35Cc6634C0532925a3b844Bc454e4438f44e",
    "to_address": "0xAb5801a7D398351b8bE11C439e05C5B3259aeC9B",
    "amount": 100,
    "token_contract": "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48"
  }'
```

### پایتون

```python
import requests

# تخمین کارمزد برای انتقال بیت‌کوین
response = requests.post(
    "http://localhost:5000/api/estimate-fee",
    json={
        "blockchain": "bitcoin",
        "from_address": "bc1qxy2kgdygjrsqtzq2n0yrf2493p83kkfjhx0wlh",
        "to_address": "bc1qxy2kgdygjrsqtzq2n0yrf2493p83kkfjhx0wlh",
        "amount": 0.01
    }
)

print(response.json())
```

## نکات مهم

1. این API برای استفاده در محیط تولید (Production) باید همراه با پیکربندی‌های امنیتی مناسب مانند HTTPS، احراز هویت و محدودیت نرخ درخواست باشد.

2. برای استفاده در محیط تولید، باید نودها و کلیدهای API خصوصی خود را تنظیم کنید. فایل‌های بلاک‌چین موجود از API‌های عمومی استفاده می‌کنند که ممکن است محدودیت نرخ درخواست داشته باشند.

3. برای بهبود کارایی، می‌توانید سیستم کش (Cache) را پیاده‌سازی کنید تا از تکرار درخواست‌های مشابه به API‌های بلاک‌چین جلوگیری شود. 