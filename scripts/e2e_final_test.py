#!/usr/bin/env python3
"""Final E2E Test: Real Price Alert -> Push Notification (Frontend Fixed)"""
import requests, json, uuid, sys

BASE = 'https://coinceeper.com'
HDRS = {
    'User-Agent': 'E2ETest/1.0',
    'Origin': 'https://coinceeper.com',
    'Content-Type': 'application/json',
}

DEVICE_ID = str(uuid.uuid4())
FCM_TOKEN = 'eg1NQT0jQFWisOUnba4BeK:APA91bHH-hBBYTzMG6G8DL_mpjsy93Ige_3dMMIQr10KKrqsGSGGnu9-iVRlTwTUJUXf15oCK-ZocElaUJmdpPE5ZVsTKVej94P8Hp6WneNjIkjI6yQAMEs'

print('='*60)
print('FINAL E2E: Real Price Alert w/ Fixed Frontend')
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

# Step 1: Register
print('\n[1/4] Registering device...')
s, d = call("POST", "/api/notifications/simple-register-device", {
    "DeviceID": DEVICE_ID, "DeviceToken": FCM_TOKEN,
    "DeviceName": "Pixel 7 Pro", "DeviceType": "android",
})
print(f'  {"[OK]" if d.get("success") else "[FAIL]"} Device registered')

# Step 2: Create alerts that WILL trigger
print('\n[2/4] Creating price alerts...')
alerts = [("BTC", 200000, "below"), ("ETH", 10000, "below")]
for sym, target, atype in alerts:
    s, d = call("POST", "/api/notifications/price-alert", {
        "DeviceID": DEVICE_ID, "Symbol": sym,
        "AlertType": atype, "TargetPrice": target,
    })
    aid = d.get("alert", {}).get("id", "?")
    print(f'  {"[OK]" if s == 201 else "[FAIL]"} {sym}: alert_id={aid}')

# Step 3: Verify
print('\n[3/4] Verifying alerts...')
s, d = call("GET", f"/api/notifications/price-alerts/{DEVICE_ID}")
print(f'  Active alerts: {len(d.get("alerts", []))}')

print('\n[4/4] Ready! Trigger the price checker on server...')
print(f'\nDeviceID: {DEVICE_ID}')
