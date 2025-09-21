# 🌐 نمونه‌های cURL برای API های جدید

## 💰 **Prices API**

### درخواست قیمت تک ارز:
```bash
curl -X POST http://localhost:5000/api/prices \
  -H "Content-Type: application/json" \
  -d '{
    "Symbol": ["BTC"],
    "FiatCurrencies": ["USD"]
  }'
```

### درخواست قیمت چند ارز:
```bash
curl -X POST http://localhost:5000/api/prices \
  -H "Content-Type: application/json" \
  -d '{
    "Symbol": ["BTC", "ETH", "ADA", "DOGE"],
    "FiatCurrencies": ["USD", "EUR", "IRR"]
  }'
```

### پاسخ نمونه:
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

---

## 📈 **Chart API**

### درخواست چارت روزانه:
```bash
curl -X POST http://localhost:5000/api/chart-data \
  -H "Content-Type: application/json" \
  -d '{
    "Symbol": "BTC",
    "FiatCurrency": "USD", 
    "timeframe": "1d",
    "points": 24
  }'
```

### درخواست چارت هفتگی:
```bash
curl -X POST http://localhost:5000/api/chart-data \
  -H "Content-Type: application/json" \
  -d '{
    "Symbol": "ETH",
    "FiatCurrency": "USD",
    "timeframe": "1w", 
    "points": 168
  }'
```

### درخواست چارت ماهانه:
```bash
curl -X POST http://localhost:5000/api/chart-data \
  -H "Content-Type: application/json" \
  -d '{
    "Symbol": "ADA",
    "FiatCurrency": "EUR",
    "timeframe": "1m",
    "points": 720
  }'
```

### پاسخ نمونه:
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
      "trend": "up",
      "last_updated": "2025-09-01T10:30:45Z"
    }
  },
  "metadata": {
    "response_time_ms": 89,
    "data_quality": "complete"
  }
}
```

---

## 🔧 **تست سریع با cURL**

### تست اتصال:
```bash
# تست Prices API
curl -X POST http://localhost:5000/api/prices \
  -H "Content-Type: application/json" \
  -d '{"Symbol":["BTC"],"FiatCurrencies":["USD"]}' \
  | jq '.'

# تست Chart API  
curl -X POST http://localhost:5000/api/chart-data \
  -H "Content-Type: application/json" \
  -d '{"Symbol":"BTC","FiatCurrency":"USD","timeframe":"1h","points":12}' \
  | jq '.'
```

### تست خطاها:
```bash
# نماد نامعتبر
curl -X POST http://localhost:5000/api/prices \
  -H "Content-Type: application/json" \
  -d '{"Symbol":["INVALID"],"FiatCurrencies":["USD"]}'

# timeframe نامعتبر
curl -X POST http://localhost:5000/api/chart-data \
  -H "Content-Type: application/json" \
  -d '{"Symbol":"BTC","timeframe":"invalid"}'
```

---

## 📱 **استفاده در JavaScript/Frontend**

### Fetch API:
```javascript
// دریافت قیمت‌ها
async function getPrices(symbols, fiats) {
  const response = await fetch('/api/prices', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      Symbol: symbols,
      FiatCurrencies: fiats
    })
  });
  
  return await response.json();
}

// دریافت چارت
async function getChartData(symbol, fiat, timeframe, points) {
  const response = await fetch('/api/chart-data', {
    method: 'POST', 
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      Symbol: symbol,
      FiatCurrency: fiat,
      timeframe: timeframe,
      points: points
    })
  });
  
  return await response.json();
}

// مثال استفاده
getPrices(['BTC', 'ETH'], ['USD', 'EUR'])
  .then(data => {
    if (data.status === 'success') {
      console.log('BTC Price:', data.data.BTC.USD.formatted_price);
      console.log('ETH Price:', data.data.ETH.USD.formatted_price);
    }
  });

getChartData('BTC', 'USD', '1d', 24)
  .then(data => {
    if (data.status === 'success') {
      const chartData = data.data.price_data;
      // رسم چارت با chartData
    }
  });
```

---

## 🐍 **استفاده در Python**

```python
import requests
import json

# تابع دریافت قیمت
def get_prices(symbols, fiats=['USD']):
    response = requests.post(
        'http://localhost:5000/api/prices',
        json={
            'Symbol': symbols,
            'FiatCurrencies': fiats
        }
    )
    return response.json()

# تابع دریافت چارت
def get_chart_data(symbol, fiat='USD', timeframe='1d', points=100):
    response = requests.post(
        'http://localhost:5000/api/chart-data',
        json={
            'Symbol': symbol,
            'FiatCurrency': fiat,
            'timeframe': timeframe,
            'points': points
        }
    )
    return response.json()

# مثال استفاده
prices = get_prices(['BTC', 'ETH'], ['USD', 'EUR'])
chart = get_chart_data('BTC', 'USD', '1w', 168)

print(f"BTC Price: {prices['data']['BTC']['USD']['formatted_price']}")
print(f"Chart Points: {len(chart['data']['price_data'])}")
```

---

## ⚠️ **نکات مهم**

### Rate Limits:
- **Prices API**: 100 درخواست در دقیقه
- **Chart API**: 200 درخواست در دقیقه

### Timeframes معتبر:
- `1h`: 1 ساعت (تا 60 نقطه)
- `1d`: 1 روز (تا 24 نقطه)  
- `1w`: 1 هفته (تا 168 نقطه)
- `1m`: 1 ماه (تا 720 نقطه)
- `3m`: 3 ماه (تا 2160 نقطه)
- `6m`: 6 ماه (تا 4320 نقطه)
- `1y`: 1 سال (تا 8760 نقطه)

### Error Handling:
همیشه `status` فیلد را بررسی کنید:
- `"success"`: درخواست موفق
- `"error"`: خطا رخ داده
