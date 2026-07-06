"""Test register-device endpoint."""
import requests, json

base = "https://coinceeper.com"

payload = {
    "UserID": "test-user-001",
    "WalletID": "test-wallet-001",
    "DeviceToken": "test-device-token-abc12345",
    "DeviceName": "Test Device",
    "DeviceType": "android"
}

print("--- Register Device ---")
try:
    r = requests.post(f"{base}/api/notifications/register-device",
                      json=payload, timeout=15)
    print(f"Status: {r.status_code}")
    print(f"Response: {json.dumps(r.json(), indent=2)}")
except Exception as e:
    print(f"ERROR: {e}")

print("")
print("--- Airdrops (verify other endpoints still work) ---")
try:
    r = requests.get(f"{base}/api/v2/airdrops?per_page=2", timeout=15)
    print(f"Status: {r.status_code}")
    d = r.json()
    print(f"success={d.get('success')} total={d.get('total')} status={d.get('cache_status')}")
except Exception as e:
    print(f"ERROR: {e}")
