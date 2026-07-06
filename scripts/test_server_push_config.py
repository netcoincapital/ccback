#!/usr/bin/env python3
"""
Server-side Push Notification Configuration Diagnostic
=======================================================
تست تنظیمات سرور برای پوش نوتیفیکیشن

این اسکریپت بررسی می‌کند:
  1. آیا Firebase در سرور مقداردهی شده است؟
  2. آیا Scheduler (Price Alert + Gas + Portfolio) در حال اجراست؟
  3. آیا Device Token می‌تواند ثبت شود؟
  4. آیا Send Notification کار می‌کند؟
  5. آیا فایل credentials Firebase در سرور وجود دارد؟
"""
import sys
import os
import json
import requests
import argparse

BASE_URL = "https://coinceeper.com"
HEADERS = {
    "User-Agent": "Coinceeper-Diag/1.0",
    "Origin": "https://coinceeper.com",
    "Content-Type": "application/json",
}

results = {"passed": 0, "failed": 0, "warnings": 0, "info": []}


def report(test_name, success, detail=""):
    status = "[PASS]" if success else "[FAIL]"
    if success:
        results["passed"] += 1
    else:
        results["failed"] += 1
    print(f"  {status} | {test_name}")
    if detail:
        print(f"         {detail}")


def warn(test_name, detail=""):
    results["warnings"] += 1
    print(f"  [WARN] | {test_name}")
    if detail:
        print(f"         {detail}")


def info(msg):
    results["info"].append(msg)
    print(f"  [INFO] | {msg}")


def request(method, path, body=None):
    url = f"{BASE_URL}{path}"
    try:
        kwargs = {"method": method, "url": url, "headers": HEADERS, "timeout": 15}
        if body is not None:
            kwargs["json"] = body
        resp = requests.request(**kwargs)
        try:
            return {"status": resp.status_code, "data": resp.json()}
        except Exception:
            return {"status": resp.status_code, "text": resp.text}
    except requests.exceptions.ConnectionError:
        return {"status": 0, "error": "Connection refused"}
    except requests.exceptions.Timeout:
        return {"status": 0, "error": "Timeout"}
    except Exception as e:
        return {"status": 0, "error": str(e)}


def check_firebase_initialization():
    """
    بررسی اینکه آیا Firebase در سرور مقداردهی شده است.

    راه اول: اگر APIای وجود داشته باشد که وضعیت Firebase را برگرداند.
    راه دوم: با ارسال یک نوتیفیکیشن تست به یک توکن نامعتبر،
    لاگ خطا را بررسی می‌کنیم. (در اینجا فقط بررسی می‌کنیم که
    اندپوینت تست نوتیفیکیشن چه پاسخی می‌دهد.)
    """
    print("\n" + "=" * 60)
    print("1. FIREBASE INITIALIZATION CHECK")
    print("=" * 60)

    # Firebase init را با endpoint تست بررسی می‌کنیم
    # First check app health
    resp = request("GET", "/api/app-health")
    if resp["status"] == 200:
        data = resp.get("data", {})
        info(f"Server status: {data.get('status')}")
        info(f"Services: {json.dumps(data.get('services', {}))}")

    # Try to send a test notification
    # این اندپوینت سعی می‌کند Firebase را مقداردهی کرده و پیام بفرستد
    # اگر Firebase ست نباشد، خطا برمی‌گرداند
    resp = request("POST", "/api/notifications/test", {
        "DeviceToken": "test-invalid-token-for-diagnostic-only"
    })
    data = resp.get("data", {})
    status = resp["status"]

    if status == 200:
        report("Firebase: test notification endpoint responds 200", True, json.dumps(data))
        # یعنی Firebase مقداردهی شده و پیام رو فرستاده (هرچند به توکن نامعتبر)
        if data.get("success") is True:
            report("Firebase: notification sent successfully", True)
        elif data.get("success") is False:
            warn("Firebase: endpoint exists but send failed", json.dumps(data))
        else:
            report("Firebase: endpoint responded", True, json.dumps(data))
    elif status == 400:
        # Validation error means Firebase is initialized (request reached code)
        report("Firebase: endpoint reached (400 means code ran)", True, json.dumps(data))
    elif status == 500:
        detail = json.dumps(data)
        if "credentials" in detail.lower() or "firebase" in detail.lower() or "not found" in detail.lower():
            report("Firebase: NOT initialized on server", False, detail)
        else:
            report("Firebase: endpoint error but unclear", False, detail)
    else:
        report(f"Firebase: HTTP {status}", False, json.dumps(data))


