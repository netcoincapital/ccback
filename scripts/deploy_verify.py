#!/usr/bin/env python3
import os
import sys
import importlib

REMOTE_DIR = "/opt/coinceeper/CC"
VENV_PYTHON = "/opt/coinceeper/venv/bin/python"

print("=== 1. Setting ownership ===")
os.system(f"chown -R mohammad:mohammad {REMOTE_DIR}/services/cache_proxy")
os.system(f"chown -R mohammad:mohammad {REMOTE_DIR}/deploy")
os.system(f"chown -R mohammad:mohammad {REMOTE_DIR}/secrets")
os.system(f"chown mohammad:mohammad {REMOTE_DIR}/app.py")
os.system(f"chown mohammad:mohammad {REMOTE_DIR}/.env.template")
print("ownership set")

print("\n=== 2. Cleaning pycache ===")
os.system(f"find {REMOTE_DIR}/services/cache_proxy -name __pycache__ -type d -exec rm -rf {{}} + 2>/dev/null || true")
print("pycache cleaned")

print("\n=== 3. Verifying transferred files ===")
os.system(f"find {REMOTE_DIR}/services/cache_proxy -name '*.py' -not -path '*__pycache__*' | sort")
os.system(f"ls -la {REMOTE_DIR}/deploy/ 2>/dev/null || echo 'no deploy dir'")
os.system(f"ls -la {REMOTE_DIR}/secrets/ 2>/dev/null || echo 'no secrets dir'")

print("\n=== 4. Checking Python dependencies ===")
pkgs = {
    "flask": "flask",
    "redis": "redis",
    "requests": "requests",
    "prometheus_client": "prometheus_client",
}
for name, mod in pkgs.items():
    try:
        m = importlib.import_module(mod)
        ver = getattr(m, "__version__", "?")
        print(f"  OK: {name} (v{ver})")
    except ImportError:
        print(f"  MISSING: {name}")

print("\n=== 5. Installing missing deps ===")
os.system(f"{VENV_PYTHON} -m pip install prometheus-client redis 2>&1 | tail -3")

print("\n=== 6. Syntax check (compile all Python files) ===")
os.chdir(REMOTE_DIR)
py_files = [
    "services/cache_proxy/__init__.py",
    "services/cache_proxy/price_cache.py",
    "services/cache_proxy/chart_cache.py",
    "services/cache_proxy/coin_cache.py",
    "services/cache_proxy/routes_v3.py",
    "services/cache_proxy/core/__init__.py",
    "services/cache_proxy/core/cache.py",
    "services/cache_proxy/core/errors.py",
    "services/cache_proxy/core/key_pool.py",
    "services/cache_proxy/core/metrics.py",
    "services/cache_proxy/core/rate_limiter.py",
    "services/cache_proxy/providers/__init__.py",
    "services/cache_proxy/providers/evm_explorer.py",
    "services/cache_proxy/providers/evm_rpc.py",
    "services/cache_proxy/providers/trongrid.py",
    "services/cache_proxy/providers/solana.py",
    "services/cache_proxy/providers/blockcypher.py",
    "services/cache_proxy/providers/blockstream.py",
    "services/cache_proxy/providers/subscan.py",
    "app.py",
]

import py_compile
ok = True
for f in py_files:
    if not os.path.exists(f):
        print(f"  NOT FOUND: {f}")
        ok = False
        continue
    try:
        py_compile.compile(f, doraise=True)
        print(f"  OK: {f}")
    except py_compile.PyCompileError as e:
        print(f"  FAIL: {f}: {e}")
        ok = False

if ok:
    print("\nAll files compiled successfully!")
else:
    print("\nERROR: some files failed to compile!")
    sys.exit(1)

print("\n=== All checks passed. Ready for restart ===")
