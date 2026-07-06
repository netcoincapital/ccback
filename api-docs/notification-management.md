# Notification Management — Frontend Guide

## Overview

Coinceeper now has a **complete push notification system** covering 5 priority areas:

| Priority | Type | Trigger | API to Call |
|----------|------|---------|-------------|
| **P1** | Financial Transactions | Block Scanner detects new tx | Auto (no API needed) |
| **P2** | Security & Account | Frontend calls API | `POST /api/notifications/security/*` |
| **P3** | Price Alerts & Portfolio | User sets alerts + Background Scheduler | `POST /api/notifications/price-alert` |
| **P4** | Network & Gas | Admin API + Scheduler | `POST /api/admin/notifications/network-*` |
| **P5** | Engagement & Features | Admin API | `POST /api/admin/notifications/*` |

---

## 1. Device Registration (Prerequisite)

Before any push notifications work, the app must register the user's device:

```
POST /api/notifications/register-device
Content-Type: application/json

{
    "DeviceToken": "f0lh9BMO...APA91bGhOH...",
    "Platform": "android" | "ios" | "web",
    "WalletID": "550e8400-e29b-41d4-a716-446655440000",
    "UserID": "d7fd960c-0b3b-4f0c-8963-baa6b365953d"
}
```

> **Important**: This must be called every time the app starts to ensure token freshness.

---

## 2. Priority 2 — Security Notifications (Frontend → Backend)

The **frontend** must call these APIs when security events happen. The backend then sends the push notification.

### 2.1 New Login Detected

Call this when the user logs in from a new device or location:

```
POST /api/notifications/security/login
Content-Type: application/json

{
    "UserID": "d7fd960c-0b3b-4f0c-8963-baa6b365953d",
    "DeviceName": "Samsung Galaxy S24",
    "DeviceType": "android",
    "IPAddress": "192.168.1.1",
    "Location": "Tehran, Iran"
}
```

- `DeviceType`: `android`, `ios`, or `web`
- `Location`: optional but recommended

### 2.2 Security Setting Changed

Call this when the user changes security settings:

```
POST /api/notifications/security/change
Content-Type: application/json

{
    "UserID": "d7fd960c-0b3b-4f0c-8963-baa6b365953d",
    "ChangeType": "password_changed" | "pin_changed" | "2fa_enabled" | "2fa_disabled",
    "DeviceName": "Samsung Galaxy S24"
}
```

### 2.3 Suspicious Activity

Call this for unusual patterns:

```
POST /api/notifications/security/suspicious
Content-Type: application/json

{
    "UserID": "d7fd960c-0b3b-4f0c-8963-baa6b365953d",
    "ActivityType": "failed_login" | "unusual_transaction" | "new_ip",
    "Description": "5 failed login attempts in 2 minutes",
    "Severity": "info" | "warning" | "critical"
}
```

---

## 3. Priority 3 — Price Alerts (User Settings + Backend Scheduler)

> ✅ **Price Alert Scheduler فعال است.** بک‌اند هر ۱۰ دقیقه همه هشدارهای کاربران را با قیمت‌های فعلی مقایسه می‌کند و در صورت فعال شدن، از طریق FCM Push نوتیفیکیشن می‌فرستد. پس از فعال شدن، هشدار به صورت خودکار از دیتابیس حذف می‌شود (یک‌بار مصرف).

### 3.1 Creating a Price Alert (Frontend → Backend)

When the user sets a price alert, call:

```
POST /api/notifications/price-alert
Content-Type: application/json

{
    "UserID": "d7fd960c-0b3b-4f0c-8963-baa6b365953d",
    "Symbol": "BTC",
    "TargetPrice": 50000,
    "AlertType": "above"
}
```

- `AlertType`: `"above"` (price goes above target) or `"below"` (price drops below target)

### 3.2 Getting User's Price Alerts

```
GET /api/notifications/price-alerts/{UserID}

Response:
{
    "success": true,
    "alerts": [
        {"symbol": "BTC", "target_price": 50000.0, "alert_type": "above"},
        {"symbol": "ETH", "target_price": 3000.0, "alert_type": "below"}
    ]
}
```

### 3.3 Deleting a Price Alert

```
DELETE /api/notifications/price-alert
Content-Type: application/json

{
    "UserID": "d7fd960c-0b3b-4f0c-8963-baa6b365953d",
    "Symbol": "BTC",
    "AlertType": "above"
}
```

### 3.4 Portfolio Summary (Manual Trigger)

```
POST /api/admin/notifications/portfolio-summary/{UserID}
```

The scheduler also sends this automatically every 24 hours.

---

## 4. Priority 4 — Network & Gas (Admin + Auto Scheduler)

### 4.1 Gas Fee Alerts (Automatic)

The background scheduler checks gas prices every 5 minutes. When gas exceeds thresholds, alerts are sent to users who have recently transacted on that chain.

**Thresholds**:
- Ethereum: ≥ 100 Gwei (high), ≥ 200 Gwei (very high)
- BSC: ≥ 10 Gwei (high), ≥ 20 Gwei (very high)
- Polygon: ≥ 200 Gwei (high), ≥ 500 Gwei (very high)

### 4.2 Network Status (Admin via API)

```
POST /api/admin/notifications/network-status
Content-Type: application/json

{
    "Blockchain": "Ethereum",
    "Status": "maintenance" | "outage" | "degraded" | "restored",
    "Message": "Network maintenance scheduled at 2:00 UTC"
}
```

### 4.3 Network Upgrade Notification (Admin via API)

