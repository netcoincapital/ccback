"""Upload this to server to verify deployment."""
import sys, os
sys.path.insert(0, '/opt/coinceeper/CC')

import py_compile
files = [
    'api/notifications_admin_api.py',
    'utils/error_handlers.py',
    'database/price_alert.py',
    'services/notifications/scheduler.py',
]
all_ok = True
for f in files:
    try:
        py_compile.compile(f, doraise=True)
        print('OK: ' + f)
    except Exception as e:
        print('FAIL: ' + f + ': ' + str(e))
        all_ok = False

if not all_ok:
    print('SYNTAX ERROR')
    sys.exit(1)

from database.price_alert import PriceAlert
print('PriceAlert loaded: ' + PriceAlert.__tablename__)

from sqlalchemy import text
from database import SessionLocal
session = SessionLocal()
try:
    count = session.execute(text('SELECT COUNT(*) FROM price_alerts')).scalar()
    print('Table price_alerts exists. Row count: ' + str(count))
except Exception as e:
    print('Table check: ' + str(e))
finally:
    session.close()

print('VERIFICATION COMPLETE')
