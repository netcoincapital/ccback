# 🔄 خلاصه تغییرات API های Prices و Chart

## 📅 **تاریخ آپدیت:** چند روز پیش

---

## 🆕 **تغییرات کلیدی**

### 1. **🔐 Security Enhancements**
- **Rate Limiting:** محدودیت تعداد درخواست
- **Input Validation:** اعتبارسنجی ورودی‌ها
- **Error Handling:** مدیریت خطاهای بهتر

### 2. **📊 Response Structure**
- **Standardized Format:** فرمت یکپارچه پاسخ‌ها
- **Metadata:** اطلاعات اضافی درخواست
- **Formatted Output:** خروجی فرمت شده

### 3. **⚡ Performance Improvements**
- **Database Optimization:** بهینه‌سازی کوئری‌ها
- **Caching:** کش هوشمند
- **Response Time:** کاهش زمان پاسخ

---

## 💰 **Prices API - تغییرات**

### **قبل:**
```json
{
  "BTC": 65000,
  "ETH": 4400
}
```

### **بعد:**
```json
{
  "status": "success",
  "data": {
    "BTC": {
      "USD": {
        "price": 65432.50,
        "change_24h": 2.45,
        "change_percentage_24h": 3.89,
        "formatted_price": "$65,432.50",
        "formatted_change": "+2.45%",
        "trend": "up",
        "last_updated": "2025-09-01T10:30:45Z"
      }
    }
  },
  "metadata": {
    "total_requested": 1,
    "total_found": 1,
    "response_time_ms": 145
  }
}
```

### **ویژگی‌های جدید:**
- ✅ **Multi-Currency Support**: پشتیبانی چند ارز فیات
- ✅ **Formatted Prices**: قیمت‌های فرمت شده
- ✅ **24h Changes**: تغییرات 24 ساعته
- ✅ **Trend Detection**: تشخیص جهت قیمت
- ✅ **Metadata**: اطلاعات درخواست
- ✅ **Error Details**: جزئیات خطاها

---

## 📈 **Chart API - تغییرات**

### **قبل:**
```json
{
  "prices": [65000, 65100, 64900],
  "timestamps": [1725100800, 1725104400, 1725108000]
}
```

### **بعد:**
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
        "change_from_previous": 150.25,
        "change_percentage": 0.23
      }
    ],
    "statistics": {
      "highest_price": 65432.50,
      "lowest_price": 64120.00,
      "average_price": 64776.25,
      "percentage_change_24h": 0.48,
      "volatility": 2.15
    },
    "current_price": {
      "price": 65432.50,
      "trend": "up"
    }
  }
}
```

### **ویژگی‌های جدید:**
- ✅ **Rich Data Points**: اطلاعات کامل هر نقطه
- ✅ **Statistical Analysis**: آمار کامل بازه
- ✅ **Multiple Timeframes**: 7 بازه زمانی
- ✅ **Volume Data**: حجم معاملات
- ✅ **Change Calculations**: محاسبه تغییرات
- ✅ **Current Price**: قیمت فعلی جداگانه

---

## 🔄 **Migration Guide**

### **Frontend Changes Required:**

#### **Prices API:**
```javascript
// قبل
const price = response.BTC; // 65000

// بعد  
const price = response.data.BTC.USD.price; // 65432.50
const formatted = response.data.BTC.USD.formatted_price; // "$65,432.50"
const trend = response.data.BTC.USD.trend; // "up"
```

#### **Chart API:**
```javascript
// قبل
const prices = response.prices; // [65000, 65100]
const times = response.timestamps; // [1725100800, 1725104400]

// بعد
const chartData = response.data.price_data;
chartData.forEach(point => {
  console.log(point.datetime, point.price, point.volume);
});

const stats = response.data.statistics;
console.log('High:', stats.highest_price);
console.log('Low:', stats.lowest_price);
```

### **Backend Changes Required:**

#### **Request Format:**
```python
# قبل
payload = {"symbols": ["BTC", "ETH"]}

# بعد
payload = {
    "Symbol": ["BTC", "ETH"],
    "FiatCurrencies": ["USD", "EUR"]
}
```

#### **Response Parsing:**
```python
# قبل
btc_price = response['BTC']

# بعد
if response['status'] == 'success':
    btc_price = response['data']['BTC']['USD']['price']
    btc_trend = response['data']['BTC']['USD']['trend']
else:
    print(f"Error: {response['error']['message']}")
```

---

## 🛡️ **Security & Rate Limiting**

### **Headers مورد نیاز:**
```bash
Content-Type: application/json
User-Agent: YourApp/1.0
```

### **Rate Limits:**
- **Prices API**: 100 req/min
- **Chart API**: 200 req/min

### **Error Codes:**
- **400**: Bad Request (ورودی نامعتبر)
- **429**: Too Many Requests (Rate limit)
- **500**: Internal Server Error
- **503**: Service Unavailable

---

## 📋 **Validation Rules**

### **Prices API:**
- `Symbol`: حداقل 1، حداکثر 50 نماد
- `FiatCurrencies`: حداقل 1، حداکثر 10 ارز فیات
- نمادها باید معتبر باشند (BTC, ETH, etc.)

### **Chart API:**
- `Symbol`: یک نماد معتبر
- `timeframe`: یکی از مقادیر مجاز
- `points`: بین 1 تا 10000
- `FiatCurrency`: ارز فیات معتبر

---

## 🧪 **تست API ها**

### **Python Test:**
```bash
python test_local_apis.py
```

### **cURL Test:**
```bash
# تست سریع
curl -X POST localhost:5000/api/prices \
  -H "Content-Type: application/json" \
  -d '{"Symbol":["BTC"],"FiatCurrencies":["USD"]}'
```

### **Browser Test:**
```javascript
fetch('/api/prices', {
  method: 'POST',
  headers: {'Content-Type': 'application/json'},
  body: JSON.stringify({Symbol:['BTC'], FiatCurrencies:['USD']})
})
.then(r => r.json())
.then(console.log);
```

---

## 📞 **Support**

در صورت مشکل در استفاده از API های جدید:

1. **بررسی فرمت درخواست** - باید دقیقاً مطابق نمونه باشد
2. **چک کردن Rate Limits** - آیا از حد مجاز عبور کرده‌اید؟
3. **بررسی Response Status** - همیشه `status` فیلد را چک کنید
4. **مطالعه Error Messages** - پیام‌های خطا راهنمای خوبی هستند

**API های جدید قدرتمندتر، ایمن‌تر و کامل‌تر هستند! 🚀**
