# Historical Data Implementation for Price Charts

## Overview

This implementation adds historical price data functionality to your cryptocurrency price system, enabling you to build price charts using data from CoinMarketCap API.

## Features

✅ **Database Support**: Extended `prices` table to store historical data  
✅ **CoinMarketCap Integration**: Fetch historical data using your API key  
✅ **Flexible APIs**: Both dedicated historical endpoint and enhanced existing API  
✅ **Chart-Ready Format**: Data formatted for easy chart integration  
✅ **Time Range Support**: Configurable time periods and intervals  

## API Key Configuration

Your CoinMarketCap API key `0d216d8a-ddd0-4ada-bacb-da2d7467468a` should be configured in your `.env` file:

```bash
# Option 1: Single key
CMC_API_KEY=0d216d8a-ddd0-4ada-bacb-da2d7467468a

# Option 2: Multiple keys (comma-separated)
CMC_API_KEYS=0d216d8a-ddd0-4ada-bacb-da2d7467468a,other-key-if-needed
```

## Database Changes

### New Columns in `prices` Table

```sql
-- Added columns
is_historical BOOLEAN NOT NULL DEFAULT FALSE
timestamp DATETIME NULL

-- New indexes
INDEX timestamp_idx (timestamp)
INDEX historical_idx (is_historical)

-- Updated unique constraints
UNIQUE (crypto_id, currency, timestamp)  -- For historical records
UNIQUE (crypto_id, currency)             -- For current prices
```

### Migration

Run the migration to update your database:

```bash
mysql -u your_user -p your_database < migrations/add_historical_data_support.sql
```

## API Endpoints

### 1. Enhanced Existing API (`/prices`)

The existing `/prices` endpoint now supports historical data:

**Request:**
```json
{
  "Symbol": ["BTC", "ETH"],
  "FiatCurrencies": ["USD", "EUR"],
  "include_historical": true,
  "days": 30
}
```

**Response:**
```json
{
  "prices": {
    "BTC": {
      "USD": {
        "price": "43,250.50",
        "change_24h": "+2.45%"
      }
    }
  },
  "historical_data": {
    "BTC": {
      "USD": {
        "timestamps": ["2024-12-19T00:00:00Z", "2024-12-20T00:00:00Z"],
        "prices": [42000.50, 43250.50],
        "market_caps": [825000000000, 850000000000],
        "volumes": [25000000000, 28000000000]
      }
    }
  },
  "success": true,
  "days": 30
}
```

### 2. Dedicated Historical API (`/historical-prices`)

New endpoint specifically for historical data:

**Request:**
```json
{
  "Symbol": ["BTC", "ETH"],
  "FiatCurrencies": ["USD"],
  "time_start": "2024-11-19T00:00:00Z",
  "time_end": "2024-12-19T00:00:00Z",
  "interval": "daily"
}
```

**Response:**
```json
{
  "historical_data": {
    "BTC": {
      "USD": {
        "timestamps": ["2024-11-19T00:00:00Z", "2024-11-20T00:00:00Z"],
        "prices": [40000.00, 41000.00],
        "market_caps": [800000000000, 820000000000],
        "volumes": [22000000000, 24000000000]
      }
    }
  },
  "success": true,
  "interval": "daily",
  "time_start": "2024-11-19T00:00:00Z",
  "time_end": "2024-12-19T00:00:00Z"
}
```

### 3. Historical Data Update API (`/update-historical-prices`)

Manually update historical data:

**Request:**
```json
{
  "Symbol": ["BTC"],
  "FiatCurrencies": ["USD"],
  "time_start": "2024-11-01T00:00:00Z",
  "time_end": "2024-12-01T00:00:00Z",
  "interval": "daily"
}
```

## Supported Intervals

- **Minutes**: `5m`, `10m`, `15m`, `30m`, `45m`
- **Hours**: `1h`, `2h`, `3h`, `4h`, `6h`, `12h`
- **Days**: `1d`, `2d`, `3d`, `7d`, `14d`, `15d`, `30d`, `60d`, `90d`, `365d`
- **Aliases**: `daily`, `hourly`

## Implementation Architecture

