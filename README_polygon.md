# Polygon (POL) Transaction Finder

🚀 **Find specific Polygon transactions matching custom criteria**

## 📋 Overview

This script finds Polygon blockchain transactions with the following criteria:
- **Total network fees**: Approximately **$52**
- **Transaction amounts**: Less than **$300** each
- **Date range**: July 17, 2025 to August 17, 2025
- **Wallet types**: "New" wallets + specific exchanges (Binance, XT.com)
- **Token support**: Includes ERC-20 token transfers

## 🎯 Target Criteria

### 💰 Fee Target
- **Total accumulated fees**: $52 USD
- **Individual fee range**: $0.01 - $10.00 per transaction
- **Maximum transactions**: 50

### 💸 Transaction Amount Limit
- Each transaction must be **less than $300 USD**
- Includes both native POL and ERC-20 token transfers

### 🏦 Wallet Requirements

#### "New" Wallets
- **Current balance**: ≤ 222 POL (~$100 at $0.45/POL)
- **Total received**: ≤ 2222 POL (~$1000 at $0.45/POL)

#### Allowed Exchanges
- ✅ **Binance** addresses
- ✅ **XT.com** addresses

#### Blocked Exchanges
- ❌ Coinbase
- ❌ Bitfinex  
- ❌ Kraken

### 📅 Date Range
- **Start**: July 17, 2025
- **End**: August 17, 2025
- Note: Future dates are simulated for demonstration

## 🔧 Installation

1. **Install dependencies:**
```bash
pip install -r requirements_polygon.txt
```

2. **Set up API keys (optional):**
```bash
# Create .env file
echo "POLYGONSCAN_API_KEY=your_polygonscan_api_key_here" > .env
```

## 🚀 Usage

### Basic Usage
```bash
python polygon_transaction_finder.py
```

### API Key Setup
1. Get a free API key from [PolygonScan](https://polygonscan.com/apis)
2. Add it to your `.env` file:
```
POLYGONSCAN_API_KEY=YourApiKeyHere
```

## 📊 Output

### Console Output
```
🚀 Polygon (POL) Transaction Finder
=================================================
🔑 Using PolygonScan API (API key required)
📅 Date range: July 17, 2025 to August 17, 2025
💰 Target total fees: $52
💸 Max transaction amount: $300

🔍 Starting Polygon transaction search...
🎯 Target: Total fees = $52, Transaction amounts < $300
📦 Fetching recent blocks from PolygonScan...
✅ TX 1: Fee: $2.45 | Amount: $156.78 | From: 0x1234... (New Wallet) | To: 0x5678... (New Wallet)
✅ TX 2: Fee: $1.23 | Amount: $45.67 (ERC-20 Token) | From: 0x9abc... (New Wallet) | To: 0xdef0... (Exchange - Binance)

📊 Search completed!
✅ Found: 42 transactions
💰 Total fees: $51.89
```

### JSON Output
Creates `polygon_transactions_YYYYMMDD_HHMMSS.json`:
```json
{
  "metadata": {
    "blockchain": "Polygon (POL)",
    "total_transactions": 42,
    "total_fees_usd": 51.89,
    "target_total_fees": 52,
    "max_transaction_amount": 300,
    "date_range": "2025-07-17 to 2025-08-17",
    "supports_erc20_tokens": true
  },
  "transactions": [
    {
      "hash": "0x1234...",
      "fee_usd": 2.45,
      "sender_address": "0x1234...",
      "receiver_address": "0x5678...",
      "value_usd": 156.78,
      "is_token_transfer": false,
      "transaction_date": "2025-07-25 14:30:45"
    }
  ]
}
```

## 🔍 Features

### 🌟 Core Features
- **Real-time data** from PolygonScan API
- **Smart wallet classification** (new wallets vs exchanges)
- **ERC-20 token support** with automatic detection
- **Fee optimization** to reach target amount
- **Exchange filtering** (allow/block specific exchanges)

### 📈 Transaction Analysis
- Gas usage and price calculation
- USD value conversion using live POL prices
- Token transfer detection (ERC-20)
- Wallet balance and history checking

### 🛡️ Error Handling
- API rate limiting protection
- Network timeout handling
- Retry mechanisms with exponential backoff
- Offline mode for testing

## 🔧 Configuration

### Environment Variables
```bash
# Optional: PolygonScan API key for higher rate limits
POLYGONSCAN_API_KEY=your_api_key_here
```

### Customizable Parameters
```python
# In the script, you can modify:
target_total_fee = 52        # Target total fees in USD
max_transactions = 50        # Maximum number of transactions
max_amount_usd = 300        # Maximum transaction amount
fee_range = (0.01, 10.0)   # Acceptable fee range
```

## 🌐 API Endpoints

### Primary APIs
- **PolygonScan API**: Transaction and block data
- **CoinGecko API**: POL/MATIC price feeds

### Rate Limits
- **PolygonScan**: 5 requests/second (with API key)
- **CoinGecko**: 10-50 requests/minute (free tier)

## 🚨 Important Notes

### ⚠️ Demo Mode
- **Future dates**: July-August 2025 are simulated
- **Real data**: Use current/past dates for actual blockchain data
- **Price simulation**: Uses current POL prices for calculations

### 🔐 Security
- **API keys**: Store in `.env` file, never commit to version control
- **Rate limits**: Automatic delays prevent API blocking
- **Data validation**: All inputs sanitized and validated

### 💡 Tips
- **API key recommended**: For reliable data access
- **Network stability**: Ensure stable internet connection
- **Large datasets**: May take several minutes to process

## 🐛 Troubleshooting

### Common Issues

1. **No transactions found**
   - Criteria might be too strict
   - Try wider date range or higher fee limits

2. **API rate limits**
   - Add delays between requests
   - Get PolygonScan API key for higher limits

3. **Network errors**
   - Check internet connection
   - Verify API endpoints are accessible

### Debug Mode
Enable detailed logging by modifying the script:
```python
# Add at the top of the script
import logging
logging.basicConfig(level=logging.DEBUG)
```

## 📚 Related Files

- `polygon_transaction_finder.py` - Main script
- `requirements_polygon.txt` - Dependencies
- `README_polygon.md` - This documentation

## 🔗 External APIs

- [PolygonScan API](https://polygonscan.com/apis) - Polygon blockchain data
- [CoinGecko API](https://www.coingecko.com/en/api) - Cryptocurrency prices

---

**✨ Happy transaction hunting on Polygon! 🚀**
