# 📊 فرمت‌های JSON جدید API های Prices و Chart

## 🔗 API Endpoints

### 1. **Prices API** - `/prices` (POST)
### 2. **Chart API** - `/chart-data` (POST)

---

## 💰 **Prices API**

### 📤 **Request Format (ارسال):**

```json
{
  "Symbol": ["BTC", "ETH", "ADA", "DOGE"],
  "FiatCurrencies": ["USD", "EUR", "IRR"]
}
```

#### **پارامترهای Request:**
- **`Symbol`** (array): لیست نمادهای ارزهای دیجیتال
- **`FiatCurrencies`** (array): لیست ارزهای فیات مورد نظر

### 📥 **Response Format (دریافت):**

```json
{
  "status": "success",
  "data": {
    "BTC": {
      "USD": {
        "price": 65432.50,
        "change_24h": 2.45,
        "change_percentage_24h": 3.89,
        "market_cap": 1234567890123,
        "volume_24h": 98765432109,
        "last_updated": "2025-09-01T10:30:45Z",
        "timestamp": 1725186645,
        "formatted_price": "$65,432.50",
        "formatted_change": "+2.45%",
        "trend": "up"
      },
      "EUR": {
        "price": 58789.25,
        "change_24h": 2.20,
        "change_percentage_24h": 3.89,
        "market_cap": 1111111111111,
        "volume_24h": 88888888888,
        "last_updated": "2025-09-01T10:30:45Z",
        "timestamp": 1725186645,
        "formatted_price": "€58,789.25",
        "formatted_change": "+2.20%",
        "trend": "up"
      },
      "IRR": {
        "price": 2750000000,
        "change_24h": 103000000,
        "change_percentage_24h": 3.89,
        "market_cap": 51850000000000000,
        "volume_24h": 4150000000000,
        "last_updated": "2025-09-01T10:30:45Z",
        "timestamp": 1725186645,
        "formatted_price": "۲,۷۵۰,۰۰۰,۰۰۰ ریال",
        "formatted_change": "+۱۰۳,۰۰۰,۰۰۰ ریال",
        "trend": "up"
      }
    },
    "ETH": {
      "USD": {
        "price": 4450.75,
        "change_24h": -125.30,
        "change_percentage_24h": -2.74,
        "market_cap": 535000000000,
        "volume_24h": 15000000000,
        "last_updated": "2025-09-01T10:30:45Z",
        "timestamp": 1725186645,
        "formatted_price": "$4,450.75",
        "formatted_change": "-2.74%",
        "trend": "down"
      }
    }
  },
  "metadata": {
    "total_requested": 4,
    "total_found": 2,
    "missing_symbols": ["ADA", "DOGE"],
    "fiat_currencies": ["USD", "EUR", "IRR"],
    "request_timestamp": "2025-09-01T10:30:45Z",
    "cache_status": "fresh",
    "response_time_ms": 145
  }
}
```

#### **فیلدهای Response:**
- **`price`**: قیمت فعلی
- **`change_24h`**: تغییر 24 ساعته (مقدار مطلق)
- **`change_percentage_24h`**: درصد تغییر 24 ساعته
- **`market_cap`**: ارزش بازار
- **`volume_24h`**: حجم معاملات 24 ساعته
- **`last_updated`**: آخرین به‌روزرسانی (ISO format)
- **`timestamp`**: timestamp یونیکس
- **`formatted_price`**: قیمت فرمت شده با واحد
- **`formatted_change`**: تغییر فرمت شده
- **`trend`**: جهت قیمت ("up", "down", "stable")

---

## 📈 **Chart API**

### 📤 **Request Format (ارسال):**

```json
{
  "Symbol": "BTC",
  "FiatCurrency": "USD",
  "timeframe": "1d",
  "points": 100
}
```

#### **پارامترهای Request:**
- **`Symbol`** (string): نماد ارز دیجیتال
- **`FiatCurrency`** (string): ارز فیات (پیش‌فرض: USD)
- **`timeframe`** (string): بازه زمانی
  - `1h`: 1 ساعت
  - `1d`: 1 روز
  - `1w`: 1 هفته
  - `1m`: 1 ماه
  - `3m`: 3 ماه
  - `6m`: 6 ماه
  - `1y`: 1 سال
- **`points`** (integer): حداکثر تعداد نقاط (پیش‌فرض: 100)

### 📥 **Response Format (دریافت):**

