import requests
import json

# تست API v3 جدید - مستقیم از Trongrid Proxy
url = "https://coinceeper.com/api/v2/explorer/tx-history"
body = {
    "chain": "tron",
    "address": "TNidf9kL1sARwfhdrpiJT9yjsEcdteBnPV",
    "limit": 10
}

print(f"Calling {url}...")
resp = requests.post(url, json=body, timeout=30)
print(f"Status: {resp.status_code}")
data = resp.json()
print(json.dumps(data, indent=2, ensure_ascii=False))

print("\n\n=== Searching for transaction 01987edc... ===")
if data.get("success") and data.get("transactions"):
    found = False
    for tx in data["transactions"]:
        if "01987edc" in str(tx.get("txID", "")):
            found = True
            print(f"✅ FOUND! Transaction: {json.dumps(tx, indent=2, ensure_ascii=False)}")
    if not found:
        print("❌ Transaction NOT FOUND in API response")
        # Show all txIDs
        for tx in data["transactions"]:
            print(f"  - txID: {tx.get('txID', 'N/A')}")
else:
    print(f"Response structure: {list(data.keys()) if isinstance(data, dict) else 'N/A'}")
    print(f"Error: {data.get('error', 'unknown')}")