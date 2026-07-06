"""Deploy Tron broadcast provider to server."""
import py_compile
import sys
import os

files = [
    'services/cache_proxy/providers/tron_broadcast.py',
    'services/cache_proxy/providers/__init__.py',
    'services/cache_proxy/routes_v3.py',
]

os.chdir('/opt/coinceeper/CC')
all_ok = True
for f in files:
    try:
        py_compile.compile(f, doraise=True)
        print(f'OK: {f}')
    except py_compile.PyCompileError as e:
        print(f'FAIL: {f}: {e}')
        all_ok = False

if all_ok:
    print('All files compiled successfully')
else:
    print('ERROR: some files failed')
    sys.exit(1)
