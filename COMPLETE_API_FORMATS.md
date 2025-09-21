# 🔄 فرمت‌های کامل API های آپدیت شده

## 📋 **لیست API ها:**

1. **Manual Update** - `/manual-update`
2. **Automatic All Currencies** - `/historical-prices-auto`
3. **Long-term Data** - `/historical-prices-bulk`
4. **Custom Historical Data** - `/historical-prices`
5. **Live Chart Update** - `/chart-live-update`
6. **Main Chart** - `/chart-data`

---

## 1. 🔧 **Manual Update API**

### **Endpoint:** `POST /api/manual-update`

#### **📤 Request:**
```json
{
  "Symbol": ["BTC", "ETH"],
  "FiatCurrencies": ["USD", "EUR"],
  "force_update": true,
  "include_market_data": true
}
```

#### **📥 Response:**
```json
{
  "status": "success",
  "data": {
    "updated_currencies": ["BTC", "ETH"],
    "timestamp": "2025-09-01T10:30:45Z",
    "updates": {
      "BTC": {
        "USD": {
          "old_price": 65000.00,
          "new_price": 65432.50,
          "change": 432.50,
          "updated": true
        },
        "EUR": {
          "old_price": 58500.00,
          "new_price": 58789.25,
          "change": 289.25,
          "updated": true
        }
      }
    }
  },
  "metadata": {
    "total_requested": 2,
    "total_updated": 2,
    "response_time_ms": 234,
    "source": "manual"
  }
}
```

---

## 2. 🤖 **Automatic All Currencies API**

### **Endpoint:** `POST /api/historical-prices-auto`

#### **📤 Request:**
```json
{
  "time_start": "2024-08-01T00:00:00Z",
  "time_end": "2024-08-31T23:59:59Z",
  "interval": "daily",
  "fiat_currencies": ["USD", "EUR"],
  "max_currencies": 50
}
```

#### **📥 Response:**
```json
{
  "status": "success",
  "data": {
    "currencies_processed": 45,
    "records_added": 1395,
    "time_range": "2024-08-01T00:00:00Z to 2024-08-31T23:59:59Z",
    "interval": "daily",
    "processing_time_minutes": 12.5,
    "currencies_list": [
      {"symbol": "BTC", "name": "Bitcoin", "records": 31},
      {"symbol": "ETH", "name": "Ethereum", "records": 31},
      {"symbol": "ADA", "name": "Cardano", "records": 31}
    ]
  },
  "metadata": {
    "start_time": "2025-09-01T10:30:45Z",
    "end_time": "2025-09-01T10:43:15Z",
    "api_calls_made": 156,
    "success_rate": 98.5,
    "recommendation": "Use /historical-prices endpoint to retrieve stored data"
  }
}
```

---

## 3. 📊 **Long-term Data API**

### **Endpoint:** `POST /api/historical-prices-bulk`

#### **📤 Request:**
```json
{
  "Symbol": ["BTC", "ETH", "ADA"],
  "months": 12,
  "interval": "daily",
  "fiat_currencies": ["USD", "EUR"]
}
```

#### **📥 Response:**
```json
{
  "status": "success",
  "data": {
    "symbols_processed": ["BTC", "ETH", "ADA"],
    "months_processed": 12,
    "total_records_added": 1095,
    "batches_processed": 36,
    "processing_summary": {
      "BTC": {
        "records_added": 365,
        "success_rate": 100.0,
        "date_range": "2024-09-01 to 2025-08-31"
      },
      "ETH": {
        "records_added": 365,
        "success_rate": 99.7,
        "date_range": "2024-09-01 to 2025-08-31"
      },
      "ADA": {
        "records_added": 365,
        "success_rate": 98.9,
        "date_range": "2024-09-01 to 2025-08-31"
      }
    }
  },
  "metadata": {
    "processing_time_minutes": 45.2,
    "api_calls_made": 732,
    "start_time": "2025-09-01T10:00:00Z",
    "end_time": "2025-09-01T10:45:12Z",
    "recommendation": "Data is now available via /historical-prices endpoint"
  }
}
```

---

## 4. 📈 **Custom Historical Data API**

### **Endpoint:** `POST /api/historical-prices`

#### **📤 Request:**
```json
{
  "Symbol": ["BTC"],
  "FiatCurrency": "USD",
  "time_start": "2024-08-01T00:00:00Z",
  "time_end": "2024-08-31T23:59:59Z",
  "interval": "hourly",
  "include_volume": true,
  "include_market_cap": true
}
```

