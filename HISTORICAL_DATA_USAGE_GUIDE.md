# راهنمای استفاده از سیستم داده‌های تاریخی
# Historical Data System Usage Guide

## مشکل اصلی و راه حل

### مشکل قبلی:
- فقط 136 ارز از 1130 ارز پردازش شد
- خطاهای Rate Limiting زیاد
- عدم مدیریت صحیح خطاهای API
- عدم وجود batch processing مناسب

### راه حل‌های پیاده شده:
✅ **بهبود مدیریت Rate Limiting**
✅ **اضافه کردن Retry Logic پیشرفته** 
✅ **پردازش Batch بهینه شده**
✅ **بهبود Error Handling**
✅ **Progressive Delay System**

## فایل‌های بهبود یافته

### 1. `Currencies/historical_data_service.py`
**تغییرات اصلی:**
- اضافه شدن retry logic با 3 تلاش
- مدیریت پیشرفته rate limiting (429, 401, 403)
- Progressive delay: 30s, 60s, 90s
- محدود کردن CMC IDs به 100 (محدودیت API)
- Batch processing با انتظار 30 ثانیه بین batch ها

### 2. `improved_historical_fetcher.py` (جدید)
**ویژگی‌های جدید:**
- رابط کاربری آسان
- گزینه‌های مختلف: کامل، اخیر، نمونه، سفارشی
- آمار دقیق و گزارش‌گیری بهتر
- مدیریت خطای پیشرفته

### 3. `historical_data_fetcher_1year.py`
**بهبودهای اعمال شده:**
- افزایش batch size از 5 به 25
- افزایش delay بین batch ها از 30 به 60 ثانیه
- افزایش delay بین requests از 0.5 به 2 ثانیه

## نحوه استفاده

### روش 1: استفاده از فایل بهبود یافته (توصیه شده)
```bash
python improved_historical_fetcher.py
```

**گزینه‌های موجود:**
1. **دریافت کامل (1 سال)**: همه 1130 ارز، 365 روز
2. **دریافت اخیر (30 روز)**: همه ارزها، 30 روز اخیر
3. **تست نمونه**: 20 ارز، 90 روز (برای تست)
4. **سفارشی**: تعیین تعداد روز و batch size

### روش 2: استفاده مستقیم از سرویس
```python
from Currencies.historical_data_service import HistoricalDataService
from datetime import datetime, timedelta

service = HistoricalDataService()

# تاریخ 30 روز گذشته
end_date = datetime.now()
start_date = end_date - timedelta(days=30)

result = service.store_historical_data(
    currency_ids=[1, 16, 3],  # BTC, ETH, BNB
    time_start=start_date.isoformat() + "Z",
    time_end=end_date.isoformat() + "Z",
    interval="daily",
    fiat_currencies=["USD"],
    batch_size=25
)
```

## پارامترهای بهینه

### تنظیمات Rate Limiting:
- **Batch Size**: 25 ارز در هر batch
- **Delay بین Batch ها**: 60 ثانیه
- **Max Retries**: 3 تلاش
- **Progressive Delay**: 30s → 60s → 90s
- **CMC ID Limit**: 100 (محدودیت API)

### تنظیمات Timeout:
- **Request Timeout**: 60 ثانیه
- **Connection Retry**: 20 ثانیه انتظار
- **Rate Limit Retry**: 60-180 ثانیه انتظار

## مدیریت خطاها

### خطاهای رایج و راه حل:
1. **Rate Limit (429)**: انتظار Progressive و تلاش مجدد
2. **Unauthorized (401)**: تغییر API key و تلاش مجدد  
3. **Forbidden (403)**: لاگ خطا و توقف
4. **Timeout**: انتظار و تلاش مجدد
5. **Connection Error**: انتظار طولانی‌تر و تلاش مجدد

### نمونه Log موفق:
```
📊 آمار نهایی - Improved Historical Fetcher
🕐 زمان شروع: 2025-09-15 16:00:00
🕐 زمان پایان: 2025-09-15 18:30:00
⏱️ مدت زمان کل: 2:30:00

📊 آمار پردازش:
   🔢 کل ارزها: 1130
   ✅ پردازش شده: 1100
   ❌ ناموفق: 30
   📈 نرخ موفقیت: 97.3%

💾 آمار دیتابیس:
   📈 رکوردهای جدید: 401,500
   🌐 تعداد API calls: 46
   📊 میانگین رکورد/ارز: 365.0
```

## نکات مهم

### برای بهترین نتیج:
1. **زمان اجرا**: اجرا در ساعات کم ترافیک
2. **API Keys**: استفاده از چندین کلید معتبر
3. **Monitoring**: نظارت بر لاگ‌ها حین اجرا
4. **Patience**: صبر برای تکمیل فرآیند (2-4 ساعت)

### اگر باز هم مشکل داشتید:
1. **کاهش Batch Size**: از 25 به 10 یا 15
2. **افزایش Delay**: از 60 به 120 ثانیه
3. **استفاده از تست نمونه**: ابتدا 50 ارز تست کنید
4. **بررسی API Keys**: اطمینان از اعتبار کلیدها

## مقایسه نتایج

### قبل از بهبود:
- ✅ پردازش شده: 136/1130 (12%)
- 📈 رکوردها: 44,465
- 🌐 API calls: 1,582
- ❌ خطاها: 113 خطا روی هر کلید

### بعد از بهبود (انتظار):
- ✅ پردازش شده: 1100+/1130 (97%+)
- 📈 رکوردها: 400,000+
- 🌐 API calls: 50-60
- ❌ خطاها: کمتر از 5%

---

## تست سریع

برای تست سریع سیستم بهبود یافته:

```bash
python improved_historical_fetcher.py
# انتخاب گزینه 3 (تست نمونه)
```

این تست 20 ارز را در 90 روز گذشته بررسی می‌کند و باید در کمتر از 30 دقیقه تکمیل شود.


