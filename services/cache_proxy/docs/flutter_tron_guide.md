# Tron Broadcast & Balance — Flutter Integration Guide

## معماری (Non-Custodial)

```
┌─────────────────────────────────────────────────────────┐
│                    Flutter (Client)                       │
│                                                           │
│  1️⃣  کاربر آدرس مبدأ، مقصد و مقدار را وارد می‌کند          │
│  2️⃣  تراکنش با tronweb (dart) محلی امضا می‌شود             │
│  3️⃣  signedTx hex به بک‌اند فرستاده می‌شود                 │
│  4️⃣  بک‌اند به TronGrid فوروارد می‌کند + txId برمی‌گرداند │
└──────────────────────┬──────────────────────────────────┘
                       │ POST /api/v2/broadcast
                       ▼
┌─────────────────────────────────────────────────────────┐
│               Backend (Proxy)                            │
│                                                           │
│  - signedTx را ذخیره/لاگ نمی‌کند                          │
│  - 12 کلید TronGrid (round-robin, circuit breaker)       │
│  - فقط به /wallet/broadcasthex فوروارد می‌کند             │
└─────────────────────────────────────────────────────────┘
```

---

## 1. دریافت Balance (TRX Native)

**Endpoint:** `POST /api/v2/balance/native`

### درخواست (Flutter)

```dart
import 'dart:convert';
import 'package:http/http.dart' as http;

Future<String?> getTronBalance(String address) async {
  final response = await http.post(
    Uri.parse('$BASE_URL/api/v2/balance/native'),
    headers: {'Content-Type': 'application/json'},
    body: jsonEncode({
      'chain': 'tron',
      'address': address,
    }),
  );

  if (response.statusCode == 200) {
    final data = jsonDecode(response.body);
    if (data['success'] == true) {
      // balance به واحد SUN (1 TRX = 1_000_000 SUN)
      return data['balance']; // مثال: "15000000" = 15 TRX
    }
  }
  return null;
}
```

### پاسخ موفق

```json
{
  "success": true,
  "chain": "tron",
  "address": "TXYZ...",
  "balance": "15000000",
  "source": "proxy",
  "timestamp": "2026-06-29T..."
}
```

> **نکته:** balance به واحد SUN برمی‌گردد. برای تبدیل به TRX: `balance / 1_000_000`

---

## 2. دریافت Balance (TRC20 Token)

**Endpoint:** `POST /api/v2/balance/token`

### درخواست (Flutter)

```dart
Future<String?> getTrc20Balance(String address, String contractAddress) async {
  final response = await http.post(
    Uri.parse('$BASE_URL/api/v2/balance/token'),
    headers: {'Content-Type': 'application/json'},
    body: jsonEncode({
      'chain': 'tron',
      'address': address,
      'contract_address': contractAddress,
    }),
  );

  if (response.statusCode == 200) {
    final data = jsonDecode(response.body);
    if (data['success'] == true) {
      // balance به واحد خام (raw, بدون اعمال decimals)
      return data['balance']; // مثال: "5000000" = 5 USDT (6 decimals)
    }
  }
  return null;
}
```

---

## 3. Broadcast تراکنش امضا شده

**Endpoint:** `POST /api/v2/broadcast`

### گردش کار کامل (Flutter)

```dart
import 'dart:convert';
import 'package:http/http.dart' as http;
// بسته tronweb برای dart: https://pub.dev/packages/tronweb
import 'package:tronweb/tronweb.dart';

class TronBroadcastService {
  static const String baseUrl = 'YOUR_BACKEND_URL';

  /// 1️⃣ ساخت و امضای تراکنش در Flutter (کلید خصوصی هرگز به بک‌اند نمی‌رود)
  Future<String> signTransaction({
    required String privateKey,
    required String from,
    required String to,
    required double amountTrx,
  }) async {
    final tronWeb = TronWeb(
      fullNode: 'https://api.trongrid.io',
      solidityNode: 'https://api.trongrid.io',
      eventServer: 'https://api.trongrid.io',
      privateKey: privateKey,
    );

    // ساخت تراکنش
    final transaction = await tronWeb.transactionBuilder.sendTrx(
      to,
      (amountTrx * 1_000_000).toInt(), // TRX → SUN
      from,
    );

    // امضای تراکنش (در کلاینت)
    final signedTx = await tronWeb.trx.sign(transaction, privateKey);

    // سریالایز به hex
    final signedHex = jsonEncode(signedTx);
    return signedHex;
  }

  /// 2️⃣ ارسال signedTx به بک‌اند برای broadcast
  Future<String?> broadcastToBackend(String signedHex) async {
    final response = await http.post(
      Uri.parse('$baseUrl/api/v2/broadcast'),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({
        'chain': 'tron',
        'signed_tx': signedHex,
      }),
    );

    if (response.statusCode == 200) {
      final data = jsonDecode(response.body);
      if (data['success'] == true) {
        return data['tx_hash']; // txId ترون
      }
    }
    return null;
  }

  /// یک‌جا: امضا + broadcast
  Future<String?> signAndBroadcast({
    required String privateKey,
    required String from,
    required String to,
    required double amountTrx,
  }) async {
    final signedHex = await signTransaction(
      privateKey: privateKey,
      from: from,
      to: to,
      amountTrx: amountTrx,
    );

    return await broadcastToBackend(signedHex);
  }
}
```