#### **📥 Response:**
```json
{
  "status": "success",
  "data": {
    "symbol": "BTC",
    "fiat_currency": "USD",
    "time_range": {
      "start": "2024-08-01T00:00:00Z",
      "end": "2024-08-31T23:59:59Z",
      "interval": "hourly",
      "total_points": 744
    },
    "historical_data": [
      {
        "timestamp": 1722470400,
        "datetime": "2024-08-01T00:00:00Z",
        "price": 64500.00,
        "market_cap": 1270000000000,
        "volume_24h": 28500000000,
        "change_1h": 0.25,
        "change_24h": 1.85,
        "change_7d": -2.15
      },
      {
        "timestamp": 1722474000,
        "datetime": "2024-08-01T01:00:00Z", 
        "price": 64625.50,
        "market_cap": 1272500000000,
        "volume_24h": 29200000000,
        "change_1h": 0.19,
        "change_24h": 2.04,
        "change_7d": -1.96
      }
    ],
    "statistics": {
      "period_high": 67890.00,
      "period_low": 62100.00,
      "period_average": 65245.75,
      "total_volume": 890000000000,
      "volatility": 8.45,
      "correlation_market": 0.87
    }
  },
  "metadata": {
    "data_source": "database",
    "cache_status": "fresh",
    "response_time_ms": 456,
    "data_quality": "complete"
  }
}
```

---

## 5. ⚡ **Live Chart Update API**

### **Endpoint:** `POST /api/chart-live-update`

#### **📤 Request:**
```json
{
  "Symbol": ["BTC", "ETH", "ADA"],
  "FiatCurrency": "USD"
}
```

#### **📥 Response:**
```json
{
  "status": "success",
  "data": {
    "live_prices": {
      "BTC": {
        "price": 65432.50,
        "market_cap": 1285000000000,
        "volume_24h": 32500000000,
        "change_1h": 0.15,
        "change_24h": 2.45,
        "change_7d": -1.25,
        "last_updated": "2025-09-01T10:30:45Z",
        "trend": "up",
        "price_formatted": "$65,432.50",
        "change_formatted": "+2.45%"
      },
      "ETH": {
        "price": 4450.75,
        "market_cap": 535000000000,
        "volume_24h": 15000000000,
        "change_1h": -0.05,
        "change_24h": -2.74,
        "change_7d": 5.12,
        "last_updated": "2025-09-01T10:30:45Z",
        "trend": "down",
        "price_formatted": "$4,450.75",
        "change_formatted": "-2.74%"
      }
    },
    "fiat_currency": "USD",
    "update_frequency": "real-time"
  },
  "metadata": {
    "timestamp": "2025-09-01T10:30:45Z",
    "response_time_ms": 89,
    "data_freshness": "live",
    "next_update_in_seconds": 30
  }
}
```

---

## 6. 📊 **Main Chart API**

### **Endpoint:** `POST /api/chart-data`

#### **📤 Request:**
```json
{
  "Symbol": "BTC",
  "FiatCurrency": "USD",
  "timeframe": "1w",
  "points": 168,
  "include_volume": true,
  "include_indicators": true
}
```

#### **📥 Response:**
```json
{
  "status": "success",
  "data": {
    "symbol": "BTC",
    "fiat_currency": "USD",
    "timeframe": "1w",
    "total_points": 168,
    "chart_config": {
      "interval_minutes": 60,
      "data_quality": "complete",
      "coverage_percentage": 99.4
    },
    "price_data": [
      {
        "timestamp": 1724889600,
        "datetime": "2024-08-29T00:00:00Z",
        "open": 64200.00,
        "high": 64750.00,
        "low": 63980.00,
        "close": 64500.00,
        "volume": 1200000000,
        "market_cap": 1270000000000,
        "change_from_previous": 300.00,
        "change_percentage": 0.47
      }
    ],
    "technical_indicators": {
      "sma_20": 64890.25,
      "ema_12": 65120.50,
      "rsi": 58.5,
      "macd": {
        "macd": 125.30,
        "signal": 98.75,
        "histogram": 26.55
      },
      "bollinger_bands": {
        "upper": 66500.00,
        "middle": 65000.00,
        "lower": 63500.00
      }
    },
    "statistics": {
      "period_high": 67890.00,
      "period_low": 62100.00,
      "period_average": 65245.75,
      "total_volume": 890000000000,
      "volatility": 8.45,
      "trend_strength": 0.72,
      "support_levels": [63500, 64200, 65000],
      "resistance_levels": [66000, 67000, 68500]
    },
    "current_status": {
      "price": 65432.50,
      "trend": "bullish",
      "momentum": "increasing",
      "last_updated": "2025-09-01T10:30:45Z"
    }
  },
  "metadata": {
    "request_timestamp": "2025-09-01T10:30:45Z",
    "response_time_ms": 234,
    "data_source": "database",
    "cache_status": "fresh"
  }
}
```

