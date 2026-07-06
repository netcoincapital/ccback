# راهنمای پیاده‌سازی Price Alert در فرانت‌اند

## معرفی

این سند راهنمای کامل پیاده‌سازی قابلیت **هشدار قیمت (Price Alert)** در اپلیکیشن فرانت‌اند (موبایل/وب) است.

## معماری کلی

```
فرانت‌اند                          بک‌اند
─────────                          ──────
  │                                    │
  │  1. ثبت FCM Device Token          │
  │  ───────────────────────────────►  │  POST /api/notifications/register-device
  │                                    │
  │  2. دریافت لیست ارزها              │
  │  ───────────────────────────────►  │  GET /api/all-currencies
  │                                    │
  │  3. دریافت قیمت فعلی               │
  │  ───────────────────────────────►  │  GET /api/prices?ids=1,2,3&fiat=USD
  │                                    │
  │  4. ایجاد هشدار قیمت               │
  │  ───────────────────────────────►  │  POST /api/notifications/price-alert
  │                                    │
  │  5. دریافت لیست هشدارها            │
  │  ───────────────────────────────►  │  GET /api/notifications/price-alerts/{UserID}
  │                                    │
  │  6. حذف هشدار                      │
  │  ───────────────────────────────►  │  DELETE /api/notifications/price-alert
  │                                    │
  │                                    │
  │  ┌───── بک‌اند (هر ۱۰ دقیقه) ─────┐
  │  │  7. خواندن همه هشدارها از DB   │
  │  │  8. گرفتن قیمت‌های فعلی        │
  │  │  9. مقایسه با target price      │
  │  │  10. ارسال FCM Push به کاربر   │
  │  │  11. حذف هشدار فعال شده        │
  │  └─────────────────────────────────┘
  │                                    │
  │  12. دریافت PUSH notification     │
  │  ◄───────────────────────────────  │  FCM (Firebase Cloud Messaging)
  │                                    │
```

---

## مرحله ۱: پیش‌نیاز — ثبت Device Token

قبل از هر چیزی، اپلیکیشن باید توکن FCM دستگاه را در بک‌اند ثبت کند. این کار را **در زمان لاگین و هر بار که اپ باز می‌شود** انجام دهید.

### اندپوینت

```
POST /api/notifications/register-device
Content-Type: application/json
```

### بدنه درخواست

```json
{
    "UserID": "d7fd960c-0b3b-4f0c-8963-baa6b365953d",
    "WalletID": "550e8400-e29b-41d4-a716-446655440000",
    "DeviceToken": "fBHZPFJLREyXNK2pNwQlV7:APA91bHgT4BDh5xYP3vd4fg2z...",
    "DeviceName": "iPhone 15 Pro",
    "DeviceType": "ios"
}
```

### نکات مهم

- **DeviceToken**: توکن FCM که از Firebase Messaging دریافت می‌کنید. این توکن ممکن است توسط Firebase تغییر کند، بنابراین حتماً در هر start-up اپلیکیشن آن را ثبت کنید.
- **DeviceType**: یکی از `android`، `ios`، یا `web`
- **WalletID**: شناسه کیف پول اصلی کاربر
- **UserID**: شناسه کاربر در سیستم

### نمونه کد Flutter

```dart
import 'package:firebase_messaging/firebase_messaging.dart';

Future<void> registerDeviceToken(String userId, String walletId) async {
  final messaging = FirebaseMessaging.instance;
  final token = await messaging.getToken();
  
  if (token == null) return;
  
  final response = await http.post(
    Uri.parse('https://coinceeper.com/api/notifications/register-device'),
    headers: {'Content-Type': 'application/json'},
    body: jsonEncode({
      'UserID': userId,
      'WalletID': walletId,
      'DeviceToken': token,
      'DeviceName': await _getDeviceName(),
      'DeviceType': Platform.isAndroid ? 'android' : 'ios',
    }),
  );
  
  if (response.statusCode == 200) {
    print('Device registered successfully');
  }
}
```

---

## مرحله ۲: دریافت لیست ارزها و قیمت فعلی

برای اینکه کاربر بتواند هشدار تنظیم کند، باید لیست ارزها و قیمت فعلی را ببیند.

### دریافت لیست ارزها

```
GET /api/all-currencies
```

این اندپوینت لیست همه ارزهای پشتیبانی شده را برمی‌گرداند.

### دریافت قیمت‌ها

```
GET /api/prices
```

می‌توانید از این اندپوینت قیمت فعلی هر ارز را دریافت کنید تا به کاربر نشان دهید.

