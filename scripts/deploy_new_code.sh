#!/bin/bash
set -e

REMOTE_DIR="/opt/coinceeper/CC"
source /opt/coinceeper/venv/bin/activate

echo "=== 1. Setting ownership ==="
chown -R mohammad:mohammad "$REMOTE_DIR/services/cache_proxy"
chown -R mohammad:mohammad "$REMOTE_DIR/deploy"
chown -R mohammad:mohammad "$REMOTE_DIR/secrets"
chown mohammad:mohammad "$REMOTE_DIR/app.py"
chown mohammad:mohammad "$REMOTE_DIR/.env.template"
echo "ownership set"

echo "=== 2. Cleaning pycache ==="
find "$REMOTE_DIR/services/cache_proxy" -name __pycache__ -type d -exec rm -rf {} + 2>/dev/null || true
echo "pycache cleaned"

echo "=== 3. Verifying transferred files ==="
echo "--- cache_proxy structure ---"
find "$REMOTE_DIR/services/cache_proxy" -name "*.py" | sort

echo "--- deploy files ---"
ls -la "$REMOTE_DIR/deploy/" 2>/dev/null || echo "no deploy dir"

echo "--- secrets ---"
ls -la "$REMOTE_DIR/secrets/" 2>/dev/null || echo "no secrets dir"

echo "=== 4. Checking Python dependencies ==="
python -c "
import importlib
pkgs = {'flask': 'flask', 'redis': 'redis', 'requests': 'requests', 'prometheus_client': 'prometheus_client'}
for name, mod in pkgs.items():
    try:
        m = importlib.import_module(mod)
        ver = getattr(m, '__version__', '?')
        print(f'OK: {name} (v{ver})')
    except ImportError:
        print(f'MISSING: {name}')
"

echo "=== 5. Installing missing deps ==="
python -c "import prometheus_client" 2>/dev/null && echo "prometheus_client OK" || pip install prometheus-client 2>&1 | tail -2
python -c "import redis" 2>/dev/null && echo "redis OK" || pip install redis 2>&1 | tail -2
echo "dependencies installed"

echo "=== 6. Syntax check (compile Python files) ==="
python -c "
import py_compile, sys, os

files = [
    'services/cache_proxy/__init__.py',
    'services/cache_proxy/price_cache.py',
    'services/cache_proxy/chart_cache.py',
    'services/cache_proxy/coin_cache.py',
    'services/cache_proxy/routes_v3.py',
    'services/cache_proxy/core/__init__.py',
    'services/cache_proxy/core/cache.py',
    'services/cache_proxy/core/errors.py',
    'services/cache_proxy/core/key_pool.py',
    'services/cache_proxy/core/metrics.py',
    'services/cache_proxy/core/rate_limiter.py',
    'services/cache_proxy/providers/__init__.py',
    'services/cache_proxy/providers/evm_explorer.py',
    'services/cache_proxy/providers/evm_rpc.py',
    'services/cache_proxy/providers/trongrid.py',
    'services/cache_proxy/providers/solana.py',
    'services/cache_proxy/providers/blockcypher.py',
    'services/cache_proxy/providers/blockstream.py',
    'services/cache_proxy/providers/subscan.py',
]

os.chdir('$REMOTE_DIR')
ok = True
for f in files:
    try:
        py_compile.compile(f, doraise=True)
        print(f'OK: {f}')
    except py_compile.PyCompileError as e:
        print(f'FAIL: {f}: {e}')
        ok = False
if ok:
    print('All files compiled successfully')
else:
    print('ERROR: some files failed to compile')
    sys.exit(1)
"

echo ""
echo "=== All checks passed. Ready for restart ==="
