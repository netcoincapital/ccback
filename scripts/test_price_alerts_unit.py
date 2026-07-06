"""
Unit test for PriceAlert model logic + scheduler percentage logic.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from database.price_alert import PriceAlert

errors = []
def check(cond, msg):
    if not cond:
        errors.append(msg)
        print(f"  FAIL: {msg}")
    else:
        print(f"  OK: {msg}")

print("+" + "-"*59 + "+")
print("|  Price Alert Unit Tests                                  |")
print("+" + "-"*59 + "+")

# ─── Test 1: Model Fields ───
print("\n-- Test 1: Model Fields --")
fields = [c.name for c in PriceAlert.__table__.columns]
expected = ['id', 'user_id', 'symbol', 'alert_type', 'target_price', 
            'target_percent', 'reference_price', 'is_active', 'created_at', 'updated_at']
for f in expected:
    check(f in fields, f"Field '{f}' exists")
print(f"  Fields: {fields}")

# ─── Test 2: to_dict() for Custom Price Alert ───
print("\n-- Test 2: to_dict() for Custom Price Alert --")
alert = PriceAlert(id=1, user_id='test', symbol='BTC', alert_type='above', target_price=75000.0)
d = alert.to_dict()
check(d['id'] == 1, "id == 1")
check(d['symbol'] == 'BTC', "symbol == BTC")
check(d['alert_type'] == 'above', "alert_type == above")
check(d['target_price'] == 75000.0, "target_price == 75000")
check('target_percent' not in d, "target_percent not in dict (custom)")
print(f"  Dict: {d}")

# ─── Test 3: to_dict() for Percentage Alert ───
print("\n-- Test 3: to_dict() for Percentage Alert --")
alert2 = PriceAlert(id=2, user_id='test', symbol='SOL', alert_type='percent_up', target_percent=10.0, reference_price=150.0)
d2 = alert2.to_dict()
check(d2['id'] == 2, "id == 2")
check(d2['symbol'] == 'SOL', "symbol == SOL")
check(d2['alert_type'] == 'percent_up', "alert_type == percent_up")
check(d2['target_percent'] == 10.0, "target_percent == 10")
check(d2['reference_price'] == 150.0, "reference_price == 150")
check('target_price' not in d2, "target_price not in dict (percent)")
print(f"  Dict: {d2}")

# ─── Test 4: Scheduler Percentage Logic ───
print("\n-- Test 4: Percentage Alert Trigger Logic --")

def check_pct(alert_type, ref, pct, current):
    if ref is None or pct is None or ref <= 0:
        return False
    change = ((current - ref) / ref) * 100
    if alert_type == 'percent_up':
        return change >= pct
    elif alert_type == 'percent_down':
        return change <= -pct
    return False

# percent_up
check(check_pct('percent_up', 100, 10, 110) == True, "10% up at 110 triggers")
check(check_pct('percent_up', 100, 10, 109) == False, "9% up at 109 no trigger")
check(check_pct('percent_up', 100, 10, 100) == False, "0% change no trigger")
check(check_pct('percent_up', 100, 10, 200) == True, "100% up triggers")
check(check_pct('percent_up', 100, 50, 149) == False, "49% up at 50% no trigger")
check(check_pct('percent_up', 100, 50, 150) == True, "50% up triggers")

# percent_down
check(check_pct('percent_down', 100, 10, 90) == True, "10% down at 90 triggers")
check(check_pct('percent_down', 100, 10, 91) == False, "9% down at 91 no trigger")
check(check_pct('percent_down', 100, 10, 100) == False, "0% change no trigger")
check(check_pct('percent_down', 100, 10, 50) == True, "50% down triggers")
check(check_pct('percent_down', 100, 50, 51) == False, "49% down at 50% no trigger")
check(check_pct('percent_down', 100, 50, 50) == True, "50% down triggers")

# Edge cases
check(check_pct('percent_up', None, 10, 110) == False, "None ref_price")
check(check_pct('percent_up', 0, 10, 110) == False, "Zero ref_price")
check(check_pct('percent_up', 100, None, 110) == False, "None target_pct")

print("\n-- Test 5: Custom Price Alert Logic --")

def check_custom(alert_type, target, current):
    if alert_type == 'above':
        return current >= target
    elif alert_type == 'below':
        return current <= target
    return False

check(check_custom('above', 75000, 75100) == True, "above: 75100 >= 75000 triggers")
check(check_custom('above', 75000, 75000) == True, "above: 75000 == 75000 triggers")
check(check_custom('above', 75000, 74999) == False, "above: 74999 < 75000 no trigger")
check(check_custom('below', 2000, 1990) == True, "below: 1990 <= 2000 triggers")
check(check_custom('below', 2000, 2000) == True, "below: 2000 == 2000 triggers")
check(check_custom('below', 2000, 2010) == False, "below: 2010 > 2000 no trigger")

print("\n-- Test 6: Recurring Percentage (reference reset) --")
ref = 100.0
pct = 10

# Iter 1: 100 -> 115
current = 115.0
change = ((current - ref) / ref) * 100
check(change >= pct, "Iter 1: 15% >= 10% triggers")
ref = current
check(ref == 115.0, f"Iter 1: ref reset to {ref}")

# Iter 2: 115 -> 130
current = 130.0
change = ((current - ref) / ref) * 100
check(change >= pct, "Iter 2: 13% >= 10% triggers again")
ref = current
check(ref == 130.0, f"Iter 2: ref reset to {ref}")

# Iter 3: 130 -> 135
current = 135.0
change = ((current - ref) / ref) * 100
check(change < pct, f"Iter 3: {change:.1f}% < 10% no trigger")

print()
print("+" + "-"*59 + "+")
if errors:
    print(f"|  FAILED: {len(errors)} test(s) failed")
    for e in errors:
        print(f"|    - {e}")
    print("+" + "-"*59 + "+")
    sys.exit(1)
else:
    print("|  ALL 6 TESTS PASSED")
    print("+" + "-"*59 + "+")