---

## مرحله ۳: ایجاد هشدار قیمت (Create Alert)

### اندپوینت

```
POST /api/notifications/price-alert
Content-Type: application/json
```

### بدنه درخواست

```json
{
    "UserID": "d7fd960c-0b3b-4f0c-8963-baa6b365953d",
    "Symbol": "BTC",
    "TargetPrice": 75000,
    "AlertType": "above"
}
```

| فیلد | نوع | توضیحات |
|------|------|------|
| `UserID` | string | شناسه کاربر |
| `Symbol` | string | نماد ارز (مثلاً BTC, ETH, SOL) — **حروف بزرگ** |
| `TargetPrice` | number | قیمت هدف (مثلاً 75000) |
| `AlertType` | string | `"above"` = بالاتر از target / `"below"` = پایین‌تر از target |

### پاسخ موفق

```json
{
    "success": true,
    "message": "Price alert set: BTC above $75,000.00"
}
```

### نمونه کد Flutter

```dart
Future<bool> createPriceAlert({
  required String userId,
  required String symbol,
  required double targetPrice,
  required String alertType,
}) async {
  final response = await http.post(
    Uri.parse('https://coinceeper.com/api/notifications/price-alert'),
    headers: {'Content-Type': 'application/json'},
    body: jsonEncode({
      'UserID': userId,
      'Symbol': symbol.toUpperCase(),
      'TargetPrice': targetPrice,
      'AlertType': alertType,
    }),
  );
  
  final body = jsonDecode(response.body);
  return body['success'] == true;
}
```

---

## مرحله ۴: دریافت لیست هشدارهای کاربر (Get Alerts)

### اندپوینت

```
GET /api/notifications/price-alerts/{UserID}
```

### پاسخ موفق

```json
{
    "success": true,
    "alerts": [
        {
            "symbol": "BTC",
            "target_price": 75000.0,
            "alert_type": "above"
        },
        {
            "symbol": "ETH",
            "target_price": 3000.0,
            "alert_type": "below"
        }
    ]
}
```

### نمونه کد Flutter

```dart
Future<List<PriceAlert>> getPriceAlerts(String userId) async {
  final response = await http.get(
    Uri.parse('https://coinceeper.com/api/notifications/price-alerts/$userId'),
  );
  
  if (response.statusCode == 200) {
    final body = jsonDecode(response.body);
    if (body['success'] == true && body['alerts'] != null) {
      return (body['alerts'] as List).map((alert) => PriceAlert(
        symbol: alert['symbol'],
        targetPrice: alert['target_price'],
        alertType: alert['alert_type'],
      )).toList();
    }
  }
  return [];
}

class PriceAlert {
  final String symbol;
  final double targetPrice;
  final String alertType;
  
  PriceAlert({
    required this.symbol,
    required this.targetPrice,
    required this.alertType,
  });
}
```

---

## مرحله ۵: حذف هشدار (Delete Alert)

### اندپوینت

```
DELETE /api/notifications/price-alert
Content-Type: application/json
```

### بدنه درخواست

```json
{
    "UserID": "d7fd960c-0b3b-4f0c-8963-baa6b365953d",
    "Symbol": "BTC",
    "AlertType": "above"
}
```

### پاسخ موفق

```json
{
    "success": true,
    "message": "Alert for BTC removed"
}
```

### نمونه کد Flutter

```dart
Future<bool> deletePriceAlert({
  required String userId,
  required String symbol,
  required String alertType,
}) async {
  final response = await http.delete(
    Uri.parse('https://coinceeper.com/api/notifications/price-alert'),
    headers: {'Content-Type': 'application/json'},
    body: jsonEncode({
      'UserID': userId,
      'Symbol': symbol.toUpperCase(),
      'AlertType': alertType,
    }),
  );
  
  final body = jsonDecode(response.body);
  return body['success'] == true;
}
```

---

## مرحله ۶: دریافت و پردازش PUSH Notification

وقتی قیمت به مقدار هدف برسد، بک‌اند از طریق **Firebase Cloud Messaging (FCM)** یک نوتیفیکیشن پوش برای دستگاه کاربر می‌فرستد.

### Payload نوتیفیکیشن

```json
{
    "notification": {
        "title": "📈 BTC Hit Your Target!",
        "body": "BTC is now $75,200.00 (target: $75,000.00)"
    },
    "data": {
        "type": "price_alert",
        "symbol": "BTC",
        "current_price": "75200.00",
        "target_price": "75000.00",
        "alert_type": "above"
    }
}
```

