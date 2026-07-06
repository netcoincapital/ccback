# Blockchains List API

## Endpoint

```
GET https://coinceeper.com/api/blockchains
```

## توضیح

لیست تمام بلاکچین‌های پشتیبانی شده در IronWallet را برمی‌گرداند. این لیست از دیتابیس خوانده می‌شود و شامل شناسه، نام، نماد و کد زنجیر هر بلاکچین است.

نیازی به احراز هویت (Authentication) یا API Key ندارد — عمومی است.

## نمونه پاسخ (JSON)

```json
{
  "success": true,
  "blockchains": [
    {
      "id": 1,
      "name": "Ethereum",
      "symbol": "ETH",
      "chain_code": "ETH"
    },
    {
      "id": 2,
      "name": "Tron",
      "symbol": "TRX",
      "chain_code": "TRX"
    },
    {
      "id": 3,
      "name": "Binance Smart Chain",
      "symbol": "BNB",
      "chain_code": "BNB"
    },
    {
      "id": 4,
      "name": "Bitcoin",
      "symbol": "BTC",
      "chain_code": "BTC"
    },
    {
      "id": 5,
      "name": "Polygon",
      "symbol": "MATIC",
      "chain_code": "MATIC"
    },
    {
      "id": 6,
      "name": "Arbitrum",
      "symbol": "ARB",
      "chain_code": "ARB"
    },
    {
      "id": 11,
      "name": "XRP",
      "symbol": "XRP",
      "chain_code": "XRP"
    },
    {
      "id": 12,
      "name": "Solana",
      "symbol": "SOL",
      "chain_code": "SOL"
    },
    {
      "id": 13,
      "name": "Avalanche",
      "symbol": "AVAX",
      "chain_code": "AVAX"
    },
    {
      "id": 14,
      "name": "Polkadot",
      "symbol": "DOT",
      "chain_code": "DOT"
    }
  ],
  "count": 10
}
```

## ساختار پاسخ

| فیلد | نوع | توضیح |
|---|---|---|
| `success` | boolean | همیشه `true` در صورت موفقیت |
| `count` | integer | تعداد کل بلاکچین‌ها |
| `blockchains` | array | آرایه‌ای از اشیاء بلاکچین |

### ساختار هر بلاکچین

| فیلد | نوع | مثال | توضیح |
|---|---|---|---|
| `id` | integer | `1` | شناسه یکتای بلاکچین در دیتابیس |
| `name` | string | `"Ethereum"` | نام کامل بلاکچین |
| `symbol` | string | `"ETH"` | نماد (همان کوین اصلی) |
| `chain_code` | string | `"ETH"` | کد زنجیر — مقدار استفاده شده در سایر APIها |

## Error Response

در صورت مشکل دیتابیس:

```json
{
  "success": false,
  "message": "Database error: <description>"
}
```

کد HTTP: `500`

## استفاده در فرانت‌اند (Flutter/Dart)

```dart
Future<List<Blockchain>> fetchBlockchains() async {
  final response = await http.get(
    Uri.parse('https://coinceeper.com/api/blockchains'),
  );

  if (response.statusCode == 200) {
    final json = jsonDecode(response.body);
    final List<dynamic> data = json['blockchains'];
    return data.map((b) => Blockchain(
      id: b['id'],
      name: b['name'],
      symbol: b['symbol'],
      chainCode: b['chain_code'],
    )).toList();
  } else {
    throw Exception('Failed to load blockchains');
  }
}

class Blockchain {
  final int id;
  final String name;
  final String symbol;
  final String chainCode;

  Blockchain({
    required this.id,
    required this.name,
    required this.symbol,
    required this.chainCode,
  });
}
```

## استفاده با JavaScript/TypeScript

```typescript
interface Blockchain {
  id: number;
  name: string;
  symbol: string;
  chain_code: string;
}

interface BlockchainsResponse {
  success: boolean;
  blockchains: Blockchain[];
  count: number;
}

async function fetchBlockchains(): Promise<Blockchain[]> {
  const res = await fetch('https://coinceeper.com/api/blockchains');
  const data: BlockchainsResponse = await res.json();
  return data.blockchains;
}
```

## کوئری استعلام (برای دیباگ)

```sql
SELECT BlockchainID, BlockchainName, Symbol, ChainCode
FROM blockchains
ORDER BY BlockchainID;
```