```
POST /api/admin/notifications/network-upgrade
Content-Type: application/json

{
    "Blockchain": "Ethereum",
    "UpgradeName": "Pectra",
    "Description": "Major protocol upgrade with EIP improvements",
    "EstimatedTime": "June 2026"
}
```

---

## 5. Priority 5 — Engagement & Features (Admin API)

### 5.1 New Coin Listing

```
POST /api/admin/notifications/new-listing
Content-Type: application/json

{
    "Symbol": "PEPE",
    "Name": "Pepe Coin",
    "Blockchain": "Ethereum",
    "Description": "New memecoin now available"
}
```

### 5.2 Breaking News

```
POST /api/admin/notifications/breaking-news
Content-Type: application/json

{
    "Title": "Major Exchange Listing",
    "Body": "PEPE listed on major exchanges, +200% in 24h",
    "URL": "https://coinceeper.com/news/pepe-listing"
}
```

### 5.3 App Update Notification

```
POST /api/admin/notifications/app-update
Content-Type: application/json

{
    "Version": "2.4.0",
    "Changes": ["New staking feature", "Bug fixes", "Security improvements"],
    "ForceUpdate": false
}
```

### 5.4 Rewards & Airdrops

```
POST /api/admin/notifications/reward
Content-Type: application/json

{
    "UserID": "d7fd960c-0b3b-4f0c-8963-baa6b365953d",
    "RewardType": "staking" | "airdrop" | "cashback" | "referral",
    "Amount": "0.5",
    "Symbol": "NCC",
    "Description": "Monthly staking rewards"
}
```

### 5.5 General Broadcast

```
POST /api/admin/notifications/broadcast
Content-Type: application/json

{
    "Title": "🚀 Coinceeper v2 is live!",
    "Body": "Experience the new non-custodial wallet",
    "Type": "general"
}
```

---

## 6. FCM Data Payload Format

All push notifications include a `data` payload for deep linking:

```json
{
    "type": "transaction_received" | "send" | "receive" | "security_login" |
            "security_change" | "security_suspicious" | "price_alert" |
            "volatility_alert" | "portfolio_summary" | "gas_alert" |
            "network_status" | "network_upgrade" | "new_listing" |
            "reward" | "breaking_news" | "app_update",
    // Plus notification-specific fields
}
```

### Handling Data in Flutter

```dart
// In your FirebaseMessaging handler
FirebaseMessaging.onMessage.listen((RemoteMessage message) {
  final type = message.data['type'];
  
  switch (type) {
    case 'transaction_received':
    case 'send':
    case 'receive':
      // Navigate to transaction details
      break;
    case 'security_login':
      // Show security alert dialog
      break;
    case 'price_alert':
      // Navigate to price chart
      break;
    case 'app_update':
      // Open app store for update
      break;
    case 'breaking_news':
      // Open news article
      break;
    case 'reward':
      // Show reward animation
      break;
    case 'gas_alert':
      // Show warning when user tries to send
      break;
    default:
      // General notification
  }
});
```

---

## 7. Notification Channels (Android)

For Android 8+, create these notification channels:

| Channel ID | Name | Description | Importance |
|-----------|------|-------------|------------|
| `transactions` | Transactions | Send/Receive notifications | High |
| `security` | Security | Login alerts, suspicious activity | Critical |
| `price_alerts` | Price Alerts | Price targets reached | Default |
| `network` | Network | Gas fees, network status | Default |
| `engagement` | Coinceeper News | New listings, updates, rewards | Default |

### Flutter example:

```dart
final flutterLocalNotificationsPlugin = FlutterLocalNotificationsPlugin();

// Initialize channels
final androidSettings = AndroidInitializationSettings('@mipmap/ic_launcher');
final initializationSettings = InitializationSettings(
  android: androidSettings,
);

await flutterLocalNotificationsPlugin.initialize(initializationSettings);

// Create channels
final androidChannel = AndroidNotificationChannel(
  'transactions', 'Transactions',
  description: 'Send/Receive notifications',
  importance: Importance.high,
);
await flutterLocalNotificationsPlugin
    .resolvePlatformSpecificImplementation<
        AndroidFlutterLocalNotificationsPlugin>()
    ?.createNotificationChannel(androidChannel);
```

---

## 8. Summary Flow Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                    NOTIFICATION SYSTEM FLOW                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Block Scanner ──► Priority 1 ──► FCM Push (Auto)              │
│                                                                  │
│  Frontend Login ──► Security API ──► FCM Push (P2)             │
│                                                                  │
│  User Sets Alert ──► Price API ──► DB ──► Scheduler ──► Push   │
│                                                                  │
│  Gas Checker (5min) ──► Threshold? ──► Scheduler ──► FCM (P4)  │
│                                                                  │
│  Admin Panel ──► Engagement API ──► Broadcast ──► All Users     │
│                                                                  │
│  Admin Panel ──► Network API ──► Affected Users ──► FCM (P4)    │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 9. Important Notes for the Frontend Team

1. **Always register the device token on app start** — old tokens expire.
2. **Security notifications require the frontend to detect** the event (new login, setting change, suspicious pattern) and call the respective API.
3. **Price alerts are checked every 10 minutes** by the backend scheduler — there might be a short delay.
4. **Gas fee alerts** are only sent to users who have recently transacted on the chain.
5. **Portfolio summaries** are sent automatically every 24 hours.
6. **All admin endpoints** (`/api/admin/notifications/*`) are designed for backend admin panel — they require authentication.
7. **The `data` payload** is the key to deep linking. Parse `message.data['type']` in Flutter to route correctly.
8. **No special notification permission is needed** on Android 13+ if the app targets API 33 — use `POST_NOTIFICATIONS` permission.
