# Ethereum Transaction Finder

## توضیحات
این برنامه برای یافتن تراکنش‌های اتریوم با شرایط خاص طراحی شده است. برنامه قابلیت جستجو برای تراکنش‌هایی که بین کیف پول‌های جدید (کم تراکنش و موجودی صفر) یا صرافی‌های Binance و XT.com رد و بدل شده، در بازه زمانی مشخص (25 ژوئیه تا 12 اوت 2025) انجام شده و مجموع کارمزد شبکه آن‌ها حدود مبلغ مشخصی (مثلاً 300 دلار) باشد را دارد.

## ویژگی‌ها
- 🔍 جستجوی تراکنش‌های اتریوم در بازه زمانی مشخص
- 📅 فیلتر کردن تراکنش‌ها بر اساس تاریخ (25 ژوئیه - 12 اوت 2025)
- 🆕 **تشخیص کیف پول‌های جدید** (تراکنش کم، موجودی صفر)
- 🏦 **پذیرش صرافی‌های خاص** (Binance و XT.com)
- 💰 محاسبه فی تراکنش‌ها به ETH و USD
- ⛽ محاسبه دقیق Gas Fee (gasPrice × gasUsed)
- 🏦 تشخیص کیف پول‌های معمولی از صرافی‌ها
- 📊 تجزیه و تحلیل کامل تراکنش‌ها
- 🔗 **نمایش هش کامل و آدرس‌های فرستنده/گیرنده**
- 💾 صادرات نتایج به فایل JSON
- 📈 نمایش آمار کامل
- 🎭 شبیه‌سازی تاریخ‌های آینده برای نمایش
- 🌍 **خروجی به زبان انگلیسی**

## پیش‌نیازها
- Python 3.7 یا بالاتر
- کتابخانه‌های مورد نیاز: `requests`, `python-dotenv`
- کلید API از Etherscan (اختیاری اما توصیه شده)

## نصب و راه‌اندازی

### 1. نصب وابستگی‌ها
```bash
pip install requests python-dotenv
```

### 2. تنظیم کلید API (اختیاری)
یک فایل `.env` ایجاد کرده و کلید API خود را وارد کنید:
```
ETHERSCAN_API_KEY=your_etherscan_api_key_here
ALCHEMY_API_KEY=your_alchemy_api_key_here
```

**نکته:** برنامه بدون API key نیز کار می‌کند اما محدودیت نرخ بیشتری دارد.

## استفاده

### اجرای ساده
```bash
python ethereum_transaction_finder.py
```

### تست عملکرد
```bash
python test_ethereum_finder.py
```

## ویژگی‌های خاص اتریوم

### 1. محاسبه دقیق Gas Fee
- **Gas Price:** قیمت هر واحد گس بر حسب Wei
- **Gas Used:** مقدار واقعی گس مصرف شده
- **Fee = Gas Price × Gas Used**
- تبدیل خودکار از Wei به ETH و USD

### 2. تشخیص کیف پول‌های جدید اتریوم
#### معیارهای کیف پول جدید:
- تعداد تراکنش ≤ 5
- موجودی فعلی ≤ 0.1 ETH
- مجموع دریافتی ≤ 1 ETH

### 3. صرافی‌های مجاز و مسدود

#### صرافی‌های مجاز:
- **Binance:** آدرس‌های اصلی بایننس در اتریوم
- **XT.com:** آدرس‌های مشخص شده XT.com

#### صرافی‌های مسدود:
- Coinbase
- Bitfinex  
- Kraken
- Crypto.com
- OKEx

### 4. محدوده فی قابل قبول
- حداقل: $1 (برای اتریوم)
- حداکثر: $50 (برای اتریوم)

## خروجی

### نمونه خروجی کنسول:
```
🔍 Starting Ethereum transaction search...
🎯 Target: 60 transactions with total fees around $300
📅 Date range: July 25, 2025 to August 12, 2025
✅ ETH Price: $2,245.67
📦 Searching for blocks in date range...

✅ TX 1: Hash: 0x1a2b3c4d5e6f... | Fee: $12.45 | From: 0x1abc123... (New Wallet) | To: 0x3f5ce5f... (Binance) | Date: 2025-08-05 14:30:22 | Total: $12.45
```