### هندل کردن در Flutter

```dart
import 'package:firebase_messaging/firebase_messaging.dart';

@override
void initState() {
  super.initState();
  
  // وقتی اپ در foreground است
  FirebaseMessaging.onMessage.listen((RemoteMessage message) {
    _handleNotification(message);
  });
  
  // وقتی اپ در background است و کاربر روی notification کلیک می‌کند
  FirebaseMessaging.onMessageOpenedApp.listen((RemoteMessage message) {
    _handleNotification(message);
  });
  
  // اگر اپ با کلیک روی notification باز شده باشد
  FirebaseMessaging.instance.getInitialMessage().then((message) {
    if (message != null) {
      _handleNotification(message);
    }
  });
}

void _handleNotification(RemoteMessage message) {
  final type = message.data['type'];
  
  switch (type) {
    case 'price_alert':
      final symbol = message.data['symbol'];
      final currentPrice = message.data['current_price'];
      final targetPrice = message.data['target_price'];
      final alertType = message.data['alert_type'];
      
      // هدایت کاربر به صفحه نمودار قیمت آن ارز
      Navigator.pushNamed(context, '/price-chart', arguments: {
        'symbol': symbol,
        'currentPrice': currentPrice,
      });
      break;
      
    case 'volatility_alert':
      // نمایش هشدار نوسان شدید
      break;
      
    case 'portfolio_summary':
      // هدایت به صفحه پورتفوی
      break;
      
    default:
      break;
  }
}
```

---

## مرحله ۷: Android Notification Channels

برای اندروید ۸+، حتماً این کانال‌ها را در اپلیکیشن بسازید:

```dart
final flutterLocalNotificationsPlugin = FlutterLocalNotificationsPlugin();

// مقداردهی اولیه
final androidSettings = AndroidInitializationSettings('@mipmap/ic_launcher');
final initializationSettings = InitializationSettings(
  android: androidSettings,
);
await flutterLocalNotificationsPlugin.initialize(initializationSettings);

// ساخت کانال‌ها
final channels = [
  AndroidNotificationChannel(
    'transactions',
    'Transactions',
    description: 'Send/Receive transaction notifications',
    importance: Importance.high,
  ),
  AndroidNotificationChannel(
    'security',
    'Security',
    description: 'Security and login alerts',
    importance: Importance.max,  // Critical
  ),
  AndroidNotificationChannel(
    'price_alerts',  // مهم برای Price Alert
    'Price Alerts',
    description: 'Price target reached notifications',
    importance: Importance.defaultImportance,
  ),
  AndroidNotificationChannel(
    'network',
    'Network',
    description: 'Gas fees and network status',
    importance: Importance.defaultImportance,
  ),
  AndroidNotificationChannel(
    'engagement',
    'Coinceeper News',
    description: 'New listings, updates, rewards',
    importance: Importance.defaultImportance,
  ),
];

for (final channel in channels) {
  await flutterLocalNotificationsPlugin
      .resolvePlatformSpecificImplementation<
          AndroidFlutterLocalNotificationsPlugin>()
      ?.createNotificationChannel(channel);
}
```

---

## دیاگرام UI پیشنهادی برای صفحه Price Alert

```
┌─────────────────────────────────────┐
│  ← Price Alerts              [+ Add] │
├─────────────────────────────────────┤
│                                     │
│  ┌─────────────────────────────┐   │
│  │  BTC                        │   │
│  │  Current: $74,500           │   │
│  │                             │   │
│  │  ┌──── Alert: Above ─────┐ │   │
│  │  │ Target: $75,000       │ │   │
│  │  │ [       🔔       ]    │ │   │
│  │  └───────────────────────┘ │   │
│  │           [Delete]         │   │
│  └─────────────────────────────┘   │
│                                     │
│  ┌─────────────────────────────┐   │
│  │  ETH                        │   │
│  │  Current: $3,200            │   │
│  │                             │   │
│  │  ┌──── Alert: Below ──────┐ │   │
│  │  │ Target: $3,000         │ │   │
│  │  │ [       🔔       ]     │ │   │
│  │  └───────────────────────┘ │   │
│  │           [Delete]         │   │
│  └─────────────────────────────┘   │
│                                     │
│  ┌─────────────────────────────┐   │
│  │  + Create New Alert         │   │
│  └─────────────────────────────┘   │
└─────────────────────────────────────┘
```

---

## خلاصه APIها

