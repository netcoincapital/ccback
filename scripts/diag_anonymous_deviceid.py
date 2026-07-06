#!/usr/bin/env python3
"""
Anonymous DeviceID Flow Diagnostic
=====================================
تست اندپوینت‌های جدید که از DeviceID ناشناس پشتیبانی می‌کنند.
"""
import sys, os, json, requests, uuid

BASE = "https://coinceeper.com"
HDRS = {
    "User-Agent": "Diag/1.0",
    "Origin": "https://coinceeper.com",
    "Content-Type": "application/json",
}

ok = 0
fail = 0

def p(name, cond, detail=""):
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
    try:
        kwargs = {"method": method, "url": f"{BASE}{path}", "headers": HDRS, "timeout": 15}
        if body is not None:
            kwargs["json"] = body
        r = requests.request(**kwargs)
        try:
            return r.status_code, r.json()
        except:
            return r.status_code, {"text": r.text[:300]}
    except Exception as e:
        return 0, {"error": str(e)}

DEVICE_ID = str(uuid.uuid4())  # یک UUID ناشناس جدید

print("=" * 65)
print("  ANONYMOUS DEVICEID FLOW - SERVER TEST")
print(f"  Target: {BASE}")
print(f"  Anonymous DeviceID: {DEVICE_ID}")
print("=" * 65)

# ========================================================================
# 1. Firebase (same test)
# ========================================================================
print("\n--- 1. Firebase Initialization (baseline) ---")
s, d = req("POST", "/api/notifications/test", {"DeviceToken": "test-invalid"})
msg = str(d.get("message", ""))
if s == 500 and "registration token is not a valid FCM" in msg:
    p("Firebase SDK is ACTIVE", True, "Firebase correctly initialized")
else:
    p("Firebase SDK status", False, msg)

# ========================================================================
# 2. Anonymous Device Registration (new flow)
# ========================================================================
print("\n--- 2. Anonymous Device Registration (DeviceID only) ---")
s, d = req("POST", "/api/notifications/simple-register-device", {
    "DeviceID": DEVICE_ID,
    "DeviceToken": "fcm:diag-" + DEVICE_ID[:8],
    "DeviceName": "Diag Test Device",
    "DeviceType": "android",
})
p("Register device with DeviceID (no UserID/WalletID)",
  s in (200, 201) and d.get("success") == True,
  f"Response: device_id={d.get('device_id', '?')}")

# ========================================================================
# 3. Anonymous Device Registration - reject missing DeviceID
# ========================================================================
print("\n--- 3. Invalid Registration (rejection check) ---")
s, d = req("POST", "/api/notifications/simple-register-device", {
    "DeviceToken": "fcm:no-id"
})
p("Reject request without DeviceID or UserID+WalletID",
  s == 400,
  json.dumps(d))

# ========================================================================
# 4. Create Price Alert with DeviceID (new flow)
# ========================================================================
print("\n--- 4. Price Alert with DeviceID ---")
s, d = req("POST", "/api/notifications/price-alert", {
    "DeviceID": DEVICE_ID,
    "Symbol": "BTC",
    "AlertType": "above",
    "TargetPrice": 999999,
})
aid = d.get("alert", {}).get("id") if s == 201 else None
p("Create price alert with DeviceID",
  s == 201 and aid is not None,
  f"Alert ID={aid}, Response: {json.dumps(d, indent=2)[:300]}")

# ========================================================================
# 5. Get Price Alerts by DeviceID
# ========================================================================
print("\n--- 5. Get Alerts by DeviceID ---")
s, d = req("GET", f"/api/notifications/price-alerts/{DEVICE_ID}")
p("Get alerts via DeviceID",
  s == 200,
  f"{len(d.get('alerts',[]))} alert(s) found for DeviceID")

# ========================================================================
# 6. Create Percentage Alert with DeviceID
# ========================================================================
print("\n--- 6. Percentage Alert with DeviceID ---")
s, d = req("POST", "/api/notifications/price-alert", {
    "DeviceID": DEVICE_ID,
    "Symbol": "SOL",
    "AlertType": "percent_up",
    "TargetPercent": 15,
})
p("Create percent alert with DeviceID",
  s == 201,
  json.dumps(d.get("alert", {}))[:200])

# ========================================================================
# 7. Delete Price Alert by DeviceID
# ========================================================================
print("\n--- 7. Delete Alert by DeviceID ---")
s, d = req("DELETE", "/api/notifications/price-alert", {
    "DeviceID": DEVICE_ID,
    "Symbol": "BTC",
    "AlertType": "above",
})
p("Delete alert via DeviceID",
  s == 200,
  json.dumps(d))

s, d = req("DELETE", "/api/notifications/price-alert", {
    "DeviceID": DEVICE_ID,
    "Symbol": "SOL",
    "AlertType": "percent_up",
})

# ========================================================================
# 8. Verify old UserID+WalletID flow still works (backward compat)
# ========================================================================
print("\n--- 8. Backward Compatibility (UserID+WalletID still works) ---")
s, d = req("POST", "/api/notifications/price-alert", {
    "UserID": "compat-test-999",
    "Symbol": "ETH",
    "AlertType": "above",
    "TargetPrice": 99999,
})
p("Create price alert with UserID (legacy)",
  s == 201,
  json.dumps(d.get("alert", {}))[:200])

s, d = req("DELETE", "/api/notifications/price-alert", {
    "UserID": "compat-test-999",
    "Symbol": "ETH",
    "AlertType": "above",
})

s, d = req("POST", "/api/notifications/simple-register-device", {
    "UserID": "compat-user",
    "WalletID": "compat-wallet",
    "DeviceToken": "fcm:compat-" + str(uuid.uuid4())[:8],
})
p("Register device with UserID+WalletID (legacy)",
  s in (200, 201),
  json.dumps(d)[:200])

# ========================================================================
# SUMMARY
# ========================================================================
print("\n" + "=" * 65)
total = ok + fail
print(f"  Total:    {total}")
print(f"  Passed:   {ok}")
print(f"  Failed:   {fail}")
print()

if fail == 0:
    print("  *** ANONYMOUS DEVICEID FLOW: FULLY FUNCTIONAL ***")
    print()
    print("  - Device Registration via DeviceID: WORKS")
    print("  - Price Alert CRUD via DeviceID:    WORKS")
    print("  - Backward Compat (UserID+WalletID): WORKS")
    print("  - Firebase SDK:                     ACTIVE")
    print()
    print("  Note: The final push notification delivery")
    print("  depends on the scheduler detecting a price")
    print("  trigger. This is tested via the existing")
    print("  token lookup in base.py -> send_push_to_user")
else:
    print(f"  *** {fail} ISSUE(S) DETECTED ***")
print("=" * 65)

sys.exit(0 if fail == 0 else 1)
