"""Simple syntax check for uploaded files - run on server."""
import sys
import py_compile

files = [
    "database/price_alert.py",
    "database/__init__.py", 
    "api/notifications_admin_api.py",
    "services/notifications/scheduler.py",
]

all_ok = True
for f in files:
    try:
        py_compile.compile(f, doraise=True)
        print("OK: " + f)
    except py_compile.PyCompileError as e:
        print("FAIL: " + f + ": " + str(e))
        all_ok = False

if all_ok:
    print("All files compiled successfully")
    sys.exit(0)
else:
    print("ERROR: some files failed")
    sys.exit(1)