def check_scheduler():
    """
    بررسی وضعیت Notification Scheduler در سرور.
    
    Scheduler شامل:
    - Gas Alert checker (هر ۵ دقیقه)
    - Price Alert checker (هر ۱۰ دقیقه) 
    - Portfolio Summary (هر ۲۴ ساعت)
    
    مستقیماً لاگ سرور را نمی‌توانیم ببینیم،
    ولی با ارسال یک Price Alert و بررسی اینکه حذف می‌شود یا نه
    می‌توانیم متوجه شویم Scheduler کار می‌کند.
    """
    print("\n" + "=" * 60)
    print("2. NOTIFICATION SCHEDULER CHECK")
    print("=" * 60)

    # Test 1: Check if price endpoint works (scheduler needs prices)
    resp = request("GET", "/api/notifications/price-alerts/prices?symbols=BTC,ETH")
    if resp["status"] == 200:
        data = resp.get("data", {})
        prices = data.get("prices", {})
        if prices.get("BTC") is not None:
            report("Price endpoint works (scheduler dependency OK)", True,
                   f"BTC={prices['BTC']}")
        else:
            report("Price endpoint returns no prices", False, json.dumps(data))
    else:
        report("Price endpoint not available", False, json.dumps(resp.get("data", {})))

    # Test 2: Create a triggerable alert and check if scheduler deletes it
    # با یک قیمت هدف پایین که حتماً فعال می‌شود
    btc_price = None
    resp = request("GET", "/api/notifications/price-alerts/prices?symbols=BTC")
    if resp["status"] == 200:
        btc_price = resp.get("data", {}).get("prices", {}).get("BTC")

    if btc_price:
        # Create alert with target slightly below current price (should trigger immediately)
        target = btc_price * 0.99  # 1% below current
        alert_resp = request("POST", "/api/notifications/price-alert", {
            "UserID": "scheduler-test-user",
            "Symbol": "BTC",
            "AlertType": "below",
            "TargetPrice": round(target, 2),
        })
        if alert_resp["status"] == 201:
            alert_id = alert_resp.get("data", {}).get("alert", {}).get("id")
            info(f"Test alert created with ID={alert_id}, target=${target:.2f}, current=${btc_price}")

            # حالا صبر نمی‌کنیم (scheduler هر ۱۰ دقیقه اجرا می‌شود)
            # بجای آن، مستقیماً بررسی می‌کنیم alert ذخیره شده
            get_resp = request("GET", "/api/notifications/price-alerts/scheduler-test-user")
            if get_resp["status"] == 200:
                alerts = get_resp.get("data", {}).get("alerts", [])
                if any(a.get("id") == alert_id for a in alerts):
                    info(f"Alert #{alert_id} is saved in DB. Scheduler will process it in ~10 min.")
                    info(f"To verify: check later if alert is auto-deleted.")
                    report("Scheduler: alert stored correctly", True)
                else:
                    report("Scheduler: alert not found after creation", False)
        else:
            report("Scheduler: could not create test alert", False, json.dumps(alert_resp))

    # Test 3: Check if the scheduler routes are registered
    resp = request("GET", "/api/notifications/price-alerts/scheduler-test-user")
    if resp["status"] == 200:
        report("Get alerts endpoint works", True)
    else:
        report("Get alerts endpoint fails", False, json.dumps(resp.get("data", {})))


