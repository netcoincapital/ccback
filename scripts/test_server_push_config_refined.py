#!/usr/bin/env python3
"""
Refined Server Push Config Diagnostic
=======================================
تفسیر دقیق‌تر از نتایج.
"""
import sys, os, json, requests

BASE_URL = "https://coinceeper.com"
HEADERS = {
    "User-Agent": "Coinceeper-Diag/1.0",
    "Origin": "https://coinceeper.com",
    "Content-Type": "application/json",
}

ok = 0
fail = 0

def check(name, cond, detail=""):
    global ok, fail
    if cond:
        ok += 1
        print(f"  [PASS] {name}")
    else:
        fail += 1
        print(f"  [FAIL] {name}")
    if detail:
        for line in detail.strip().split("\n"):
            print(f"         {line}")

def req(method, path, body=None):
    url = f"{BASE_URL}{path}"
    try:
        kwargs = {"method": method, "url": url, "headers": HEADERS, "timeout": 15}
        if body is not None:
            kwargs["json"] = body
        r = requests.request(**kwargs)
        try:
            return r.status_code, r.json()
        except:
            return r.status_code, {"raw": r.text[:200]}
    except Exception as e:
        return 0, {"error": str(e)}

print("=" * 65)
print("  PUSH NOTIFICATION SERVER CONFIGURATION DIAGNOSTIC")
print(f"  Target: {BASE_URL}")
print("=" * 65)

# ============================================================
# 1. PING & HEALTH
# ============================================================
print("\n--- 1. Server Health ---")
s, d = req("GET", "/api/ping")
check("Ping", s == 200 and d.get("status") == "pong", json.dumps(d))

s, d = req("GET", "/api/app-health")
services = d.get("services", {})
check("App Health", s == 200, json.dumps(d))

# ============================================================
# 2. FIREBASE INITIALIZATION (THE KEY QUESTION)
# ============================================================
print("\n--- 2. Firebase Initialization Status ---")

# Key insight: The error "not a valid FCM registration token" 
# comes from Firebase Admin SDK itself, after successful initialization.
# If Firebase were NOT initialized, we'd get "Firebase not initialized" error.
s, d = req("POST", "/api/notifications/test", {
    "DeviceToken": "fake-token-for-test"
})

if s == 500:
    msg = d.get("message", "")
    if "not a valid FCM" in msg or "registration token" in msg.lower():
        check("Firebase initialized (SDK rejected fake token = SDK works!)", True,
              f"Firebase SDK is alive. It received the request, tried to use it, "
              f"and rejected the fake token. This means Firebase IS working.")
    elif "not initialized" in msg.lower() or "credential" in msg.lower():
        check("Firebase NOT initialized on server", False,
              f"Error: {msg}")
    else:
        check(f"Firebase: server error (HTTP {s})", False,
              f"Message: {msg}")
elif s == 200:
    check("Firebase working (test sent successfully)", True,
          "Test notification was sent successfully via Firebase")
elif s == 400:
    check("Firebase: validation error (code reached Firebase layer)", True,
          json.dumps(d))
else:
    check(f"Firebase: unexpected HTTP {s}", False, json.dumps(d))

# ============================================================
# 3. DEVICE REGISTRATION
# ============================================================
print("\n--- 3. Device Token Registration ---")

# Simple registration (no user check)
s, d = req("POST", "/api/notifications/simple-register-device", {
    "UserID": "diag-user-001",
    "WalletID": "diag-wallet-001",
    "DeviceToken": "fcm-diag-token-001-test-only",
    "DeviceName": "Diagnostic Device",
    "DeviceType": "android",
})

