# 📈 استراتژی استفاده از API ها برای چارت‌های قیمتی

## 🎯 **توصیه‌های API برای هر بازه زمانی:**

### ⏰ **1 ساعته (1h)**
```json
API: /api/chart-data
Request: {
  "Symbol": "BTC",
  "FiatCurrency": "USD", 
  "timeframe": "1h",
  "points": 60,
  "include_volume": true
}
```
**دلیل:** داده‌های تازه و دقیق برای نمایش کوتاه مدت

---

### 📅 **1 روزه (1d)**
```json
API: /api/chart-data
Request: {
  "Symbol": "BTC",
  "FiatCurrency": "USD",
  "timeframe": "1d", 
  "points": 24,
  "include_indicators": true
}
```
**دلیل:** بهینه برای نمایش روزانه با اندیکاتورهای تکنیکال

---

### 📆 **1 هفته‌ای (1w)**
```json
API: /api/chart-data
Request: {
  "Symbol": "BTC",
  "FiatCurrency": "USD",
  "timeframe": "1w",
  "points": 168,
  "include_indicators": true
}
```
**دلیل:** داده‌های ساعتی برای نمایش هفتگی دقیق

---

### 🗓️ **1 ماهه (1m)**
```json
API: /api/historical-prices (اولویت اول)
Request: {
  "Symbol": ["BTC"],
  "FiatCurrency": "USD",
  "time_start": "2024-08-01T00:00:00Z",
  "time_end": "2024-08-31T23:59:59Z", 
  "interval": "daily"
}

یا

API: /api/chart-data (جایگزین)
Request: {
  "Symbol": "BTC",
  "FiatCurrency": "USD",
  "timeframe": "1m",
  "points": 30
}
```
**دلیل:** داده‌های تاریخی دقیق‌تر برای بازه ماهانه

---

### 📊 **3 ماهه (3m)**
```json
API: /api/historical-prices (توصیه شده)
Request: {
  "Symbol": ["BTC"],
  "FiatCurrency": "USD",
  "time_start": "2024-06-01T00:00:00Z",
  "time_end": "2024-08-31T23:59:59Z",
  "interval": "daily"
}

یا

API: /api/chart-data
Request: {
  "Symbol": "BTC", 
  "FiatCurrency": "USD",
  "timeframe": "3m",
  "points": 90
}
```
**دلیل:** داده‌های تاریخی کامل برای تحلیل میان مدت

---

### 📈 **1 ساله (1y)**
```json
API: /api/historical-prices-bulk (اولویت اول)
Request: {
  "Symbol": ["BTC"],
  "months": 12,
  "interval": "daily",
  "fiat_currencies": ["USD"]
}

سپس استفاده از:

API: /api/historical-prices
Request: {
  "Symbol": ["BTC"],
  "FiatCurrency": "USD", 
  "time_start": "2024-01-01T00:00:00Z",
  "time_end": "2024-12-31T23:59:59Z",
  "interval": "daily"
}
```
**دلیل:** نیاز به داده‌های bulk برای بازه طولانی

---

## 🔄 **استراتژی ترکیبی (پیشنهادی):**

### **برای چارت Real-time:**
```javascript
// 1. دریافت داده‌های اصلی چارت
const chartData = await fetch('/api/chart-data', {
  method: 'POST',
  headers: {'Content-Type': 'application/json'},
  body: JSON.stringify({
    Symbol: 'BTC',
    timeframe: '1d',
    points: 24,
    include_indicators: true
  })
});

// 2. آپدیت زنده (هر 30 ثانیه)
setInterval(async () => {
  const liveUpdate = await fetch('/api/chart-live-update', {
    method: 'POST', 
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({
      Symbol: ['BTC'],
      FiatCurrency: 'USD'
    })
  });
  
  const data = await liveUpdate.json();
  // آپدیت آخرین نقطه چارت
  updateLastChartPoint(data.data.live_prices.BTC);
}, 30000);
```

---

## 🎨 **پیاده‌سازی کامل چارت:**

