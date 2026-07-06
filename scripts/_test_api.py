"""Run on server: python3 scripts/_test_api.py"""
import sys, os, json
sys.path.insert(0, '/opt/coinceeper/CC')

# Set PYTHONPATH
os.environ['PYTHONPATH'] = '/opt/coinceeper'

import urllib.request

payloads = [
    {"UserID": "final-test", "Symbol": "BTC", "AlertType": "above", "TargetPrice": 100000},
    {"UserID": "final-test", "Symbol": "ETH", "AlertType": "below", "TargetPrice": 1500},
    {"UserID": "final-test", "Symbol": "SOL", "AlertType": "percent_up", "TargetPercent": 10},
    {"UserID": "final-test", "Symbol": "BTC", "AlertType": "percent_down", "TargetPercent": 5},
]

for p in payloads:
    body = json.dumps(p).encode('utf-8')
    req = urllib.request.Request(
        'http://127.0.0.1:5000/api/notifications/price-alert',
        data=body,
        headers={'Content-Type': 'application/json'},
        method='POST',
    )
    try:
        resp = urllib.request.urlopen(req, timeout=15)
        data = json.loads(resp.read().decode('utf-8'))
        print(f'OK [{resp.status}] {p["AlertType"]} {p["Symbol"]}: {data.get("message","")}')
    except urllib.request.HTTPError as e:
        err = json.loads(e.read().decode('utf-8'))
        print(f'ERR [{e.code}] {p["AlertType"]} {p["Symbol"]}: {err.get("message","")}')

# List alerts
req = urllib.request.Request('http://127.0.0.1:5000/api/notifications/price-alerts/final-test')
resp = urllib.request.urlopen(req, timeout=15)
alerts = json.loads(resp.read().decode('utf-8'))
print(f'\nAlerts: {len(alerts.get("alerts",[]))} total')
for a in alerts.get('alerts', []):
    print(f'  - #{a["id"]} {a["symbol"]} {a["alert_type"]}')

# Cleanup
from database import SessionLocal, PriceAlert
session = SessionLocal()
cnt = session.query(PriceAlert).filter(PriceAlert.user_id == 'final-test').delete()
session.commit()
session.close()
print(f'\nCleaned up {cnt} test alerts')
print('ALL DONE')
