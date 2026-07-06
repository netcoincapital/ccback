import py_compile
files = [
    'services/cache_proxy/__init__.py',
    'services/cache_proxy/price_cache.py',
    'services/cache_proxy/chart_cache.py',
    'services/cache_proxy/gas_cache.py',
    'services/cache_proxy/coin_cache.py',
    'services/cache_proxy/routes_v2.py',
    'app.py',
]
ok = True
for f in files:
    try:
        py_compile.compile(f, doraise=True)
        print(f'OK: {f}')
    except py_compile.PyCompileError as e:
        print(f'FAIL: {f}: {e}')
        ok = False
if ok:
    print('ALL FILES COMPILED SUCCESSFULLY')
else:
    print('ERROR: Some files failed to compile')
    exit(1)