### **کامپوننت React نمونه:**
```jsx
import React, { useState, useEffect } from 'react';

const CryptoPriceChart = ({ symbol, timeframe }) => {
  const [chartData, setChartData] = useState(null);
  const [livePrice, setLivePrice] = useState(null);
  
  // دریافت داده‌های اولیه چارت
  useEffect(() => {
    const fetchChartData = async () => {
      const response = await fetch('/api/chart-data', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
          Symbol: symbol,
          FiatCurrency: 'USD',
          timeframe: timeframe,
          points: getPointsForTimeframe(timeframe),
          include_indicators: true
        })
      });
      
      const data = await response.json();
      if (data.status === 'success') {
        setChartData(data.data);
      }
    };
    
    fetchChartData();
  }, [symbol, timeframe]);
  
  // آپدیت زنده
  useEffect(() => {
    const interval = setInterval(async () => {
      const response = await fetch('/api/chart-live-update', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
          Symbol: [symbol],
          FiatCurrency: 'USD'
        })
      });
      
      const data = await response.json();
      if (data.status === 'success') {
        setLivePrice(data.data.live_prices[symbol]);
      }
    }, 30000); // هر 30 ثانیه
    
    return () => clearInterval(interval);
  }, [symbol]);
  
  const getPointsForTimeframe = (tf) => {
    const pointsMap = {
      '1h': 60,
      '1d': 24, 
      '1w': 168,
      '1m': 30,
      '3m': 90,
      '1y': 365
    };
    return pointsMap[tf] || 100;
  };
  
  return (
    <div className="crypto-chart">
      {chartData && (
        <div>
          <h3>{chartData.symbol} - {timeframe}</h3>
          {/* رسم چارت با chartData.price_data */}
          <Chart data={chartData.price_data} />
          
          {/* نمایش اندیکاتورها */}
          {chartData.technical_indicators && (
            <TechnicalIndicators data={chartData.technical_indicators} />
          )}
          
          {/* قیمت زنده */}
          {livePrice && (
            <LivePrice 
              price={livePrice.price_formatted}
              change={livePrice.change_formatted}
              trend={livePrice.trend}
            />
          )}
        </div>
      )}
    </div>
  );
};
```

---

## 📊 **جدول انتخاب API:**

| بازه زمانی | API اصلی | API پشتیبان | نقاط توصیه شده | فرکانس آپدیت |
|------------|----------|-------------|---------------|---------------|
| **1h** | `/chart-data` | `/chart-live-update` | 60 | هر 30 ثانیه |
| **1d** | `/chart-data` | `/chart-live-update` | 24 | هر 1 دقیقه |
| **1w** | `/chart-data` | `/historical-prices` | 168 | هر 5 دقیقه |
| **1m** | `/historical-prices` | `/chart-data` | 30-720 | هر 30 دقیقه |
| **3m** | `/historical-prices` | `/chart-data` | 90 | هر ساعت |
| **1y** | `/historical-prices-bulk` + `/historical-prices` | - | 365 | روزانه |

---

## 🔄 **الگوی پیشنهادی برای هر بازه:**

### **⚡ بازه‌های کوتاه (1h, 1d):**
1. **API اصلی:** `/chart-data`
2. **آپدیت زنده:** `/chart-live-update`
3. **فرکانس:** 30 ثانیه - 1 دقیقه

### **📊 بازه‌های متوسط (1w, 1m):**
1. **API اصلی:** `/historical-prices`
2. **API پشتیبان:** `/chart-data`
3. **فرکانس:** 5-30 دقیقه

### **📈 بازه‌های طولانی (3m, 1y):**
1. **آماده‌سازی:** `/historical-prices-bulk`
2. **دریافت:** `/historical-prices`
3. **فرکانس:** ساعتی یا روزانه

---

## 💡 **نکات بهینه‌سازی:**

### **1. کش کردن داده‌ها:**
```javascript
// کش محلی برای داده‌های چارت
const chartCache = new Map();

async function getCachedChartData(symbol, timeframe) {
  const cacheKey = `${symbol}-${timeframe}`;
  const cached = chartCache.get(cacheKey);
  
  if (cached && Date.now() - cached.timestamp < 300000) { // 5 دقیقه
    return cached.data;
  }
  
  const freshData = await fetchChartData(symbol, timeframe);
  chartCache.set(cacheKey, {
    data: freshData,
    timestamp: Date.now()
  });
  
  return freshData;
}
```

### **2. آپدیت تدریجی:**
```javascript
// فقط آپدیت آخرین نقطه برای بازه‌های کوتاه
async function updateLastPoint(symbol) {
  const liveData = await getLiveUpdate(symbol);
  // جایگزینی آخرین نقطه چارت
  chartData[chartData.length - 1] = {
    ...chartData[chartData.length - 1],
    price: liveData.price,
    timestamp: Date.now()
  };
}
```

**با این استراتژی، چارت‌های شما همیشه به‌روز و بهینه خواهند بود! 🚀**
