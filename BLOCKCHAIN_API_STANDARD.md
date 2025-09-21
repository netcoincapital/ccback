# 📊 ساختار استاندارد API برای تمام بلاکچین‌ها

## 🔗 **API Endpoint:**
```
POST /api/send/prepare
```

---

## 📤 **Request Format (یکسان برای همه بلاکچین‌ها):**

### **ساختار اصلی:**
```json
{
  "UserId": "63ff3616-abb3-4d03-b8d6-51a3c5a6dc08",
  "blockchain": "BlockchainName",
  "sender_address": "0x...",
  "recipient_address": "0x...",
  "amount": "0.002",
  "smart_contract_address": ""
}
```

### **فیلدهای Request:**

| فیلد | نوع | الزامی | توضیح |
|------|-----|--------|-------|
| `UserId` | string | ✅ | شناسه کاربر |
| `blockchain` | string | ✅ | نام بلاکچین |
| `sender_address` | string | ✅ | آدرس فرستنده |
| `recipient_address` | string | ✅ | آدرس گیرنده |
| `amount` | string | ✅ | مقدار (واحد اصلی) |
| `smart_contract_address` | string | ❌ | آدرس قرارداد (برای توکن‌ها) |

### **فرمت‌های مختلف Amount:**

#### **1. واحد اصلی (توصیه شده):**
```json
{
  "amount": "0.002"
}
```

#### **2. واحد کوچک (پیشرفته):**
```json
{
  "amount_wei": "2000000000000000"    // برای Ethereum
  "amount_satoshi": "200000"          // برای Bitcoin
  "amount_lamports": "2000000"        // برای Solana
}
```

---

## 📥 **Response Format (استاندارد برای همه بلاکچین‌ها):**

### **ساختار موفق:**
```json
{
  "UserID": "63ff3616-abb3-4d03-b8d6-51a3c5a6dc08",
  "userId": "63ff3616-abb3-4d03-b8d6-51a3c5a6dc08",
  "transaction_id": "86512d80-8ced-4a48-a841-f5abf30a6d8e",
  "success": true,
  "message": "Transaction prepared successfully",
  "expires_at": "2025-09-05T23:26:23.015923",
  "details": {
    "amount": "0.001992837130202",
    "original_amount": "0.002",
    "auto_adjusted": true,
    "blockchain": "ethereum",
    "estimated_fee": "0.000007162869798",
    "sender": "0x4A56CEB9C75FA018C1e2F16474BB1fBD639a6956",
    "recipient": "0x8d697D386c175dC7ac25DF67f82B3BFbc8EC5bE9",
    "sender_balance_before": "0.002",
    "sender_balance_after": "0E-15",
    "explorer_url": "https://etherscan.io/tx/86512d80-..."
  }
}
```

### **ساختار خطا:**
```json
{
  "success": false,
  "message": "Error message here",
  "error_type": "validation_error",
  "details": {
    "field": "sender_address",
    "reason": "Invalid address format"
  }
}
```

---

## 🔗 **مقایسه بلاکچین‌ها:**

### **Ethereum:**
```json
// Request
{
  "blockchain": "Ethereum",
  "amount": "0.002"  // ETH
}

// Response details
{
  "blockchain": "ethereum",
  "estimated_fee": "0.000007162869798",  // ETH
  "explorer_url": "https://etherscan.io/tx/..."
}
```

### **Bitcoin:**
```json
// Request
{
  "blockchain": "Bitcoin",
  "amount": "0.001"  // BTC
}

// Response details
{
  "blockchain": "bitcoin",
  "estimated_fee": "0.00002",  // BTC
  "explorer_url": "https://blockchain.com/btc/tx/..."
}
```

### **Polygon:**
```json
// Request
{
  "blockchain": "Polygon",
  "amount": "1.5"  // MATIC
}

// Response details
{
  "blockchain": "polygon",
  "estimated_fee": "0.001",  // MATIC
  "explorer_url": "https://polygonscan.com/tx/..."
}
```

