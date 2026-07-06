#!/usr/bin/env python3
import urllib.request
import json
import sys
import os

HOST = "http://127.0.0.1:5000"
ENDPOINTS = []

# 1. Test balance/native (POST)
def test_balance():
    url = HOST + "/api/v2/balance/native"
    data = json.dumps({"chain": "ethereum", "address": "0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045"}).encode()
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
    try:
        resp = urllib.request.urlopen(req, timeout=20)
        body = json.loads(resp.read().decode())
        print("OK: balance/native -", resp.status)
        print("  balance:", body.get("balance", "?"))
        return True
    except urllib.request.HTTPError as e:
        body = json.loads(e.read().decode())
        print("FAIL: balance/native -", e.code, body.get("error", ""))
        return False
    except Exception as e:
        print("FAIL: balance/native -", str(e))
        return False

# 2. Test tx-history (POST)
def test_tx_history():
    url = HOST + "/api/v2/explorer/tx-history"
    data = json.dumps({"chain": "bitcoin", "address": "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa", "limit": 3}).encode()
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
    try:
        resp = urllib.request.urlopen(req, timeout=30)
        body = json.loads(resp.read().decode())
        print("OK: tx-history -", resp.status)
        print("  tx count:", body.get("count", "?"))
        return True
    except urllib.request.HTTPError as e:
        body = json.loads(e.read().decode())
        print("FAIL: tx-history -", e.code, body.get("error", ""))
        return False
    except Exception as e:
        print("FAIL: tx-history -", str(e))
        return False

# 3. Test proxy-health (GET)
def test_proxy_health():
    try:
        resp = urllib.request.urlopen(HOST + "/api/v2/proxy-health", timeout=10)
        body = json.loads(resp.read().decode())
        print("OK: proxy-health -", resp.status)
        print("  status:", body.get("status", "?"))
        print("  providers:", list(body.get("providers", {}).keys()))
        print("  key_pools:", list(body.get("modules", {}).get("key_pools", {}).keys()))
        return True
    except Exception as e:
        print("FAIL: proxy-health -", str(e))
        return False

# 4. Test V2 health (GET)
def test_v2_health():
    try:
        resp = urllib.request.urlopen(HOST + "/api/v2/health", timeout=10)
        body = json.loads(resp.read().decode())
        print("OK: v2/health -", resp.status)
        print("  status:", body.get("status", "?"))
        print("  caches:", list(body.get("caches", {}).keys()))
        return True
    except Exception as e:
        print("FAIL: v2/health -", str(e))
        return False

# 5. Test metrics (GET)
def test_metrics():
    try:
        resp = urllib.request.urlopen(HOST + "/api/v2/metrics", timeout=10)
        body = resp.read().decode()[:200]
        print("OK: metrics -", resp.status)
        print("  preview:", body[:100].replace(chr(10), " "))
        return True
    except Exception as e:
        print("FAIL: metrics -", str(e))
        return False

# 6. Test token-metadata (GET)
def test_token_metadata():
    url = HOST + "/api/v2/token-metadata?chain=ethereum&contract_address=0xdAC17F958D2ee523a2206206994597C13D831ec7"
    try:
        resp = urllib.request.urlopen(url, timeout=15)
        body = json.loads(resp.read().decode())
        print("OK: token-metadata -", resp.status)
        token = body.get("token", {})
        print("  symbol:", token.get("symbol", "?"), "name:", token.get("name", "?"))
        return True
    except urllib.request.HTTPError as e:
        body = json.loads(e.read().decode())
        print("FAIL: token-metadata -", e.code, body.get("error", ""))
        return False
    except Exception as e:
        print("FAIL: token-metadata -", str(e))
        return False


if __name__ == "__main__":
    os.chdir("/opt/coinceeper/CC")
    tests = [
        ("V2 Health", test_v2_health),
        ("V3 Proxy Health", test_proxy_health),
        ("Balance Native (Ethereum)", test_balance),
        ("TX History (Bitcoin)", test_tx_history),
        ("Metrics", test_metrics),
        ("Token Metadata (USDT)", test_token_metadata),
    ]

    passed = 0
    failed = 0
    for name, func in tests:
        print(f"\n{'='*60}")
        print(f"Testing: {name}")
        print(f"{'='*60}")
        if func():
            passed += 1
        else:
            failed += 1

    print(f"\n{'='*60}")
    print(f"RESULTS: {passed} passed, {failed} failed out of {len(tests)}")
    print(f"{'='*60}")
    sys.exit(0 if failed == 0 else 1)
