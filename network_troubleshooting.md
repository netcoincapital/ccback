# Network Troubleshooting Guide
راهنمای رفع مشکلات شبکه

## مشکلات شایع شبکه

### 🔴 خطای "Network is unreachable"
این خطا زمانی رخ می‌دهد که برنامه نتواند به API های اینترنتی متصل شود.

#### علل احتمالی:
1. **قطعی اینترنت** - اتصال اینترنت شما قطع است
2. **فیلتر IP** - IP شما توسط سرویس مسدود شده
3. **فایروال** - فایروال محلی ترافیک را مسدود می‌کند
4. **DNS مشکل** - سرور DNS پاسخ نمی‌دهد
5. **محدودیت ای‌اس‌پی** - ارائه‌دهنده اینترنت دسترسی را محدود کرده

### 🟡 خطای "Rate limit exceeded"  
API ها محدودیت تعداد درخواست در زمان معین دارند.

## راه‌حل‌ها

### 1️⃣ **حالت آفلاین (Offline Mode)**
```bash
# اجرا با حالت آفلاین
python bitcoin_transaction_finder.py --offline

# یا
python bitcoin_transaction_finder.py --no-network
```

در این حالت:
- ✅ برنامه بدون بررسی موجودی کار می‌کند
- ✅ همه آدرس‌ها به عنوان کیف پول جدید در نظر گرفته می‌شوند
- ✅ فقط صرافی‌های شناخته شده فیلتر می‌شوند

### 2️⃣ **استفاده از VPN**
```bash
# نصب و راه‌اندازی VPN
# سپس اجرای برنامه
python bitcoin_transaction_finder.py
```

### 3️⃣ **تنظیم DNS**
```bash
# تغییر DNS به گوگل
echo "nameserver 8.8.8.8" | sudo tee /etc/resolv.conf
echo "nameserver 8.8.4.4" | sudo tee -a /etc/resolv.conf
```

### 4️⃣ **بررسی اتصال**
```bash
# تست ping
ping -c 4 mempool.space
ping -c 4 8.8.8.8

# تست DNS
nslookup mempool.space
```

### 5️⃣ **استفاده از Proxy**
```python
# اضافه کردن proxy به درخواست‌ها
proxies = {
    'http': 'http://proxy-server:port',
    'https': 'https://proxy-server:port'
}

response = requests.get(url, proxies=proxies)
```

## تشخیص مشکل

### ✅ تست‌های اولیه:
```bash
# 1. تست اتصال اینترنت
curl -I https://google.com

# 2. تست دسترسی به API بیت کوین
curl -I https://mempool.space/api

# 3. تست DNS
nslookup mempool.space

# 4. تست با IP مستقیم
curl -I https://176.9.59.110/api
```

### 📊 بررسی خروجی خطا:
| خطا | علت احتمالی | راه‌حل |
|-----|-------------|--------|
| `Network is unreachable` | قطعی اینترنت | حالت آفلاین |
| `Connection timeout` | DNS یا فایروال | تغییر DNS |
| `403 Forbidden` | IP مسدود | VPN |
| `429 Too Many Requests` | Rate limit | کاهش سرعت |

## تنظیمات پیشرفته

### 🔧 تنظیم Timeout بیشتر:
```python
# در کد، timeout را افزایش دهید
response = requests.get(url, timeout=30)  # 30 ثانیه
```

### 🔧 استفاده از User-Agent:
```python
headers = {'User-Agent': 'Bitcoin-Transaction-Finder/1.0'}
response = requests.get(url, headers=headers)
```

### 🔧 Retry Mechanism:
```python
import time
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry

session = requests.Session()
retry = Retry(total=3, backoff_factor=0.3)
adapter = HTTPAdapter(max_retries=retry)
session.mount('http://', adapter)
session.mount('https://', adapter)
```

## متغیرهای محیطی مفید

```bash
# تنظیم proxy
export HTTP_PROXY=http://proxy:port
export HTTPS_PROXY=https://proxy:port

# تنظیم timeout
export REQUESTS_TIMEOUT=30

# حالت دیباگ
export DEBUG_NETWORK=1
```

## حالت‌های مختلف اجرا

### 🌐 **حالت آنلاین (پیش‌فرض):**
```bash
python bitcoin_transaction_finder.py
```
- بررسی کامل موجودی آدرس‌ها
- دقت بالا در تشخیص کیف پول‌های جدید

### 🔶 **حالت آفلاین:**
```bash
python bitcoin_transaction_finder.py --offline
```
- بدون بررسی موجودی
- همه آدرس‌ها به عنوان کیف پول جدید
- سرعت بالا

### ⚡ **حالت سریع:**
```bash
python bitcoin_transaction_finder.py --fast
```
- کمتر بلاک بررسی می‌شود
- timeout کوتاه‌تر

## API های جایگزین

اگر `mempool.space` در دسترس نیست:

### 1. **Blockchain.info:**
```python
self.api_url = "https://blockchain.info/rawaddr/{address}"
```

### 2. **Blockchair:**
```python
self.api_url = "https://api.blockchair.com/bitcoin/dashboards/address/{address}"
```

### 3. **Blockcypher:**
```python
self.api_url = "https://api.blockcypher.com/v1/btc/main/addrs/{address}"
```

## پیام‌های خطای رایج

### ❌ `ConnectionError`:
```
requests.exceptions.ConnectionError: HTTPSConnectionPool(host='mempool.space', port=443): 
Max retries exceeded with url: /api/address/...
```
**راه‌حل:** حالت آفلاین یا VPN

### ❌ `Timeout`:
```
requests.exceptions.ReadTimeout: HTTPSConnectionPool(host='mempool.space', port=443): 
Read timed out.
```
**راه‌حل:** افزایش timeout یا حالت آفلاین

### ❌ `HTTPError 429`:
```
requests.exceptions.HTTPError: 429 Client Error: Too Many Requests
```
**راه‌حل:** کاهش سرعت یا API key

## نتیجه‌گیری

برنامه طوری طراحی شده که حتی در صورت مشکلات شبکه هم کار کند:

✅ **Retry mechanism** - تلاش مجدد خودکار  
✅ **Offline mode** - حالت آفلاین  
✅ **Graceful degradation** - کاهش تدریجی قابلیت‌ها  
✅ **Error handling** - مدیریت خطا  

برای بهترین نتیجه، ابتدا حالت آفلاین را امتحان کنید:
```bash
python bitcoin_transaction_finder.py --offline
```