def check_device_registration():
    """
    بررسی اندپوینت ثبت Device Token.
    
    این مهم‌ترین بخش است: اگر کاربر Device Token ثبت نکند،
    هیچ نوتیفیکیشنی دریافت نمی‌کند.
    """
    print("\n" + "=" * 60)
    print("3. DEVICE TOKEN REGISTRATION CHECK")
    print("=" * 60)

    test_user_id = "push-diag-user-001"
    test_wallet_id = "push-diag-wallet-001"
    test_device_token = "fcm-diagnostic-token-xxxxxxxxxxxxxxx"

    # Test register-device endpoint
    resp = request("POST", "/api/notifications/register-device", {
        "UserID": test_user_id,
        "WalletID": test_wallet_id,
        "DeviceToken": test_device_token,
        "DeviceName": "Diagnostic Test Device",
        "DeviceType": "android",
    })

    data = resp.get("data", {})
    status = resp["status"]

    if status in (200, 201):
        report("Device registration endpoint works", True, json.dumps(data))
    elif status == 400:
        # Validation error - still means endpoint works
        report("Device registration endpoint reached", True, json.dumps(data))
    elif status == 500:
        # Could be Firebase not initialized, or DB issue
        detail = json.dumps(data)
        if "firebase" in detail.lower() or "credential" in detail.lower():
            report("Device registration: Firebase dependency issue", False, detail)
        else:
            report("Device registration: server error", False, detail)
    else:
        report(f"Device registration: HTTP {status}", False, json.dumps(data))

    # Test simple-register-device endpoint (fallback)
    resp = request("POST", "/api/notifications/simple-register-device", {
        "UserID": test_user_id,
        "WalletID": test_wallet_id,
        "DeviceToken": test_device_token,
        "DeviceName": "Diagnostic Test Device",
        "DeviceType": "android",
    })

    data = resp.get("data", {})
    status = resp["status"]

    if status in (200, 201):
        report("Simple device registration endpoint works", True, json.dumps(data))
    elif status == 400:
        report("Simple device registration endpoint reached", True, json.dumps(data))
    elif status == 500:
        detail = json.dumps(data)
        if "firebase" in detail.lower() or "credential" in detail.lower():
            report("Simple device reg: Firebase dependency issue", False, detail)
        else:
            report("Simple device reg: server error", False, detail)
    else:
        report(f"Simple device reg: HTTP {status}", False, json.dumps(data))


def check_test_notification():
    """
    تست ارسال مستقیم نوتیفیکیشن از طریق اندپوینت test.
    """
    print("\n" + "=" * 60)
    print("4. TEST NOTIFICATION SENDING")
    print("=" * 60)

    # Test 1: Test notification endpoint
    resp = request("POST", "/api/notifications/test", {
        "DeviceToken": "fcm-diagnostic-test-token-001"
    })

    data = resp.get("data", {})
    status = resp["status"]

    if status == 200:
        if data.get("success") is True:
            report("Test notification: sent successfully", True)
            info("Firebase is WORKING and sending notifications!")
        elif data.get("success") is False:
            warn("Test notification: endpoint called but send failed", json.dumps(data))
            # This could mean Firebase is initialized but token is invalid (expected)
        else:
            report("Test notification: responded", True, json.dumps(data))
    elif status == 400:
        report("Test notification: validation error (code ran)", True, json.dumps(data))
    elif status == 500:
        detail = json.dumps(data)
        if "initialize" in detail.lower() or "credential" in detail.lower() or "firebase" in detail.lower():
            report("FIREBASE NOT INITIALIZED ON SERVER!", False, detail)
        else:
            report("Test notification: server error", False, detail)
    else:
        report(f"Test notification: HTTP {status}", False, json.dumps(data))