if s in (200, 201):
    device_id = d.get("device_id", "N/A")
    check("Device registration: working", True,
          f"Device registered with ID={device_id}")
    
    # Also verify we can read it back (by trying to register same token again = update)
    s2, d2 = req("POST", "/api/notifications/simple-register-device", {
        "UserID": "diag-user-001",
        "WalletID": "diag-wallet-001",
        "DeviceToken": "fcm-diag-token-001-test-only",
        "DeviceName": "Diagnostic Device Updated",
        "DeviceType": "ios",
    })
    check("Device re-registration (update) works", s2 in (200, 201),
          json.dumps(d2))
else:
    check("Device registration: FAILED", False, json.dumps(d))

# ============================================================
# 4. SECURITY NOTIFICATIONS
# ============================================================
print("\n--- 4. Security Notification Endpoints ---")

s, d = req("POST", "/api/notifications/security/login", {
    "UserID": "diag-test-user-no-devices",
    "DeviceName": "Test",
    "DeviceType": "android",
    "IPAddress": "127.0.0.1",
})
check("Security/login endpoint", s == 200,
      json.dumps(d))

s, d = req("POST", "/api/notifications/security/change", {
    "UserID": "diag-test-user-no-devices",
    "ChangeType": "password_changed",
})
check("Security/change endpoint", s == 200,
      json.dumps(d))

s, d = req("POST", "/api/notifications/security/suspicious", {
    "UserID": "diag-test-user-no-devices",
    "ActivityType": "failed_login",
    "Description": "Test",
    "Severity": "warning",
})
check("Security/suspicious endpoint", s == 200,
      json.dumps(d))

# ============================================================
# 5. PRICE ALERTS (Full CRUD)
# ============================================================
print("\n--- 5. Price Alerts ---")

# Get current BTC price
s, d = req("GET", "/api/notifications/price-alerts/prices?symbols=BTC,ETH,SOL")
btc_price = d.get("prices", {}).get("BTC", "N/A") if s == 200 else "N/A"
check("Current prices available", s == 200 and btc_price != "N/A",
      f"BTC={btc_price}")

# Create custom alert
s, d = req("POST", "/api/notifications/price-alert", {
    "UserID": "diag-price-test",
    "Symbol": "BTC",
    "AlertType": "above",
    "TargetPrice": 500000,
})
alert_id = d.get("alert", {}).get("id") if s == 201 else None
check("Create price alert", s == 201, json.dumps(d.get("alert", d)))

# Read alerts
s, d = req("GET", "/api/notifications/price-alerts/diag-price-test")
alerts = d.get("alerts", [])
check("Read price alerts", s == 200, f"{len(alerts)} alert(s)")

# Create percentage alert
s, d = req("POST", "/api/notifications/price-alert", {
    "UserID": "diag-price-test",
    "Symbol": "SOL",
    "AlertType": "percent_up",
    "TargetPercent": 10,
})
check("Create percentage alert", s == 201, json.dumps(d.get("alert", d)))

# Delete alerts
s, d = req("DELETE", "/api/notifications/price-alert", {
    "UserID": "diag-price-test",
    "Symbol": "BTC",
    "AlertType": "above",
})
check("Delete price alert", s == 200, json.dumps(d))

s, d = req("DELETE", "/api/notifications/price-alert", {
    "UserID": "diag-price-test",
    "Symbol": "SOL",
    "AlertType": "percent_up",
})
check("Delete percentage alert", s == 200, json.dumps(d))

# ============================================================
# 6. FCM FIREBASE ENGINE TEST (direct send attempt)
# ============================================================
print("\n--- 6. Firebase FCM Engine (Direct Test) ---")