```json
{
  "status": "success",
  "data": {
    "symbol": "BTC",
    "fiat_currency": "USD",
    "timeframe": "1d",
    "total_points": 24,
    "price_data": [
      {
        "timestamp": 1725100800,
        "datetime": "2025-08-31T10:00:00Z",
        "price": 65000.00,
        "volume": 1200000000,
        "market_cap": 1280000000000,
        "change_from_previous": 150.25,
        "change_percentage": 0.23
      },
      {
        "timestamp": 1725104400,
        "datetime": "2025-08-31T11:00:00Z",
        "price": 65150.25,
        "volume": 1250000000,
        "market_cap": 1283000000000,
        "change_from_previous": 150.25,
        "change_percentage": 0.23
      },
      {
        "timestamp": 1725108000,
        "datetime": "2025-08-31T12:00:00Z",
        "price": 64980.50,
        "volume": 1180000000,
        "market_cap": 1281000000000,
        "change_from_previous": -169.75,
        "change_percentage": -0.26
      }
    ],
    "statistics": {
      "highest_price": 65432.50,
      "lowest_price": 64120.00,
      "average_price": 64776.25,
      "total_volume": 28800000000,
      "price_change_24h": 312.50,
      "percentage_change_24h": 0.48,
      "volatility": 2.15
    },
    "current_price": {
      "price": 65432.50,
      "last_updated": "2025-09-01T10:30:45Z",
      "trend": "up"
    }
  },
  "metadata": {
    "request_timestamp": "2025-09-01T10:30:45Z",
    "data_source": "database",
    "cache_status": "fresh",
    "response_time_ms": 89,
    "interval_minutes": 60,
    "data_quality": "complete"
  }
}
```

#### **فیلدهای Chart Response:**
- **`price_data`**: آرایه نقاط قیمت
  - **`timestamp`**: زمان یونیکس
  - **`datetime`**: تاریخ ISO
  - **`price`**: قیمت در آن لحظه
  - **`volume`**: حجم معاملات
  - **`market_cap`**: ارزش بازار
  - **`change_from_previous`**: تغییر از نقطه قبلی
  - **`change_percentage`**: درصد تغییر

- **`statistics`**: آمار کلی بازه
  - **`highest_price`**: بالاترین قیمت
  - **`lowest_price`**: پایین‌ترین قیمت
  - **`average_price`**: میانگین قیمت
  - **`volatility`**: نوسان قیمت

---

## 🔄 **مثال‌های کاربرد**

### **دریافت قیمت چند ارز:**

```javascript
// Request
const response = await fetch('/api/prices', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    Symbol: ["BTC", "ETH", "BNB"],
    FiatCurrencies: ["USD", "EUR"]
  })
});

const data = await response.json();
console.log(data.data.BTC.USD.price); // 65432.50
```

### **دریافت داده‌های چارت:**

```javascript
// Request
const response = await fetch('/api/chart-data', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    Symbol: "ETH",
    FiatCurrency: "USD",
    timeframe: "1d",
    points: 24
  })
});

const data = await response.json();
console.log(data.data.price_data); // آرایه 24 نقطه
```

---

## ⚡ **ویژگی‌های جدید**

### ✅ **Prices API:**
- **Rate Limiting:** 100 درخواست در دقیقه
- **Multi-Currency:** پشتیبانی همزمان چند ارز
- **Formatted Output:** قیمت‌های فرمت شده
- **Trend Detection:** تشخیص جهت قیمت
- **Cache Management:** مدیریت کش هوشمند

### ✅ **Chart API:**
- **Rate Limiting:** 200 درخواست در دقیقه
- **Multiple Timeframes:** 7 بازه زمانی مختلف
- **Optimized Points:** تعداد نقاط قابل تنظیم
- **Statistical Analysis:** آمار کامل بازه
- **Real-time Updates:** به‌روزرسانی لحظه‌ای

### ✅ **Security Features:**
- **Input Validation:** اعتبارسنجی ورودی‌ها
- **Error Handling:** مدیریت خطاهای کامل
- **Rate Limiting:** محدودیت نرخ درخواست
- **Logging:** ثبت کامل عملیات

---

## 🛠️ **Error Responses**

### خطای اعتبارسنجی:
```json
{
  "status": "error",
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Invalid symbol format",
    "details": {
      "field": "Symbol",
      "value": "INVALID_SYMBOL",
      "expected": "Valid cryptocurrency symbol"
    }
  },
  "timestamp": "2025-09-01T10:30:45Z"
}
```

### خطای Rate Limit:
```json
{
  "status": "error",
  "error": {
    "code": "RATE_LIMIT_EXCEEDED",
    "message": "Too many requests",
    "details": {
      "limit": 100,
      "window": 60,
      "retry_after": 45
    }
  },
  "timestamp": "2025-09-01T10:30:45Z"
}
```