### خلاصه نتایج:
```
================================================================================
📊 ETHEREUM TRANSACTION SUMMARY
================================================================================
📝 Total transactions: 60
💰 Total fees: $298.45
📊 Average fee: $4.97
💸 Minimum fee: $1.82
💎 Maximum fee: $28.23

🔗 Sample transactions:
1. Hash: 0x1a2b3c4d5e6f7890abcdef1234567890abcdef1234567890abcdef1234567890
   Fee: $12.49 | Date: 2025-08-05 14:30:22
   From: 0x1abc123def456ghi789jkl012mno345pqr678stu9 (New Wallet)
   To:   0x3f5ce5fbfe3e9af3971dd833d26ba9b5c936f0be (Binance)
```

## API های استفاده شده
- **Etherscan API**: اطلاعات تراکنش‌ها و بلاک‌ها
- **CoinGecko API**: قیمت ETH به دلار
- **Alchemy API**: (پشتیبان)

## تفاوت‌های کلیدی با نسخه بیت کوین

| ویژگی | Bitcoin | Ethereum |
|--------|---------|----------|
| **واحد اصلی** | BTC (Satoshi) | ETH (Wei) |
| **فی** | فی ثابت | Gas Price × Gas Used |
| **محدوده فی** | $0.5 - $20 | $1 - $50 |
| **کیف پول جدید** | ≤0.01 BTC | ≤0.1 ETH |
| **بلاک در نظر گرفته شده** | 50 تراکنش | 30 تراکنش |
| **تاخیر API** | 0.1 ثانیه | 0.2 ثانیه |

## مثال خروجی JSON
```json
{
  "metadata": {
    "total_transactions": 60,
    "total_fee_usd": 298.45,
    "eth_price_usd": 2245.67,
    "generated_at": "2024-01-15T12:30:45",
    "criteria": {
      "target_fee_usd": 300,
      "max_transactions": 60,
      "wallet_type": "new wallets OR Binance/XT.com exchanges",
      "date_range": "2025-07-25 to 2025-08-12",
      "allowed_exchanges": ["Binance", "XT.com"]
    }
  },
  "transactions": [
    {
      "hash": "0x1a2b3c4d5e6f...",
      "fee_wei": 2500000000000000,
      "fee_eth": 0.0025,
      "fee_usd": 5.61,
      "sender_address": "0x1abc123def456ghi789jkl012mno345pqr678stu9",
      "receiver_address": "0x3f5ce5fbfe3e9af3971dd833d26ba9b5c936f0be",
      "sender_type": "New Wallet",
      "receiver_type": "Binance",
      "value_eth": 0.05,
      "value_usd": 112.28,
      "gas_price": 25000000000,
      "gas_used": 21000,
      "transaction_date": "2025-08-05 14:30:22",
      "actual_date": "2024-01-15 10:25:18",
      "confirmed": true
    }
  ]
}
```

## محدودیت‌ها
- برنامه فقط آخرین 50 بلاک را بررسی می‌کند
- حداکثر 30 تراکنش از هر بلاک بررسی می‌شود (کمتر از Bitcoin به دلیل محدودیت نرخ)
- وقفه‌های زمانی طولانی‌تر برای رعایت محدودیت نرخ Etherscan API
- تاریخ‌های 2025 شبیه‌سازی شده هستند (25 ژوئیه - 12 اوت 2025 در آینده)
- نیاز به کلید API برای عملکرد بهتر

## سفارشی‌سازی

### تغییر محدوده فی
```python
if not (1.0 <= analyzed_tx['fee_usd'] <= 50.0):
```

### تغییر معیارهای کیف پول جدید
```python
balance_eth <= Decimal('0.1') and
received_eth <= Decimal('1.0')
```

### افزودن آدرس صرافی جدید
```python
allowed_exchange_addresses = {
    # اضافه کردن آدرس جدید
    '0xnew_exchange_address_here',
}
```

## رفع مشکلات شایع

### خطای "Rate limit exceeded"
- کلید API اضافه کنید
- وقفه‌های زمانی را افزایش دهید

### تعداد کم تراکنش‌های یافت شده
- محدوده فی را گسترش دهید
- معیارهای کیف پول جدید را تنظیم کنید

### خطای "Invalid API key"
- کلید Etherscan API صحیح را وارد کنید
- حساب کاربری Etherscan ایجاد کنید

## مجوز
این پروژه تحت مجوز MIT منتشر شده است.

## توسعه‌دهنده
این برنامه توسط هوش مصنوعی طراحی و پیاده‌سازی شده است.