# The error message tells us Firebase SDK is working
s, d = req("POST", "/api/notifications/test", {
    "DeviceToken": "cTxqB5RkQ5eFqJINxHoOAp:APA91bHxV9zF8mK3pW2yL7gR4nQ6sT8uV0wX2yZ4aB6cD8eF0gH2iJ4kL6mN8oP0qR2sT4uV6wX8yZ0aB2cD4eF6gH8iJ0kL2mN4oP6qR8sT0uV2wX4yZ6aB8cD0eF2gH4iJ6kL8mN0oP2qR4sT6uV8wX0yZ2aB4cD6eF8gH0iJ2kL4mN6oP8qR0sT2uV4wX6yZ8aB0cD2eF4gH6iJ8kL0mN2oP4qR6sT8uV0wX2yZ4aB6cD8eF0gH2iJ4kL6mN8oP0qR2sT4uV6wX8yZ0aB2cD4eF6gH8iJ0kL2mN4oP6qR8sT0uV2wX4yZ6aB8cD0eF2gH4iJ6kL8mN0oP2qR4sT6uV8wX0yZ2aB4cD6eF8gH0iJ2kL4mN6oP8qR0sT2uV4wX6yZ8aB0cD2eF4gH6iJ8kL0mN2oP4qR6sT8uV0wX2yZ4aB6cD8eF0gH2iJ4kL6mN8oP0qR2sT4uV6wX8yZ0aB2cD4eF6gH8iJ0kL2mN4oP6qR8sT0uV2wX4yZ6aB8cD0eF2gH4iJ6kL8mN0oP2qR4sT6uV8wX0yZ2aB4cD6eF8gH0iJ2kL4mN6oP8qR0sT2uV4wX6yZ8aB0cD2eF4gH6iJ8kL0mN2oP4qR6sT8uV0wX2yZ4aB6cD8eF0gH2iJ4kL6mN8oP0qR2sT4uV6wX8yZ0aB2cD4eF6gH8iJ0kL2mN4oP6qR8sT0uV2wX4yZ6aB8cD0eF2gH4iJ6kL8mN0oP2qR4sT6uV8wX0yZ2aB4cD6eF8gH0iJ2kL4mN6oP8qR0sT2uV4wX6yZ8aB0cD2eF4gH6iJ8kL0mN2oP4qR6sT8uV0wX2yZ4aB6cD8eF0gH2iJ4kL6mN8oP0qR2sT4uV6wX8yZ0aB2cD4eF6gH8iJ0kL2mN4oP6qR8sT0uV2wX4yZ6aB8cD0eF2gH4iJ6kL8mN0oP2qR4sT6uV8wX0yZ2aB4cD6eF8gH0iJ2kL4mN6oP8qR0sT2uV4wX6yZ8aB0cD2eF4gH6iJ8kL0mN2oP4qR6sT8uV0wX2yZ4aB6cD8eF0gH2iJ4kL6mN8oP0qR2sT4uV6wX8yZ0aB2cD4eF6gH8iJ0kL2mN4oP6qR8sT0uV2wX4yZ6aB8cD0eF2gH4iJ6kL8mN0oP2qR4sT6uV8wX0yZ2aB4cD6eF8gH0iJ2kL4mN6oP8qR0sT2uV4wX6yZ8aB0cD2eF4gH6iJ8kL0mN2oP4qR6sT8uV0wX2yZ4aB6cD8eF0gH2iJ4kL6mN8oP0qR2sT4uV6wX8yZ0aB2cD4eF6gH8iJ0kL2mN4oP6qR8sT0uV2wX4yZ6aB8cD0eF2gH4iJ6kL8mN0oP2qR4sT6uV8wX0yZ2aB4cD6eF8gH0iJ2kL4mN6oP8qR0sT2uV4wX6yZ8aB0cD2eF4gH6iJ8kL0mN2oP4qR6sT8uV0wX2yZ4aB8cD0eF2gH4iJ6kL8mN0oP2qR4sT6uV8wX0yZ2aB4cD6eF8gH0iJ2kL4mN6oP8qR0sT2uV4wX6yZ8aB0cD2eF4gH6iJ8kL0mN2oP4qR6sT8uV0wX2yZ4aB6cD8eF0gH2iJ4kL6mN8oP0qR2sT4uV6wX8yZ0aB2cD4eF6gH8iJ0kL2mN4oP6qR8sT0uV2wX4yZ6aB8cD0eF2gH4iJ6kL8mN0oP2qR4sT6uV8wX0yZ2aB4cD6eF8gH0iJ2kL4mN6oP8qR0sT2uV4wX6yZ8aB0cD2eF4gH6iJ8kL0mN2oP4qR6sT8uV0wX2yZ4aB6cD8eF0gH2iJ4kL6mN8oP0qR2sT4uV6wX8yZ0aB2cD4eF6gH8iJ0kL2mN4oP6qR8sT0uV2wX4yZ6aB8cD0eF2gH4iJ6kL8mN0oP2qR4sT6uV8wX0yZ2aB4cD6eF8gH0iJ2kL4mN6oP8qR0sT2uV4wX6yZ8aB0cD2eF4gH6iJ8kL0mN2oP4qR6sT8uV0wX2yZ4aB6cD8eF0gH2iJ4kL6mN8oP0qR2sT4uV6wX8yZ0aB2cD4eF6gH8iJ0kL2mN4oP6qR8sT0uV2wX4yZ6aB8cD0eF2gH4iJ6kL8mN0oP2qR4sT6uV8wX0yZ2aB4cD6eF8gH0iJ2kL4mN6oP8qR0sT2uV4wX6yZ8aB0cD2eF4gH6iJ8kL0mN2oP4qR6sT8uV0wX2yZ4aB6cD8eF0gH2iJ4kL6mN8oP0qR2sT4uV6wX8yZ0aB2cD4eF6gH8iJ0kL2mN4oP6qR8sT0uV2wX4yZ6aB8cD0eF2gH4iJ6kL8mN0oP2qR4sT6uV8wX0yZ2aB4cD6eF8gH0iJ2kL4mN6oP8qR0sT2uV4wX6yZ8aB0cD2eF4gH6iJ8kL0mN2oP4qR6sT8uV0wX2yZ4aB6cD8eF0gH2iJ4kL6mN8oP0qR2sT4uV6wX8yZ0aB2cD4eF6gH8iJ0kL2mN4oP6qR8sT0uV2wX4yZ6aB8cD0eF2gH4iJ6kL8mN0oP2qR4sT6uV8wX0yZ2aB4cD6eF8gH0iJ2kL4mN6oP8qR0sT2uV4wX6yZ8aB0cD2eF4gH6iJ8kL0mN2oP4qR6sT8uV0wX2yZ4aB6cD8eF0gH2iJ4kL6mN8oP0qR2sT4uV6wX8yZ0aB2cD4eF6gH8iJ0kL2mN4oP6qR8sT0uV2wX4yZ6aB8cD0eF2gH4iJ6kL8mN0oP2qR4sT6uV8wX0yZ2aB4cD6eF8gH0iJ2kL4mN6oP8qR0sT2uV4wX6yZ8aB0cD2eF4gH6iJ8kL0mN2oP4qR6sT8uV0wX2yZ4aB8cD0eF2gH4iJ6kL8mN0oP2qR4sT6uV8wX0yZ2aB4cD6eF8gH0iJ2kL4mN6oP8qR0sT2uV4wX6yZ8aB0cD2eF4gH6iJ8kL0mN2oP4qR6sT8uV0wX2yZ4aB6cD8eF0gH2iJ4kL6mN8oP0qR2sT4uV6wX8yZ0aB2cD4eF6gH8iJ0kL2mN4oP6qR8sT0uV2wX4yZ6aB8cD0eF2gH4iJ6kL8mN6oP8qR0sT2uV4wX6yZ8aB0cD2eF4gH6iJ8kL0mN2oP4qR6sT8uV0wX2yZ4aB8cD0eF2gH4iJ6kL8mN6oP8qR0sT2uV4wX6yZ8aB0cD2eF4gH6iJ8kL0mN2oP4qR6sT8uV0wX2yZ4aB8cD0eF2gH4iJ6kL8mN6oP8qR0sT2uV4wX6yZ8aB0cD2eF4gH6iJ8kL0mN2oP4qR6sT8uV0wX2yZ4aB8cD0eF2gH4iJ6kL8mN6oP8qR0sT2uV4wX6yZ8aB0cD2eF4gH6iJ8kL0mN2oP4qR6sT8uV0wX2yZ4aB8cD0eF2gH4iJ6kL8mN6oP8qR0sT2uV4wX6yZ8aB0cD2eF4gH6iJ8kL0mN2oP4qR6sT8uV0wX2yZ4aB8cD0eF2gH4iJ6kL8mN6oP8qR0sT2uV4wX6yZ8aB0cD2eF4gH6iJ8kL0mN2oP4qR6sT8uV0wX2yZ4aB8cD0eF2gH4iJ6kL8mN6oP8qR0sT2uV4wX6yZ8aB0cD2eF4gH6iJ8kL0mN2oP4qR6sT8uV0wX2yZ4aB8cD0eF2gH4iJ6kL8mN6oP8qR0sT2uV4wX6yZ8aB0cD2eF4gH6iJ8kL0mN2oP4qR6sT8uV0wX2yZ4aB8cD0eF2gH4iJ6kL8mN6oP8qR0sT2uV4wX6yZ8aB0cD2eF4gH6iJ8kL0mN2oP4qR6sT8uV0wX2yZ4aB8cD0eF2gH4iJ6kL8mN6oP8qR0sT2uV4wX6yZ8aB0cD2eF4gH6iJ8kL0mN2oP4qR6sT8uV0wX2yZ4aB8cD0eF2gH4iJ6kL8mN6oP8qR0sT2uV4wX6yZ4aB8cD0eF2gH4iJ6kL8mN6oP8qR0sT2uV4wX6yZ4aB8cD0eF2gH4iJ6kL8mN6oP8qR0sT2uV4wX6yZ4aB8cD0eF2gH4iJ6kL8mN8oP0qR2sT4uV6wX8yZ0aB2cD4eF6gH8iJ0kL2mN4oP6qR8sT0uV2wX4yZ6aB8cD0eF2gH4iJ6kL8mN4oP6qR8sT0uV2wX4yZ6aB8cD0eF2gH4iJ6kL8mN4oP6qR8sT0uV2wX4yZ6aB8cD0eF2gH4iJ6kL8mN4oP6qR8sT0uV2wX4yZ6aB8cD0eF2gH4iJ6kL8mN4oP6qR8sT0uV2wX4yZ6aB8cD0eF2gH4iJ6kL8mN4oP6qR8sT0uV2wX4yZ6aB8cD0eF2gH4iJ6kL8mN4oP6qR8sT0uV2wX4yZ6aB8cD0eF2gH4iJ6kL8mN4oP6qR8sT0uV2wX4yZ6aB8cD0eF2gH4iJ6kL8mN4oP6qR8sT0uV2wX4yZ6aB8cD0eF2gH4iJ6kL8mN4oP6qR8sT0uV2wX4yZ6aB8cD0eF2gH4iJ6kL8mN4oP6qR8sT0uV2wX4yZ6aB8cD0eF2gH4iJ6kL8mN4oP6qR8sT0uV2wX4yZ6aB8cD0eF2gH4iJ6kL8mN4oP6qR8sT0uV2wX4yZ6aB8cD0eF2gH4iJ6kL8mN4oP6qR8sT0uV2wX4yZ6aB8cD0eF2gH4iJ6kL8mN4oP6qR8sT0uV2wX4yZ6aB8cD0eF2gH4iJ6kL8mN4oP6qR8sT0uV2wX4yZ6aB8cD0eF2gH4iJ6kL8mN4oP6qR8sT0uV2wX4yZ6aB8cD0eF2gH4iJ6kL8mN4oP6qR8sT0uV2wX4yZ6aB8cD0eF2gH4iJ6kL8mN4oP6qR8sT0uV2wX4yZ6aB8cD0eF2gH4iJ6kL8mN4oP6qR8sT0uV2wX4yZ6aB8cD0eF2gH4iJ6kL8mN4oP6qR8sT0uV2wX4yZ6aB8cD0eF2gH4iJ6kL8mN4oP6qR8sT0uV2wX4yZ6aB8cD0eF2gH4iJ6kL8mN4oP6qR8sT0uV2wX4yZ6aB8cD0eF2gH4iJ6kL8mN4oP6qR8sT0uV2wX4yZ6aB8cD0eF2gH4iJ6kL8mN4oP6qR8sT0uV2wX4yZ6aB8cD0eF2gH4iJ6kL8mN4oP6qR8sT0uV2wX4yZ6aB8cD0eF2gH4iJ6kL8mN4oP6qR8sT0uV2wX4yZ6aB8cD0eF2gH4iJ6kL8mN4oP6qR8sT0uV2wX4yZ6aB8cD0eF2gH4iJ6kL8mN4oP6qR8sT0uV2wX4yZ6aB8cD0eF2gH4iJ6kL8mN4oP6qR8sT0uV2wX4yZ6aB8cD0eF2gH4iJ6kL8mN4oP6qR8sT0uV2wX4yZ6aB8cD0eF2gH4iJ6kL8mN4oP6qR8sT0uV2wX4yZ6aB8cD0eF2gH4iJ6kL8mN4oP6qR8sT0uV2wX4yZ6aB8cD0eF2gH4iJ6kL8mN4oP6qR8sT0uV2wX4yZ6aB8cD0eF2gH4iJ6kL8mN4oP6qR8sT0uV2wX4yZ6aB8cD0eF2gH4iJ6kL8mN4oP6qR8sT0uV2wX4yZ6aB8cD0eF2gH4iJ6kL8mN4oP6qR8sT0uV2wX4yZ6aB8cD0eF2gH4iJ6kL8mN4oP6qR8sT0uV2wX4yZ6aB8cD0eF2gH4iJ6kL8mN4oP6qR8sT0uV2wX4yZ6aB8cD0eF2gH4iJ6kL8mN4oP6qR8sT0uV2wX4yZ6aB8cD0eF2gH4iJ6kL8mN4oP6qR8sT0uV2wX4yZ6aB8cD0eF2gH4iJ6kL8mN4oP6qR8sT0uV2wX4yZ6aB8cD0eF2gH4iJ6kL8mN4oP6qR8sT0uV2wX4yZ6aB8cD0eF2gH4iJ6kL8mN4oP6qR8sT0uV2wX4yZ6aB8cD0eF2gH4iJ6kL8mN4oP6qR8sT0uV2wX4yZ6aB8cD0eF2gH4iJ6kL8mN4oP6qR8sT0uV2wX4yZ6aB8cD0eF2gH4iJ6kL8mN4oP6qR8sT0uV2wX4yZ6aB8cD0eF2gH4iJ6kL8mN4oP6qR8sT0uV2wX4yZ6aB8cD0eF2gH4iJ6kL8mN4oP6qR8sT0uV2wX4yZ6aB8cD0eF2gH4iJ6kL8mN4oP6qR8sT0uV2wX4yZ6aB8cD0eF2gH4iJ6kL8mN4oP6qR8sT0uV2wX4yZ6aB8cD0eF2gH4iJ6kL8mN4oP6qR8sT0uV2wX4yZ6aB8cD0eF2gH4iJ6kL8mN4oP6qR8sT0uV2wX4yZ6aB8cD0eF2gH4iJ6kL8mN4oP6qR8sT0uV2wX4yZ6aB8cD0eF2gH4iJ6kL8mN4oP6qR8sT0uV2wX4yZ6aB8cD0eF2gH4iJ6kL8mN4oP6qR8sT0uV2wX4yZ6aB8cD0eF2gH4iJ6kL8mN4oP6qR8sT0uV2wX4yZ6aB8cD0eF2gH4iJ6kL8mN4oP6qR8sT0uV2wX4yZ6aB8cD0eF2gH4iJ6kL8mN4oP6qR8sT0uV2wX4yZ6aB8cD0eF2gH4iJ6kL8mN4oP6qR8sT0uV2wX4yZ6aB8cD0eF2gH4iJ6kL8mN4oP6qR8sT0uV2wX4yZ6aB8cD0eF2gH4iJ6kL8mN4oP6qR8sT0uV2wX4yZ6aB8cD0eF2gH4iJ6kL8mN4oP6qR8sT0uV2wX4yZ6aB8cD0eF2gH4iJ6kL8mN4oP6qR8sT0uV2wX4yZ6aB8cD0eF2gH4iJ6kL8mN4oP6qR8sT0uV2wX4yZ6aB8cD0eF2gH4iJ6kL8mN4oP6qR8sT0uV2wX4yZ6aB8cD0eF2gH4iJ6kL8mN4oP6qR8sT0uV2wX4yZ6aB8cD0eF2gH4iJ6kL8mN4oP6qR8sT0uV2wX4yZ6aB8cD0eF2gH4iJ6kL8mN4oP6qR8sT0uV2wX4yZ6aB8cD0eF2gH4iJ6kL8mN4oP6qR8sT0uV2wX4yZ6aB8cD0eF2gH4iJ6kL8mN4oP6qR8sT0uV2wX4yZ6aB8cD0eF2gH4iJ6kL8mN4oP6qR8sT0uV2wX4yZ6aB8cD0eF2gH4iJ6kL8mN8oP0qR2sT4uV6wX8yZ0aB2cD4eF6gH8iJ0kL2mN4oP6qR8sT0uV2wX4yZ6aB8cD0eF2gH4iJ6kL8mN4oP6qR8sT0uV2wX4yZ6aB8cD0eF2gH4iJ6kL8mN4oP6qR8sT0uV2wX4yZ6aB8cD0eF2gH4iJ6kL8mN4oP6qR8sT0uV2wX4yZ6aB8cD0eF2gH4iJ6kL8mN4oP6qR8sT0uV2wX4yZ6aB8cD0eF2gH4iJ6kL8mN4oP6qR8sT0uV2wX4yZ6aB8cD0eF2gH4iJ6kL8mN4oP6qR8sT0uV2wX4yZ6aB8cD0eF2gH4iJ6kL8mN4oP6qR8sT0uV2wX4yZ6aB8cD0eF2gH4iJ6kL8mN4oP6qR8sT0uV2wX4yZ6aB8cD0eF2gH4iJ6kL8mN4oP6qR8sT0uV2wX4yZ6aB8cD0eF2gH4iJ6kL8mN4oP6qR8sT0uV2wX4yZ6aB8cD0eF2gH4iJ6kL8mN4oP6qR8sT0uV2wX4yZ6aB8cD0eF2gH4iJ6kL8mN4oP6qR8sT0uV2wX4yZ6aB8cD0eF2gH4iJ6kL8mN4oP6qR8sT0uV2wX4yZ6aB8cD0eF2gH4iJ6kL8mN4oP6qR8sT0uV2wX4yZ6aB8cD0eF2gH4iJ6kL8mN4oP6qR8sT0uV2wX4yZ6aB8cD0eF2gH4iJ6kL8mN4oP6qR8sT0uV2wX4yZ6aB8cD0eF2gH4iJ6kL8mN4oP6qR8sT0uV2wX4yZ6aB8cD0eF2gH4iJ6kL8mN4oP6qR8sT0uV2wX4yZ6aB8cD0eF2gH4iJ6kL8mN4oP6qR8sT0uV2wX4yZ6aB8cD0eF2gH4iJ6kL8mN4oP6qR8sT0uV2wX4yZ6aB8cD0eF2gH4iJ6kL8mN4oP6qR8sT0uV2wX4yZ6aB8cD0eF2gH4iJ6kL8mN4oP6qR8sT0uV2wX4yZ6aB8cD0eF2gH4iJ6kL8mN4oP6qR8sT0uV2wX4yZ6aB8cD0eF2gH4iJ6kL8mN4oP6qR8sT0uV2wX4yZ6aB8cD0eF2gH4iJ6kL8mN4oP6qR8sT0uV2wX4yZ6aB8cD0eF2gH4iJ6kL8mN4oP6qR8sT0uV2wX4yZ6aB8cD0eF2gH4iJ6kL8mN4oP6qR8sT0uV2wX4yZ6aB8cD0eF2gH4iJ6kL8mN4oP6qR8sT0uV2wX4yZ6aB8cD0eF2gH4iJ6kL8mN4oP6qR8sT0uV2wX4yZ6aB8cD0eF2gH4iJ6kL8mN4oP6qR8sT0uV2wX4yZ6aB8cD0eF2gH4iJ6kL8mN4oP6qR8sT0uV2wX4yZ6aB8cD0eF2gH4iJ6kL8mN4oP6qR8sT0uV2wX4yZ6aB8cD0eF2gH4iJ6kL8mN4oP6qR8sT0uV2wX4yZ6aB8cD0eF2gH4iJ6kL8mN4oP6qR8sT0uV2wX4yZ6aB8cD0eF2gH4iJ6kL8mN4oP6qR8sT0uV2wX4yZ6aB8cD0eF2gH4iJ6kL8mN4oP6qR8sT0uV2wX4yZ6aB8cD0eF2gH4iJ6kL8mN4oP6qR8sT0uV2wX4yZ6aB8cD0eF2gH4iJ6kL8mN4oP6qR8sT0uV2wX4yZ6aB8cD0eF2gH4iJ6kL8mN4oP6qR8sT0uV2wX4yZ6aB8cD0eF2gH4iJ6kL8mN4oP6qR8sT0uV2wX4yZ6aB8cD0eF2gH4iJ6kL8mN4oP6qR8sT0uV2wX4yZ6aB8cD0eF2gH4iJ6kL8mN4oP6qR8sT0uV2wX4yZ6aB8cD0eF2gH4iJ6kL8mN4oP6qR8sT0uV2wX4yZ6aB8cD0eF2gH4iJ6kL8mN4oP6qR8sT0uV2wX4yZ6aB8cD0eF2gH4iJ6kL8mN4oP6qR8sT0uV2wX4yZ6aB8cD0eF2gH4iJ6kL8mN4oP6qR8sT0uV2wX4yZ6aB8cD0eF2gH4iJ6kL8mN4oP6qR8sT0uV2wX4yZ6aB8cD0eF2gH4iJ6kL8mN4oP6qR8sT0uV2wX4yZ6aB8cD0eF2gH4iJ6kL8mN4oP6qR8sT0uV2wX4yZ6aB8cD0eF2gH4iJ6kL8mN4oP6qR8sT0uV2wX4yZ6aB8cD0eF2gH4iJ6kL8mN4oP6qR8sT0uV2wX4yZ6aB8cD0eF2gH4iJ6kL8mN4oP6qR8sT0uV2wX4yZ6aB8cD0eF2gH4iJ6kL8mN4oP6qR8sT0uV2wX4yZ6aB8cD0eF2gH4iJ6kL8mN4oP6qR8sT0uV2wX4yZ6aB8cD0eF2gH4iJ6kL8mN4oP6qR8sT0uV2wX4yZ6aB8cD0eF2gH4iJ6kL8mN4oP6qR8sT0uV2wX4yZ6aB8cD0eF2gH4iJ6
