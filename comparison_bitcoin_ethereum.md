# مقایسه Bitcoin Transaction Finder و Ethereum Transaction Finder

## خلاصه
دو برنامه با منطق مشابه اما تنظیمات متفاوت برای دو بلاکچین Bitcoin و Ethereum ایجاد شده‌اند.

## تشابهات

### هدف مشترک:
- یافتن تراکنش‌هایی بین کیف پول‌های جدید یا صرافی‌های Binance/XT.com
- محاسبه مجموع فی تراکنش‌ها تا رسیدن به هدف (مثلاً $300)
- فیلتر کردن بر اساس بازه زمانی (25 ژوئیه - 12 اوت 2025)
- خروجی انگلیسی با جزئیات کامل

### ویژگی‌های مشترک:
- 🔍 جستجوی تراکنش‌ها در بازه زمانی مشخص
- 🆕 تشخیص کیف پول‌های جدید
- 🏦 پذیرش صرافی‌های خاص (Binance و XT.com)
- 📊 تجزیه و تحلیل کامل تراکنش‌ها
- 🔗 نمایش هش کامل و آدرس‌ها
- 💾 صادرات نتایج به JSON
- 🎭 شبیه‌سازی تاریخ‌های آینده

## تفاوت‌های کلیدی

| ویژگی | Bitcoin | Ethereum |
|--------|---------|----------|
| **فایل اصلی** | `bitcoin_transaction_finder.py` | `ethereum_transaction_finder.py` |
| **واحد پول** | BTC (Satoshi) | ETH (Wei) |
| **محاسبه فی** | فی ثابت | Gas Price × Gas Used |
| **محدوده فی** | $0.5 - $20 | $1 - $50 |
| **واحد کوچک** | 1 BTC = 100,000,000 Satoshi | 1 ETH = 10^18 Wei |
| **API اصلی** | Mempool.space | Etherscan |
| **آدرس فرمت** | 1..., 3..., bc1... | 0x... |
| **طول آدرس** | متغیر (26-62 کاراکتر) | ثابت (42 کاراکتر) |

## معیارهای کیف پول جدید

### Bitcoin:
- تراکنش ≤ 5
- موجودی ≤ 0.01 BTC
- دریافتی ≤ 0.1 BTC

### Ethereum:
- تراکنش ≤ 5  
- موجودی ≤ 0.1 ETH
- دریافتی ≤ 1 ETH

## محدودیت‌های عملکرد

### Bitcoin:
- 50 تراکنش در هر بلاک
- وقفه 0.1 ثانیه بین تراکنش‌ها
- وقفه 0.5 ثانیه بین بلاک‌ها

### Ethereum:
- 30 تراکنش در هر بلاک (کمتر به دلیل محدودیت API)
- وقفه 0.2 ثانیه بین تراکنش‌ها
- وقفه 1.0 ثانیه بین بلاک‌ها

## آدرس‌های صرافی نمونه

### Bitcoin Binance:
```
34xp4vRoCGJym3xR7yCVPFHoCNxv4Twseo
3LYJfcfHPXYJreMsASk2jkn69LWEYKzexb
```

### Ethereum Binance:
```
0x3f5ce5fbfe3e9af3971dd833d26ba9b5c936f0be
0xd551234ae421e3bcba99a0da6d736074f22192ff
```

## API Keys مورد نیاز

### Bitcoin:
```bash
BITCOIN_API_KEY=optional
BLOCKCHAIR_API_KEY=optional
```

### Ethereum:
```bash
ETHERSCAN_API_KEY=recommended
ALCHEMY_API_KEY=optional
```

## دستورات اجرا

### Bitcoin:
```bash
python bitcoin_transaction_finder.py
python test_bitcoin_finder.py
```

### Ethereum:
```bash
python ethereum_transaction_finder.py
python test_ethereum_finder.py
```

## نمونه خروجی

### Bitcoin:
```
✅ TX 1: Hash: 1a2b3c4d5e6f... | Fee: $4.25 | From: 1ABC123... (New Wallet) | To: 3XYZ789... (Binance)
```

### Ethereum:
```
✅ TX 1: Hash: 0x1a2b3c4d5e6f... | Fee: $12.45 | From: 0x1abc123... (New Wallet) | To: 0x3f5ce5f... (Binance)
```

## فایل‌های خروجی

### Bitcoin:
- `bitcoin_transactions_YYYYMMDD_HHMMSS.json`

### Ethereum:
- `ethereum_transactions_YYYYMMDD_HHMMSS.json`

## کدهای ویژه هر بلاکچین

### Bitcoin - محاسبه فی:
```python
fee_btc = self.satoshi_to_btc(fee_satoshi)
fee_usd = self.btc_to_usd(fee_btc)
```

### Ethereum - محاسبه گس:
```python
fee_wei = gas_price * gas_used
fee_eth = self.wei_to_eth(fee_wei)
fee_usd = self.eth_to_usd(fee_eth)
```

## توصیه‌های استفاده

### برای Bitcoin:
- مناسب برای تراکنش‌های کم فی
- سرعت بیشتر به دلیل API سادह‌تر
- فی‌های قابل پیش‌بینی‌تر

### برای Ethereum:
- مناسب برای تراکنش‌های پیچیده‌تر
- نیاز به API key برای عملکرد مطلوب
- فی‌های متغیر بر اساس ازدحام شبکه

## نتیجه‌گیری
هر دو برنامه با منطق یکسان کار می‌کنند اما برای ویژگی‌های خاص هر بلاکچین بهینه‌سازی شده‌اند. انتخاب بین آن‌ها بستگی به نیاز شما به بلاکچین خاص دارد.

## دستورات ترکیبی
می‌توانید هر دو برنامه را همزمان اجرا کنید:

```bash
# اجرای همزمان
python bitcoin_transaction_finder.py &
python ethereum_transaction_finder.py &
wait
```