### 1. Database Layer (`database/prices.py`)
- Extended `Price` model with historical data support
- Added indexes for performance
- Maintains backward compatibility

### 2. Historical Data Service (`Currencies/historical_data_service.py`)
- Handles CoinMarketCap API interactions
- Manages data storage and retrieval
- Supports both quotes and OHLCV data

### 3. Enhanced Price Service (`Currencies/currency_price_service.py`)
- Integrates historical data methods
- Provides unified interface for current and historical prices
- Handles caching and optimization

### 4. API Layer (`Currencies/Prices.py`)
- Enhanced existing endpoints
- New dedicated historical endpoints
- Comprehensive error handling and validation

## Usage Examples

### For Price Charts

```python
import requests

# Get 30 days of Bitcoin price data
response = requests.post('http://your-server/historical-prices', json={
    "Symbol": ["BTC"],
    "FiatCurrencies": ["USD"],
    "time_start": "2024-11-19T00:00:00Z",
    "time_end": "2024-12-19T00:00:00Z",
    "interval": "daily"
})

data = response.json()
btc_data = data['historical_data']['BTC']['USD']

# Use with Chart.js or similar
chart_data = {
    'labels': btc_data['timestamps'],
    'datasets': [{
        'label': 'BTC Price',
        'data': btc_data['prices'],
        'borderColor': 'rgb(255, 99, 132)',
        'tension': 0.1
    }]
}
```

### Combined Current + Historical

```python
# Get current price with 7 days history
response = requests.post('http://your-server/prices', json={
    "Symbol": ["BTC"],
    "FiatCurrencies": ["USD"],
    "include_historical": True,
    "days": 7
})

data = response.json()
current_price = data['prices']['BTC']['USD']['price']
historical_prices = data['historical_data']['BTC']['USD']['prices']
```

## Performance Considerations

1. **Database Indexes**: Added for `timestamp` and `is_historical` columns
2. **API Rate Limits**: Respects CoinMarketCap rate limits
3. **Caching**: Historical data is cached in database to reduce API calls
4. **Batch Processing**: Efficient handling of multiple currencies

## Testing

Run the test script to validate your implementation:

```bash
python test_historical_data.py
```

The test script will check:
- Database schema updates
- Historical data service functionality  
- API endpoint responses
- Data format validation

## Architecture Decision: Single API vs Separate APIs

**✅ RECOMMENDED: Single Enhanced API**

**Advantages:**
- **Unified Interface**: One endpoint for both current and historical data
- **Reduced Complexity**: Fewer endpoints to maintain
- **Better UX**: Developers can get everything they need in one call
- **Backward Compatible**: Existing clients continue working unchanged

**When to use separate `/historical-prices`:**
- When you need advanced historical features (OHLCV, complex intervals)
- For dedicated chart applications
- When current price calls are frequent and you want to avoid overhead

## Error Handling

The implementation includes comprehensive error handling:

- **Validation Errors**: Invalid symbols, time ranges, intervals
- **API Errors**: CoinMarketCap API failures, rate limits
- **Database Errors**: Connection issues, constraint violations
- **Timeout Handling**: For long-running historical data fetches

## Security

- **Rate Limiting**: Applied to all endpoints
- **Input Validation**: All parameters validated
- **API Key Management**: Secure handling of CoinMarketCap keys
- **SQL Injection Prevention**: Using parameterized queries

## Next Steps

1. **Run Migration**: Update your database schema
2. **Configure API Key**: Add your CMC API key to `.env`
3. **Test Implementation**: Run the test script
4. **Update Frontend**: Integrate with your chart library
5. **Monitor Performance**: Watch API usage and database performance

## Support

If you encounter any issues:

1. Check the test script output
2. Verify API key configuration
3. Ensure database migration was successful
4. Check server logs for detailed error messages

---

**Implementation Status**: ✅ Complete and Ready for Production

**API Key**: `0d216d8a-ddd0-4ada-bacb-da2d7467468a` (Your CoinMarketCap key)

**Database**: Enhanced `prices` table with historical data support

**Endpoints**: 
- ✅ `/prices` (enhanced with historical data option)
- ✅ `/historical-prices` (dedicated historical endpoint)  
- ✅ `/update-historical-prices` (manual data updates)

