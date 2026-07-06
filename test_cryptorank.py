"""Test cryptorank API authentication methods."""
import requests, json

API_KEY = "2892d9ce696f7ea7eaad53ec47c3aeee0c6dc30d7aceb569ca1468d593d1"
BASE = "https://api.cryptorank.io/v3"

print("=" * 60)
print("CryptoRank API Debug")
print("=" * 60)

# Test 1: X-Api-Key header (current implementation)
print("\nTest 1: X-Api-Key header -> /v3/drophunting/list")
headers = {"Accept": "application/json", "X-Api-Key": API_KEY}
try:
    r = requests.get(f"{BASE}/drophunting/list", headers=headers, timeout=15)
    print(f"  Status: {r.status_code}")
    print(f"  Headers: {dict(r.headers)}")
    if r.status_code == 200:
        data = r.json()
        print(f"  Response type: {type(data).__name__}")
        if isinstance(data, dict):
            print(f"  Keys: {list(data.keys())}")
            for k, v in data.items():
                if isinstance(v, list):
                    print(f"    {k}: list[{len(v)}]")
                    if len(v) > 0:
                        print(f"    First item keys: {list(v[0].keys()) if isinstance(v[0], dict) else type(v[0])}")
                else:
                    print(f"    {k}: {type(v).__name__} = {str(v)[:100]}")
        elif isinstance(data, list):
            print(f"  List length: {len(data)}")
    else:
        print(f"  Body: {r.text[:500]}")
except Exception as e:
    print(f"  ERROR: {e}")

# Test 2: api_key query param
print("\nTest 2: api_key query param -> /v3/drophunting/list")
try:
    r = requests.get(f"{BASE}/drophunting/list?api_key={API_KEY}", timeout=15)
    print(f"  Status: {r.status_code}")
    if r.status_code == 200:
        data = r.json()
        print(f"  Response type: {type(data).__name__}")
        if isinstance(data, dict):
            print(f"  Keys: {list(data.keys())}")
            for k, v in data.items():
                if isinstance(v, list):
                    print(f"    {k}: list[{len(v)}]")
                else:
                    print(f"    {k}: {type(v).__name__} = {str(v)[:100]}")
        elif isinstance(data, list):
            print(f"  List length: {len(data)}")
    else:
        print(f"  Body: {r.text[:500]}")
except Exception as e:
    print(f"  ERROR: {e}")

# Test 3: Try /v3/drophunting/map
print("\nTest 3: X-Api-Key header -> /v3/drophunting/map (detailed)")
try:
    r = requests.get(f"{BASE}/drophunting/map", headers=headers, timeout=15)
    print(f"  Status: {r.status_code}")
    if r.status_code == 200:
        data = r.json()
        print(f"  Response type: {type(data).__name__}")
        if isinstance(data, dict):
            print(f"  Top keys: {list(data.keys())}")
            items = data.get("data", [])
            print(f"  data items: {len(items)}")
            if len(items) > 0:
                first = items[0]
                print(f"  First item type: {type(first).__name__}")
                if isinstance(first, dict):
                    print(f"  First item keys: {list(first.keys())[:20]}")
                    print(f"  First item (truncated): {json.dumps(first, indent=2)[:500]}")
            if len(items) > 1:
                second = items[1]
                if isinstance(second, dict):
                    print(f"  Second item keys: {list(second.keys())[:20]}")
    else:
        print(f"  Body: {r.text[:300]}")
except Exception as e:
    print(f"  ERROR: {e}")

# Test 5: Try /v3/drophunting/{id} with X-Api-Key header
print("\nTest 5: X-Api-Key header -> /v3/drophunting/1")
try:
    r = requests.get(f"{BASE}/drophunting/1", headers=headers, timeout=15)
    print(f"  Status: {r.status_code}")
    if r.status_code == 200:
        data = r.json()
        print(f"  Response type: {type(data).__name__}")
        if isinstance(data, dict):
            print(f"  Keys: {list(data.keys())}")
    else:
        print(f"  Body: {r.text[:300]}")
except Exception as e:
    print(f"  ERROR: {e}")

# Test 6: Try /v3/drophunting/{id}/tasks with X-Api-Key header
print("\nTest 6: X-Api-Key header -> /v3/drophunting/1/tasks")
try:
    r = requests.get(f"{BASE}/drophunting/1/tasks", headers=headers, timeout=15)
    print(f"  Status: {r.status_code}")
    if r.status_code == 200:
        data = r.json()
        print(f"  Response type: {type(data).__name__}")
        if isinstance(data, dict):
            print(f"  Keys: {list(data.keys())}")
    else:
        print(f"  Body: {r.text[:300]}")
except Exception as e:
    print(f"  ERROR: {e}")

print("\nDone.")