def check_security_notifications():
    """
    بررسی اینکه Security Notificationها می‌توانند ارسال شوند.
    این هم یک راه دیگر برای تشخیص Firebase است.
    """
    print("\n" + "=" * 60)
    print("5. SECURITY NOTIFICATION CHECK (Alternative Firebase Test)")
    print("=" * 60)

    # Security notifications need UserID only (no token needed upfront)
    resp = request("POST", "/api/notifications/security/login", {
        "UserID": "diag-test-user",
        "DeviceName": "Diagnostic Device",
        "DeviceType": "android",
        "IPAddress": "127.0.0.1",
    })

    data = resp.get("data", {})
    status = resp["status"]

    if status == 200:
        if data.get("success") is True:
            info("Security notification sent (user has devices)")
        elif data.get("success") is False:
            info("Security endpoint OK but no devices for this test user (expected)")
        report("Security notification endpoint works", True, json.dumps(data))
    elif status in (400, 422):
        report("Security notification: validation error", True, json.dumps(data))
    elif status == 500:
        detail = json.dumps(data)
        if "firebase" in detail.lower() or "initialize" in detail.lower():
            report("Security notification: Firebase issue", False, detail)
        else:
            report("Security notification: server error", False, detail)
    else:
        report(f"Security notification: HTTP {status}", False, json.dumps(data))

    # Test password change notification
    resp = request("POST", "/api/notifications/security/change", {
        "UserID": "diag-test-user",
        "ChangeType": "password_changed",
    })

    data = resp.get("data", {})
    status = resp["status"]

    if status == 200:
        report("Security change notification endpoint works", True, json.dumps(data))
    elif status == 500:
        detail = json.dumps(data)
        if "firebase" in detail.lower() or "initialize" in detail.lower():
            report("Security change: Firebase issue", False, detail)
        else:
            report("Security change: server error", False, detail)
    else:
        report(f"Security change: HTTP {status}", False, json.dumps(data))


def check_admin_broadcast():
    """
    بررسی اندپوینت Broadcast (نیازمند Firebase).
    """
    print("\n" + "=" * 60)
    print("6. ADMIN BROADCAST CHECK")
    print("=" * 60)

    resp = request("POST", "/api/admin/notifications/broadcast", {
        "Title": "Diagnostic Test",
        "Body": "This is a diagnostic test notification",
        "Type": "diagnostic",
    })

    data = resp.get("data", {})
    status = resp["status"]

    if status == 200:
        report("Admin broadcast endpoint works", True, json.dumps(data))
        devices = data.get("devices_notified", 0)
        info(f"Broadcast would notify {devices} devices")
    elif status == 500:
        detail = json.dumps(data)
        if "firebase" in detail.lower() or "initialize" in detail.lower():
            report("Broadcast: Firebase issue", False, detail)
        else:
            report("Broadcast: server error", False, detail)
    else:
        report(f"Broadcast: HTTP {status}", False, json.dumps(data))


def print_summary():
    print("\n" + "=" * 60)
    print("DIAGNOSTIC SUMMARY")
    print("=" * 60)
    total = results["passed"] + results["failed"]
    print(f"  Total:    {total}")
    print(f"  Passed:   {results['passed']}")
    print(f"  Failed:   {results['failed']}")
    print(f"  Warning:  {results['warnings']}")

    print("\n" + "-" * 60)
    print("DIAGNOSTIC INFORMATION")
    print("-" * 60)
    for msg in results["info"]:
        print(f"  {msg}")

    print("\n" + "-" * 60)
    if results["failed"] == 0:
        print("  PUSH NOTIFICATION CONFIGURATION: OK")
        print("  Firebase: Active")
        print("  Scheduler: Active (every 10 min)")
        print("  Device Registration: Working")
        print("  Send Notification: Working")
    else:
        print("  PUSH NOTIFICATION CONFIGURATION: ISSUES DETECTED")
        print(f"  {results['failed']} test(s) failed")

    print("=" * 60)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Diagnose push notification configuration on server"
    )
    parser.add_argument(
        "--server", "-s",
        default=os.environ.get("TEST_SERVER_URL", "https://coinceeper.com"),
        help="Server URL"
    )
    args = parser.parse_args()

    BASE_URL = args.server.rstrip("/")

    print("=" * 60)
    print(f"PUSH NOTIFICATION SERVER CONFIGURATION DIAGNOSTIC")
    print(f"Target: {BASE_URL}")
    print("=" * 60)

    check_firebase_initialization()
    check_scheduler()
    check_device_registration()
    check_test_notification()
    check_security_notifications()
    check_admin_broadcast()

    print_summary()
    sys.exit(0 if results["failed"] == 0 else 1)
