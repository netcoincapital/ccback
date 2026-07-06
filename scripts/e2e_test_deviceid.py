#!/usr/bin/env python3
"""E2E Test: Anonymous DeviceID -> Real Push Notification"""
import requests, json, uuid, time, sys

BASE = 'https://coinceeper.com'
HDRS = {
    'User-Agent': 'E2ETest/1.0',
    'Origin': 'https://coinceeper.com',
    'Content-Type': 'application/json',
}

DEVICE_ID = str(uuid.uuid4())
FCM_TOKEN = 'eg1NQT0jQFWisOUnba4BeK:APA91bHH-hBBYTzMG6G8DL_mpjsy93Ige_3dMMIQr10KKrqsGSGGnu9-iVRlTwTUJUXf15oCK-ZocElaUJmdpPE5ZVsTKVej94P8Hp6WneNjIkjI6yQAMEs'

print('='*60)
print('E2E TEST: Anonymous DeviceID -> Real Push Notification')
print(f'DeviceID: {DEVICE_ID}')
print('='*60)

def call(method, path, body=None):
    kwargs = {"method": method, "url": f"{BASE}{path}", "headers": HDRS, "timeout": 15}
    if body is not None:
        kwargs["json"] = body
    r = requests.request(**kwargs)
    try:
        return r.status_code, r.json()
    except:
        return r.status_code, {"text": r.text[:300]}

# Step 1: Register device
print('\n[1/4] Registering device with DeviceID...')
s, d = call("POST", "/api/notifications/simple-register-device", {
    "DeviceID": DEVICE_ID, "DeviceToken": FCM_TOKEN,
    "DeviceName": "Mohammad Pixel 7 Pro", "DeviceType": "android",
})
if d.get("success"):
    print(f'  [OK] Device registered')
else:
    print(f'  [FAIL] Status={s}: {d.get("message")}')
    sys.exit(1)

# Step 2: Create price alerts
print('\n[2/4] Creating price alerts (BTC below $200k, ETH below $10k)...')
for sym, target in [("BTC", 200000), ("ETH", 10000)]:
    s, d = call("POST", "/api/notifications/price-alert", {
        "DeviceID": DEVICE_ID, "Symbol": sym,
        "AlertType": "below", "TargetPrice": target,
    })
    if s == 201:
        aid = d.get("alert", {}).get("id", "?")
        print(f'  [OK] {sym}: alert_id={aid}')
    else:
        print(f'  [FAIL] {sym}: {d.get("message")}')

# Step 3: Verify alerts exist
print('\n[3/4] Verifying alerts...')
s, d = call("GET", f"/api/notifications/price-alerts/{DEVICE_ID}")
alerts = d.get("alerts", [])
print(f'  Active alerts: {len(alerts)}')

# Step 4: Trigger via server (SSH needs to run the checker)
print('\n[4/4] Now running scheduler check on server...')
print('  (triggering from separate SSH command)')