### **BSC:**
```json
// Request
{
  "blockchain": "BSC",
  "amount": "0.01"  // BNB
}

// Response details
{
  "blockchain": "bsc",
  "estimated_fee": "0.0005",  // BNB
  "explorer_url": "https://bscscan.com/tx/..."
}
```

### **Solana:**
```json
// Request
{
  "blockchain": "Solana",
  "amount": "0.1"  // SOL
}

// Response details
{
  "blockchain": "solana",
  "estimated_fee": "0.000005",  // SOL
  "explorer_url": "https://solscan.io/tx/..."
}
```

### **TRON:**
```json
// Request
{
  "blockchain": "Tron",
  "amount": "100"  // TRX
}

// Response details
{
  "blockchain": "tron",
  "estimated_fee": "1.1",  // TRX
  "explorer_url": "https://tronscan.org/#/transaction/..."
}
```

---

## 🔧 **تفاوت‌های کلیدی:**

### **1. واحدهای مختلف:**
- **Ethereum:** ETH (18 decimal)
- **Bitcoin:** BTC (8 decimal)
- **Polygon:** MATIC (18 decimal)
- **BSC:** BNB (18 decimal)
- **Solana:** SOL (9 decimal)
- **TRON:** TRX (6 decimal)

### **2. فیلدهای اختصاصی:**

#### **EVM Chains (ETH, Polygon, BSC):**
```json
{
  "smart_contract_address": "0x...",  // برای توکن‌ها
  "gas_limit": 21000,
  "gas_price_gwei": 20
}
```

#### **UTXO Chains (Bitcoin, Litecoin):**
```json
{
  "input_count": 2,
  "output_count": 2,
  "fee_rate": "10 sat/byte"
}
```

#### **Solana:**
```json
{
  "compute_units": 200000,
  "priority_fee": "0.000001"
}
```

### **3. Explorer URLs:**
- **Ethereum:** `https://etherscan.io/tx/{tx_hash}`
- **Bitcoin:** `https://blockchain.com/btc/tx/{tx_hash}`
- **Polygon:** `https://polygonscan.com/tx/{tx_hash}`
- **BSC:** `https://bscscan.com/tx/{tx_hash}`
- **Solana:** `https://solscan.io/tx/{tx_hash}`
- **TRON:** `https://tronscan.org/#/transaction/{tx_hash}`

---

## 🎯 **پاسخ به سوال شما:**

### ✅ **Request Format:** 
**بله، کاملاً یکسان است برای همه بلاکچین‌ها:**
```json
{
  "UserId": "...",
  "blockchain": "BlockchainName",
  "sender_address": "...",
  "recipient_address": "...",
  "amount": "...",
  "smart_contract_address": ""
}
```

### ✅ **Response Structure:**
**ساختار کلی یکسان است، ولی فیلدهای `details` کمی متفاوت:**

#### **فیلدهای مشترک:**
- `success`, `message`, `transaction_id`, `expires_at`
- `amount`, `estimated_fee`, `sender`, `recipient`
- `sender_balance_before`, `sender_balance_after`

#### **فیلدهای اختصاصی:**
- **Ethereum:** `auto_adjusted`, EIP-1559 details
- **Bitcoin:** UTXO details, fee_rate
- **Solana:** Program details, compute_units
- **TRON:** Energy/Bandwidth costs

### 🔄 **نکات مهم:**

1. **Request همیشه یکسان** - فقط `blockchain` و `amount` تغییر می‌کند
2. **Response structure مشابه** - فقط `details` متفاوت
3. **Explorer URLs متفاوت** - هر بلاکچین سایت خودش
4. **واحدهای amount متفاوت** - ETH, BTC, MATIC, SOL, etc.

**پس بله، ساختار کلی استاندارد است! 🚀**