### پاسخ موفق

```json
{
  "success": true,
  "chain": "tron",
  "tx_hash": "8a1f9a3d5b7c2e4f6a8b0c1d2e3f4a5b6c7d8e9f",
  "provider": "trongrid_broadcasthex",
  "note": "Non-custodial: signedTx was not stored or logged",
  "source": "proxy",
  "timestamp": "2026-06-29T..."
}
```

### پاسخ خطا

```json
{
  "success": false,
  "error": "Broadcast failed",
  "timestamp": "2026-06-29T..."
}
```

---

## 4. Token Metadata

**Endpoint:** `GET /api/v2/token-metadata?chain=tron&contract_address=TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t`

```dart
Future<Map<String, dynamic>?> getTokenMetadata(String contractAddress) async {
  final response = await http.get(
    Uri.parse('$BASE_URL/api/v2/token-metadata')
        .replace(queryParameters: {
      'chain': 'tron',
      'contract_address': contractAddress,
    }),
  );

  if (response.statusCode == 200) {
    final data = jsonDecode(response.body);
    if (data['success'] == true) {
      return data['token'];
      // {
      //   "symbol": "USDT",
      //   "name": "Tether USD",
      //   "decimals": 6,
      //   "contract_address": "TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t"
      // }
    }
  }
  return null;
}
```

---

## 5. Transaction History

**Endpoint:** `POST /api/v2/explorer/tx-history`

```dart
Future<List<dynamic>?> getTransactionHistory(String address) async {
  final response = await http.post(
    Uri.parse('$BASE_URL/api/v2/explorer/tx-history'),
    headers: {'Content-Type': 'application/json'},
    body: jsonEncode({
      'chain': 'tron',
      'address': address,
      'page': 1,
      'limit': 25,
    }),
  );

  if (response.statusCode == 200) {
    final data = jsonDecode(response.body);
    if (data['success'] == true) {
      return data['transactions'];
    }
  }
  return null;
}
```

---

## نکات امنیتی مهم

| مورد | توضیح |
|------|--------|
| **کلید خصوصی** | هرگز (`privateKey`) را به بک‌اند نفرستید. امضا همیشه در Flutter انجام شود |
| **signedTx** | بک‌اند signedTx را ذخیره/لاگ نمی‌کند (طبق کد) |
| **API Keyها** | ۱۲ کلید TronGrid در بک‌اند پنهان هستند — کاربر از وجود آن‌ها بی‌خبر است |
| **Rate Limit** | broadcast محدودیت ۵ req/min دارد (برای جلوگیری از spam) |
| **DoS Protection** | اگر کلیدی rate limit بخورد، خودکار ۳۰ ثانیه سرد می‌شود و کلید بعدی جایگزین می‌شود |

## خلاصه APIهای Tron در v2

| Endpoint | Method | توضیح |
|----------|--------|--------|
| `/api/v2/balance/native` | POST | دریافت TRX balance (به SUN) |
| `/api/v2/balance/token` | POST | دریافت TRC20 balance (raw, بدون decimals) |
| `/api/v2/broadcast` | POST | **ارسال تراکنش امضا شده (جدید)** |
| `/api/v2/explorer/tx-history` | POST | تاریخچه تراکنش‌های ترون |
| `/api/v2/explorer/token-tx` | POST | تاریخچه TRC20 transfer |
| `/api/v2/token-metadata` | GET | اطلاعات توکن (symbol, decimals) |
