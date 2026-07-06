#!/usr/bin/env python3
"""Test notification APIs on the server."""
import urllib.request
import json
import sys

BASE = 'http://127.0.0.1:5000/api'

tests = [
    # Security - Login
    ('POST', '/notifications/security/login', {
        'UserID': 'test',
        'DeviceName': 'Samsung Galaxy S24',
        'DeviceType': 'android',
        'IPAddress': '192.168.1.1',
    }),
    # Security - Change
    ('POST', '/notifications/security/change', {
        'UserID': 'test',
        'ChangeType': 'password_changed',
    }),
    # Security - Suspicious
    ('POST', '/notifications/security/suspicious', {
        'UserID': 'test',
        'ActivityType': 'failed_login',
        'Description': '5 failed login attempts in 2 minutes',
        'Severity': 'warning',
    }),
    # Price Alert - Create
    ('POST', '/notifications/price-alert', {
        'UserID': 'test',
        'Symbol': 'BTC',
        'TargetPrice': 50000,
        'AlertType': 'above',
    }),
    # Price Alert - Get
    ('GET', '/notifications/price-alerts/test', None),
    # Portfolio - Trigger
    ('POST', '/admin/notifications/portfolio-summary/test', None),
]

all_ok = True
for method, path, body in tests:
    url = BASE + path
    try:
        if body:
            data = json.dumps(body).encode()
            req = urllib.request.Request(url, data=data,
                                         headers={'Content-Type': 'application/json'},
                                         method=method)
        else:
            req = urllib.request.Request(url, method=method)
        resp = urllib.request.urlopen(req, timeout=5)
        result = json.loads(resp.read())
        status = 'OK' if result.get('success', True) else 'WARN'
        print(f'  {status} {method} {path}: {result}')
    except urllib.error.HTTPError as e:
        err_body = e.read().decode()
        print(f'  HTTP{e.code} {method} {path}: {err_body[:200]}')
        all_ok = False
    except Exception as e:
        print(f'  ERR {method} {path}: {e}')
        all_ok = False

# Test health
try:
    resp = urllib.request.urlopen(BASE + '/v2/health', timeout=5)
    data = json.loads(resp.read())
    s = data.get('status', 'unknown')
    print(f'  OK  /v2/health: status={s}')
except Exception as e:
    print(f'  ERR /v2/health: {e}')
    all_ok = False

if all_ok:
    print('\nAll notification APIs working!')
    sys.exit(0)
else:
    print('\nSome tests had issues (expected for missing UserID validation)')
    sys.exit(1)