| عملیات | Method | Endpoint | توضیحات |
|---------|--------|----------|---------|
| ثبت دستگاه | `POST` | `/api/notifications/register-device` | هر بار که اپ باز می‌شود |
| ساخت هشدار | `POST` | `/api/notifications/price-alert` | کاربر مقدار target را تعیین می‌کند |
| دریافت هشدارها | `GET` | `/api/notifications/price-alerts/{UserID}` | نمایش لیست هشدارهای فعال |
| حذف هشدار | `DELETE` | `/api/notifications/price-alert` | کاربر هشداری را حذف می‌کند |
| قیمت گروهی 🆕 | `GET` | `/api/notifications/price-alerts/prices?symbols=BTC,ETH,SOL` | دریافت قیمت چند سمبل با یک درخواست |

---

## 🆕 دریافت قیمت گروهی (Bulk Prices) — حل مشکل N+1

این endpoint جدید برای حل مشکل **N+1** طراحی شده است. به جای ارسال یک درخواست جداگانه برای هر سمبل، با یک درخواست قیمت همه سمبل‌ها را دریافت کنید.

### اندپوینت

```
GET /api/notifications/price-alerts/prices?symbols=BTC,ETH,SOL
```

### پاسخ موفق

```json
{
    "success": true,
    "prices": {
        "BTC": 67500.25,
        "ETH": 3450.80,
        "SOL": 145.30
    },
    "count": 3
}
```

### نمونه کد Flutter — جایگزین حلقه N+1

```dart
// ❌ روش قدیمی (N+1) — کند
Future<Map<String, double?>> _fetchPricesOld(List<String> symbols) async {
  final result = <String, double?>{};
  for (final symbol in symbols) {
    final price = await api.getPriceV2(symbol);  // N تا درخواست!
    result[symbol] = price;
  }
  return result;
}

// ✅ روش جدید (یک درخواست) — سریع
Future<Map<String, double?>> _fetchPricesBulk(List<String> symbols) async {
  final symbolsParam = symbols.join(',');
  final response = await http.get(
    Uri.parse('https://coinceeper.com/api/notifications/price-alerts/prices?symbols=$symbolsParam'),
  );
  if (response.statusCode == 200) {
    final body = jsonDecode(response.body);
    if (body['success'] == true && body['prices'] != null) {
      return Map<String, double?>.from(
        (body['prices'] as Map).map((k, v) => MapEntry(k, v?.toDouble())),
      );
    }
  }
  return {};
}
```

---

## نکات مهم برای توسعه‌دهنده فرانت

1. **ثبت Device Token را فراموش نکنید** — اگر token ثبت نشود، کاربر PUSH notification دریافت نمی‌کند.
2. **Symbolها همیشه با حروف بزرگ (UPPERCASE)** ارسال شوند (مثلاً `BTC` نه `btc`).
3. **هشدارها یک‌بار مصرف هستند** — بعد از فعال شدن، بک‌اند آن را حذف می‌کند و کاربر باید دوباره بسازد.
4. **تاخیر ۱۰ دقیقه‌ای** — Scheduler هر ۱۰ دقیقه هشدارها را چک می‌کند، پس ممکن است بین رسیدن قیمت به target و دریافت نوتیفیکیشن چند دقیقه delay باشد.
5. **دریافت لیست کامل ارزها** — از `GET /api/all-currencies` برای نمایش ارزهای قابل انتخاب به کاربر استفاده کنید.
6. **اعتبارسنجی سمت فرانت** — قبل از ارسال درخواست، بررسی کنید که `TargetPrice` یک عدد مثبت باشد.
7. **اندروید ۱۳+** — برای دریافت نوتیفیکیشن در اندروید ۱۳ به بعد، حتماً permission `POST_NOTIFICATIONS` را درخواست کنید.

## بهینه‌سازی‌های Performance برای فرانت‌اند

### ۱. کش کردن لیست ارزها در حافظه (Cache Currencies Locally)

لیست همه ارزها (`GET /api/all-currencies`) را یکبار در حافظه کش کنید و فقط هر ۵ دقیقه یکبار به‌روزرسانی کنید:

```dart
class CurrencyCache {
  static List<Currency>? _cached;
  static DateTime? _lastFetch;
  static const _ttl = Duration(minutes: 5);

  static Future<List<Currency>> getAll() async {
    if (_cached != null && _lastFetch != null &&
        DateTime.now().difference(_lastFetch!) < _ttl) {
      return _cached!;
    }
    _cached = await ApiService.instance.getAllCurrencies();
    _lastFetch = DateTime.now();
    return _cached!;
  }
}
```