---

## 🔧 **cURL Examples**

### **Manual Update:**
```bash
curl -X POST http://localhost:5000/api/manual-update \
  -H "Content-Type: application/json" \
  -d '{
    "Symbol": ["BTC", "ETH"],
    "FiatCurrencies": ["USD"],
    "force_update": true
  }'
```

### **Automatic All Currencies:**
```bash
curl -X POST http://localhost:5000/api/historical-prices-auto \
  -H "Content-Type: application/json" \
  -d '{
    "time_start": "2024-08-01T00:00:00Z",
    "time_end": "2024-08-31T23:59:59Z",
    "interval": "daily",
    "max_currencies": 50
  }'
```

### **Long-term Data:**
```bash
curl -X POST http://localhost:5000/api/historical-prices-bulk \
  -H "Content-Type: application/json" \
  -d '{
    "Symbol": ["BTC", "ETH"],
    "months": 12,
    "interval": "daily",
    "fiat_currencies": ["USD"]
  }'
```

### **Custom Historical:**
```bash
curl -X POST http://localhost:5000/api/historical-prices \
  -H "Content-Type: application/json" \
  -d '{
    "Symbol": ["BTC"],
    "FiatCurrency": "USD",
    "time_start": "2024-08-01T00:00:00Z",
    "time_end": "2024-08-31T23:59:59Z",
    "interval": "hourly"
  }'
```

### **Live Chart Update:**
```bash
curl -X POST http://localhost:5000/api/chart-live-update \
  -H "Content-Type: application/json" \
  -d '{
    "Symbol": ["BTC", "ETH"],
    "FiatCurrency": "USD"
  }'
```

### **Main Chart:**
```bash
curl -X POST http://localhost:5000/api/chart-data \
  -H "Content-Type: application/json" \
  -d '{
    "Symbol": "BTC",
    "FiatCurrency": "USD",
    "timeframe": "1d",
    "points": 24,
    "include_indicators": true
  }'
```

---

## ⚡ **Rate Limits**

| API | Limit | Window |
|-----|-------|---------|
| Manual Update | 10 req | 60 sec |
| Auto All Currencies | 3 req | 3600 sec |
| Long-term Data | 2 req | 3600 sec |
| Custom Historical | 50 req | 60 sec |
| Live Chart Update | 500 req | 60 sec |
| Main Chart | 200 req | 60 sec |

---

## 📝 **Request Parameters**

### **Common Parameters:**
- **`Symbol`**: نماد ارز (string یا array)
- **`FiatCurrency/FiatCurrencies`**: ارز فیات
- **`time_start`**: زمان شروع (ISO format)
- **`time_end`**: زمان پایان (ISO format)
- **`interval`**: فاصله زمانی (`hourly`, `daily`, `weekly`)

### **Chart-Specific:**
- **`timeframe`**: بازه نمایش (`1h`, `1d`, `1w`, `1m`, `3m`, `6m`, `1y`)
- **`points`**: تعداد نقاط (1-10000)
- **`include_volume`**: شامل حجم معاملات
- **`include_indicators`**: شامل اندیکاتورهای تکنیکال

### **Update-Specific:**
- **`force_update`**: به‌روزرسانی اجباری
- **`max_currencies`**: حداکثر تعداد ارزها
- **`months`**: تعداد ماه برای داده طولانی مدت

---

## 🛡️ **Error Responses**

### **Validation Error:**
```json
{
  "status": "error",
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Invalid timeframe",
    "details": {
      "field": "timeframe",
      "value": "invalid_value",
      "allowed_values": ["1h", "1d", "1w", "1m", "3m", "6m", "1y"]
    }
  },
  "timestamp": "2025-09-01T10:30:45Z"
}
```

### **Rate Limit Error:**
```json
{
  "status": "error",
  "error": {
    "code": "RATE_LIMIT_EXCEEDED",
    "message": "Too many requests",
    "details": {
      "limit": 200,
      "window": 60,
      "current_count": 201,
      "retry_after": 45
    }
  },
  "timestamp": "2025-09-01T10:30:45Z"
}
```

### **Internal Error:**
```json
{
  "status": "error",
  "error": {
    "code": "INTERNAL_ERROR",
    "message": "Database connection failed",
    "details": {
      "error_id": "ERR_2025_09_01_103045_001",
      "contact_support": true
    }
  },
  "timestamp": "2025-09-01T10:30:45Z"
}
```

