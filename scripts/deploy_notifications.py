#!/usr/bin/env python3
"""
Deployment verification script for notification system.
Run directly on the server.
"""
import py_compile
import sys

files = [
    'services/notifications/__init__.py',
    'services/notifications/base.py',
    'services/notifications/security.py',
    'services/notifications/price_alerts.py',
    'services/notifications/network.py',
    'services/notifications/engagement.py',
    'services/notifications/scheduler.py',
    'api/notifications_admin_api.py',
    'api/notification_api.py',
    'app.py',
]
ok = True
for f in files:
    try:
        py_compile.compile(f, doraise=True)
        print(f'  OK: {f}')
    except py_compile.PyCompileError as e:
        print(f'  FAIL: {f}: {e}')
        ok = False
if ok:
    print('All files compiled successfully')
    sys.exit(0)
else:
    print('ERROR: some files failed')
    sys.exit(1)
