"""Test the FCM push integration with block scanner."""
import sys
import os

sys.path.insert(0, '/opt/coinceeper/CC')
sys.path.insert(0, '/opt/coinceeper')
os.chdir('/opt/coinceeper/CC')

print("=== Testing FCM Push from Block Scanner ===")

# Test 1: Import the module
try:
    from services.cache_proxy.fcm_push import notify_new_transaction, _format_amount, _lazy_init
    print("✅ Module imported successfully")
except Exception as e:
    print(f"❌ Import failed: {e}")
    sys.exit(1)

# Test 2: Test _format_amount
print("\n=== Testing _format_amount ===")
tests = [
    ("1000000000000000000", "Ethereum", "value_wei", "1.0"),
    ("500000000000000000", "Ethereum", "value_wei", "0.5"),
    ("1000000", "Tron", "value_sun", "1.0"),
    ("100000000", "Solana", "value_lamports", "0.1"),
    ("100000000", "Bitcoin", "value_sat", "1.0"),
]
for val, chain, field, expected in tests:
    result = _format_amount(val, chain, field)
    status = "✅" if result == expected else "❌"
    print(f"  {status} {val} ({chain}) → {result} (expected: {expected})")

# Test 3: Test notify_new_transaction with a dummy tx
print("\n=== Testing lazy_init ===")
init_ok = _lazy_init()
print(f"  Lazy init: {'✅' if init_ok else '❌'}")

# Test 4: Send a test notification via the new pipeline
print("\n=== Sending test FCM push ===")
test_token = 'f0lh9BMOQgaymAEk8DGsGP:APA91bGhOH-L-DHF_fYoXe7oPX089jBKXdf3VKGxXp__sj8wu_bMZVY8QCtcexC_apzLsZdCmlROeWMEre5nTKo-4tL9GBryP6-oyXoAZs0uHbfGW0ZdG6M'

from config.firebase import send_notification
result = send_notification(
    token=test_token,
    title="🔔 Scanner Push Test",
    body="This is a test from the Block Scanner FCM integration",
    data={
        "type": "test",
        "direction": "inbound",
        "amount": "0.001",
        "symbol": "ETH",
        "blockchain": "Ethereum",
        "timestamp": "2026-06-02",
    },
    priority="high",
)
print(f"  Push result: {'✅' if result else '❌'}")

print("\n=== All tests complete ===")
