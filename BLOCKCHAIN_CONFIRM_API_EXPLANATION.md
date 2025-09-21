# 🔐 توضیح کامل API Confirm و مدیریت Private Key

## 🔍 **تشخیص مشکل شما:**

شما درست می‌گویید! سیستم **دو حالت** پشتیبانی می‌کند:

### **حالت 1: Private Key در Request (فعلی)**
```json
{
  "transaction_id": "7876481c-6abe-4a88-a822-cfdb1cf40f35",
  "private_key": "0x1234567890abcdef..."
}
```

### **حالت 2: Private Key از دیتابیس (مورد نظر شما)**
```json
{
  "UserId": "63ff3616-abb3-4d03-b8d6-51a3c5a6dc08",
  "transaction_id": "7876481c-6abe-4a88-a822-cfdb1cf40f35"
}
```

---

## 🔧 **نحوه کار سیستم:**

### **📋 در `api/blockchain_api.py` (خط 273-308):**

```python
# اگر private_key ارسال نشد
if not private_key:
    # دریافت آدرس فرستنده از transaction data
    sender_address = tx_data.get('details', {}).get('sender')
    
    # دریافت private key از دیتابیس
    private_key = get_private_key_from_db(session, sender_address, blockchain_name)
```

### **📋 در `Send/Send.py` (خط 298):**

```python
def get_private_key_from_db(session, address, blockchain_name):
    # 1. پیدا کردن blockchain_id
    blockchain = session.query(Blockchains).filter(...)
    
    # 2. پیدا کردن address record
    address_record = session.query(Address).filter(
        Address.PublicAddress == address,
        Address.BlockchainID == blockchain.BlockchainID
    ).first()
    
    # 3. رمزگشایی private key
    private_key = decrypt_private_key_aes(address_record.PrivateKey)
    
    return private_key
```

---

## 🎯 **ساختار صحیح Request برای API Confirm:**

### **✅ حالت 1: بدون Private Key (توصیه شده)**
```json
{
  "UserId": "63ff3616-abb3-4d03-b8d6-51a3c5a6dc08",
  "transaction_id": "7876481c-6abe-4a88-a822-cfdb1cf40f35"
}
```

### **✅ حالت 2: با Private Key (برای تست)**
```json
{
  "transaction_id": "7876481c-6abe-4a88-a822-cfdb1cf40f35",
  "private_key": "0x1234567890abcdef..."
}
```

---

## 🔄 **جریان کار کامل:**

### **مرحله 1: Prepare**
```bash
POST /api/send/prepare
{
  "UserId": "63ff3616-abb3-4d03-b8d6-51a3c5a6dc08",
  "blockchain": "Ethereum",
  "sender_address": "0x4A56CEB9C75FA018C1e2F16474BB1fBD639a6956",
  "recipient_address": "0x8d697D386c175dC7ac25DF67f82B3BFbc8EC5bE9",
  "amount": "0.002"
}

# Response:
{
  "success": true,
  "transaction_id": "7876481c-6abe-4a88-a822-cfdb1cf40f35",
  "details": {...}
}
```

### **مرحله 2: Confirm (بدون Private Key)**
```bash
POST /api/send/confirm
{
  "UserId": "63ff3616-abb3-4d03-b8d6-51a3c5a6dc08",
  "transaction_id": "7876481c-6abe-4a88-a822-cfdb1cf40f35"
}

# سرور خودکار:
# 1. از transaction_id، sender_address را می‌یابد
# 2. از دیتابیس private_key را دریافت می‌کند
# 3. تراکنش را امضا و ارسال می‌کند

# Response:
{
  "success": true,
  "tx_hash": "0xdbfad754d28a5774d04f4eab4631875cfdcd60a84ebecca0e443f0d87291169c",
  "status": "sent"
}
```

---

## 📊 **مقایسه TRON و Polygon:**

### **TRON Service:**
```python
# در send_transaction:
if not private_key:
    # دریافت از دیتابیس
    private_key = get_private_key_from_db(session, sender_address, 'tron')
```

### **Polygon Service:**
```python
# در send_transaction:
if not private_key:
    # دریافت از دیتابیس
    private_key = get_private_key_from_db(session, sender_address, 'polygon')
```

### **همه بلاکچین‌ها:**
- ✅ پشتیبانی از **دو حالت**: با/بدون private key
- ✅ **Auto-retrieval** از دیتابیس
- ✅ **رمزگشایی خودکار** با AES
- ✅ **امنیت**: private key هرگز لاگ نمی‌شود

---

## 🔧 **API Endpoints برای هر بلاکچین:**

### **Ethereum:**
```bash
POST /api/ethereum/prepare
POST /api/ethereum/confirm
```

### **TRON:**
```bash
POST /api/tron/prepare
POST /api/tron/confirm
```

### **Polygon:**
```bash
POST /api/polygon/prepare
POST /api/polygon/confirm
```

### **یا Generic:**
```bash
POST /api/send/prepare
POST /api/send/confirm
```

---

## 🎯 **پاسخ به سوال شما:**

### ✅ **Request صحیح برای Confirm:**
```json
{
  "UserId": "63ff3616-abb3-4d03-b8d6-51a3c5a6dc08",
  "transaction_id": "7876481c-6abe-4a88-a822-cfdb1cf40f35"
}
```

### 🔄 **چه اتفاقی می‌افتد:**
1. **سرور transaction_id را می‌گیرد**
2. **sender_address را از transaction data استخراج می‌کند**
3. **private_key را از دیتابیس دریافت می‌کند**
4. **تراکنش را امضا و ارسال می‌کند**
5. **tx_hash را برمی‌گرداند**

### 🛡️ **امنیت:**
- ✅ Private key هرگز در request ارسال نمی‌شود
- ✅ Private key رمزگذاری شده در دیتابیس نگهداری می‌شود  
- ✅ فقط سرور دسترسی به private key دارد
- ✅ Private key هرگز لاگ نمی‌شود

**پس شما فقط `UserId` و `transaction_id` ارسال کنید! 🚀**
