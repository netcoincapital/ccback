#!/bin/bash
# deploy_tron_broadcast.sh — Deploy Tron broadcast provider to server
set -e

SERVER="coinceeper"
ZONE="us-central1-a"
REMOTE_DIR="/opt/coinceeper/CC"

echo "============================================"
echo "  Deploy Tron Broadcast Provider"
echo "============================================"

echo "=== 1. Cleaning pycache ==="
gcloud compute ssh "$SERVER" --zone "$ZONE" --command="find ${REMOTE_DIR}/services/cache_proxy -name __pycache__ -type d -exec rm -rf {} + 2>/dev/null; echo 'done'"

echo "=== 2. Setting ownership ==="
gcloud compute ssh "$SERVER" --zone "$ZONE" --command="chown mohammad:mohammad ${REMOTE_DIR}/services/cache_proxy/providers/tron_broadcast.py ${REMOTE_DIR}/services/cache_proxy/providers/__init__.py ${REMOTE_DIR}/services/cache_proxy/routes_v3.py; echo 'done'"

echo "=== 3. Syntax check ==="
gcloud compute ssh "$SERVER" --zone "$ZONE" --command="cd ${REMOTE_DIR} && source /opt/coinceeper/venv/bin/activate && python << 'PYEOF'
import py_compile
files = [
    'services/cache_proxy/providers/tron_broadcast.py',
    'services/cache_proxy/providers/__init__.py',
    'services/cache_proxy/routes_v3.py',
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
    print('All files compiled successfully')
else:
    print('ERROR: some files failed')
    exit(1)
PYEOF"

echo "=== 4. Restarting coinceeper-api service ==="
gcloud compute ssh "$SERVER" --zone "$ZONE" --command="sudo systemctl restart coinceeper-api && echo 'Service restarted'"

echo "=== 5. Waiting 8s for service ready ==="
sleep 8

echo "=== 6. Testing broadcast endpoint (health check) ==="
gcloud compute ssh "$SERVER" --zone "$ZONE" --command="curl -s --max-time 5 http://127.0.0.1:5000/api/v2/proxy-health 2>&1 | python -c 'import sys, json; d=json.load(sys.stdin); p=d.get(\"providers\",{}); print(\"tron_broadcast:\", p.get(\"tron_broadcast\",\"?\")); print(\"trongrid:\",p.get(\"trongrid\",\"?\"))'"

echo ""
echo "============================================"
echo "  ✅ Deploy complete!"
echo "============================================"