---

## 🔄 **Integration Examples**

### **Python Integration:**
```python
import requests

class CoinCeeperAPI:
    def __init__(self, base_url="http://localhost:5000/api"):
        self.base_url = base_url
    
    def manual_update(self, symbols, fiats=["USD"]):
        return requests.post(f"{self.base_url}/manual-update", json={
            "Symbol": symbols,
            "FiatCurrencies": fiats,
            "force_update": True
        }).json()
    
    def auto_update_all(self, start_date, end_date, max_currencies=50):
        return requests.post(f"{self.base_url}/historical-prices-auto", json={
            "time_start": start_date,
            "time_end": end_date,
            "interval": "daily",
            "max_currencies": max_currencies
        }).json()
    
    def get_live_updates(self, symbols, fiat="USD"):
        return requests.post(f"{self.base_url}/chart-live-update", json={
            "Symbol": symbols,
            "FiatCurrency": fiat
        }).json()
    
    def get_chart_data(self, symbol, timeframe="1d", points=100):
        return requests.post(f"{self.base_url}/chart-data", json={
            "Symbol": symbol,
            "FiatCurrency": "USD",
            "timeframe": timeframe,
            "points": points,
            "include_indicators": True
        }).json()

# استفاده
api = CoinCeeperAPI()

# به‌روزرسانی دستی
result = api.manual_update(["BTC", "ETH"])

# به‌روزرسانی خودکار همه ارزها
result = api.auto_update_all("2024-08-01T00:00:00Z", "2024-08-31T23:59:59Z")

# دریافت آپدیت زنده
live_data = api.get_live_updates(["BTC", "ETH"])

# دریافت چارت
chart_data = api.get_chart_data("BTC", "1w", 168)
```

### **JavaScript Integration:**
```javascript
class CoinCeeperAPI {
  constructor(baseURL = '/api') {
    this.baseURL = baseURL;
  }
  
  async manualUpdate(symbols, fiats = ['USD']) {
    const response = await fetch(`${this.baseURL}/manual-update`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        Symbol: symbols,
        FiatCurrencies: fiats,
        force_update: true
      })
    });
    return await response.json();
  }
  
  async getLiveUpdates(symbols, fiat = 'USD') {
    const response = await fetch(`${this.baseURL}/chart-live-update`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        Symbol: symbols,
        FiatCurrency: fiat
      })
    });
    return await response.json();
  }
  
  async getChartData(symbol, timeframe = '1d', points = 100) {
    const response = await fetch(`${this.baseURL}/chart-data`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        Symbol: symbol,
        FiatCurrency: 'USD',
        timeframe: timeframe,
        points: points,
        include_indicators: true
      })
    });
    return await response.json();
  }
}

// استفاده
const api = new CoinCeeperAPI();

// آپدیت زنده
api.getLiveUpdates(['BTC', 'ETH']).then(data => {
  if (data.status === 'success') {
    console.log('BTC:', data.data.live_prices.BTC.price_formatted);
    console.log('ETH:', data.data.live_prices.ETH.price_formatted);
  }
});

// چارت اصلی
api.getChartData('BTC', '1d', 24).then(data => {
  if (data.status === 'success') {
    const chartData = data.data.price_data;
    const indicators = data.data.technical_indicators;
    // رسم چارت...
  }
});
```

---

## 🎯 **Best Practices**

### **1. Error Handling:**
```javascript
async function safeAPICall(apiFunction) {
  try {
    const result = await apiFunction();
    if (result.status === 'success') {
      return result.data;
    } else {
      console.error('API Error:', result.error.message);
      return null;
    }
  } catch (error) {
    console.error('Network Error:', error);
    return null;
  }
}
```

### **2. Rate Limit Management:**
```javascript
class RateLimitedAPI {
  constructor() {
    this.requestQueue = [];
    this.processing = false;
  }
  
  async request(apiCall) {
    return new Promise((resolve) => {
      this.requestQueue.push({ apiCall, resolve });
      this.processQueue();
    });
  }
  
  async processQueue() {
    if (this.processing) return;
    this.processing = true;
    
    while (this.requestQueue.length > 0) {
      const { apiCall, resolve } = this.requestQueue.shift();
      const result = await apiCall();
      resolve(result);
      await new Promise(r => setTimeout(r, 1000)); // 1 second delay
    }
    
    this.processing = false;
  }
}
```

**همه API ها آپدیت شده و آماده استفاده هستند! 🚀**