### ۲. به‌روزرسانی Optimistic در Create/Delete

به جای اینکه بعد از ایجاد/حذف هشدار، کل لیست را دوباره از سرور بگیرید، مستقیماً state محلی را به‌روز کنید:

```dart
// ❌ روش قدیمی — کند (۲ تا API call)
await api.createPriceAlert(request);
await loadPriceAlerts();  // دوباره GET + قیمت‌ها

// ✅ روش جدید — سریع (بدون API call اضافی)
Future<void> createPriceAlertOptimistic(PriceAlertRequest request) async {
  // ۱. اول state را به‌روز کن (UI بلافاصله آپدیت می‌شود)
  setState(() {
    _alerts.add(PriceAlert(
      symbol: request.symbol,
      targetPrice: request.targetPrice,
      alertType: request.alertType,
    ));
  });

  // ۲. بعد درخواست API را بفرست
  final response = await api.createPriceAlert(request);
  if (!response.success) {
    // ۳. اگر خطا داشت، state را برگردان (Rollback)
    setState(() {
      _alerts.removeLast();
    });
  }
}
```

### ۳. استفاده از Bulk Price Endpoint

برای دریافت قیمت همه هشدارها از endpoint گروهی استفاده کنید:

```dart
// ❌ روش قدیمی
for (final alert in alerts) {
  final price = await api.getPriceV2(alert.symbol);  // N تا درخواست
}

// ✅ روش جدید
final symbols = alerts.map((a) => a.symbol).join(',');
final prices = await api.getBulkPrices(symbols);  // ۱ درخواست
```

```xml
<!-- AndroidManifest.xml -->
<uses-permission android:name="android.permission.POST_NOTIFICATIONS"/>
```

```dart
// درخواست permission اندروید ۱۳+
if (Platform.isAndroid) {
  final plugin = FlutterLocalNotificationsPlugin();
  final androidImplementation = plugin.resolvePlatformSpecificImplementation<
      AndroidFlutterLocalNotificationsPlugin>();
  await androidImplementation?.requestNotificationsPermission();
}
```

---

## ۹. App Version — Force Update (نسخه اجباری)

### معرفی

سیستم **Force Update** به شما اجازه می‌دهد کاربران نسخه‌های قدیمی اپ را مجبور به آپدیت کنید. 
هر بار که کاربر اپ را باز می‌کند، نسخه اپ با `min_version` تعریف شده در سرور مقایسه می‌شود.

### Endpoint

```
GET /api/app/version
```

#### نمونه Response

```json
{
  "success": true,
  "android": {
    "min_version": "1.0.0",
    "latest_version": "1.0.1",
    "update_url": "https://play.google.com/store/apps/details?id=com.coinceeper.wallet"
  },
  "ios": {
    "min_version": "1.0.0",
    "latest_version": "1.0.1",
    "update_url": "https://apps.apple.com/app/id0000000000"
  },
  "force_update_message": {
    "title": "Update Required",
    "body": "A new version of Coinceeper is available. Please update to continue using the app."
  },
  "optional_update_message": {
    "title": "New Version Available",
    "body": "A new version of Coinceeper is available. Would you like to update?"
  }
}
```

### نحوه استفاده در فرانت‌اند

۱. هنگام باز شدن اپ (SplashScreen) endpoint را صدا بزنید
۲. `min_version` مربوط به پلتفرم خود را با نسخه فعلی اپ مقایسه کنید
۳. اگر `currentVersion < minVersion` ← مودال **Force Update** (قابل بستن نیست)
۴. اگر `currentVersion < latestVersion` ← مودال **Optional Update** (دکمه Later دارد)
۵. اگر سرور در دسترس نبود ← اپ به کار خود ادامه می‌دهد

### کد نمونه (Flutter)

فایل‌های کامل در پوشه `api-docs/`:
- `flutter_version_check_service.dart`
- `flutter_force_update_dialog.dart`
- `flutter_startup_integration.dart`

### به‌روزرسانی نسخه

```bash
# مشاهده وضعیت فعلی
python scripts/update_app_version.py --status

# آپدیت نسخه اندروید
python scripts/update_app_version.py \
  --platform android \
  --min 1.2.0 \
  --latest 1.2.5 \
  --url "https://play.google.com/store/apps/details?id=com.coinceeper.wallet"

# آپدیت نسخه iOS
python scripts/update_app_version.py \
  --platform ios \
  --min 1.2.0 \
  --latest 1.2.5 \
  --url "https://apps.apple.com/app/id..."
```
