#!/bin/bash
# deploy_cache_proxy.sh — Deploy non-custodial cache proxy to server
set -e

SERVER="coinceeper"
ZONE="us-central1-f"
REMOTE_DIR="/opt/coinceeper/CC"
LOCAL_SRC="services/cache_proxy"

echo "============================================"
echo "🚀 Deploying Cache Proxy (Non-Custodial V2)"
echo "============================================"

echo ""
echo "=== 1. Transferring cache proxy files ==="
# Transfer each file individually (gcloud scp doesn't handle wildcards well on Windows)
for f in price_cache.py chart_cache.py gas_cache.py coin_cache.py routes_v2.py block_scanner.py __init__.py; do
  echo "  Transferring $f..."
  gcloud compute scp --zone "$ZONE" "${LOCAL_SRC}/${f}" "${SERVER}:${REMOTE_DIR}/${LOCAL_SRC}/" 2>&1
done

echo ""
echo "=== 2. Creating api-docs directory ==="
gcloud compute ssh "$SERVER" --zone "$ZONE" --command="mkdir -p ${REMOTE_DIR}/api-docs && chown mohammad:mohammad ${REMOTE_DIR}/api-docs" 2>&1

echo ""
echo "=== 3. Transferring api-docs ==="
gcloud compute scp --zone "$ZONE" "api-docs/index.html" "${SERVER}:${REMOTE_DIR}/api-docs/" 2>&1

echo ""
echo "=== 4. Cleaning server pycache ==="
gcloud compute ssh "$SERVER" --zone "$ZONE" --command="find ${REMOTE_DIR}/services/cache_proxy -name __pycache__ -type d -exec rm -rf {} + 2>/dev/null; echo 'pycache cleaned'" 2>&1

echo ""
echo "=== 5. Setting file ownership ==="
gcloud compute ssh "$SERVER" --zone "$ZONE" --command="chown -R mohammad:mohammad ${REMOTE_DIR}/services/cache_proxy && chown -R mohammad:mohammad ${REMOTE_DIR}/api-docs && echo 'ownership set'" 2>&1

echo ""
echo "=== 6. Verifying transferred files ==="
gcloud compute ssh "$SERVER" --zone "$ZONE" --command="echo '--- cache_proxy files ---' && ls -la ${REMOTE_DIR}/services/cache_proxy/ && echo '--- api-docs ---' && ls -la ${REMOTE_DIR}/api-docs/" 2>&1

echo ""
echo "=== 7. Syntax check (compile Python files) ==="
gcloud compute ssh "$SERVER" --zone "$ZONE" --command="cd ${REMOTE_DIR} && source /opt/coinceeper/venv/bin/activate && python -c \"
import py_compile
files = [
    'services/cache_proxy/__init__.py',
    'services/cache_proxy/price_cache.py',
    'services/cache_proxy/chart_cache.py',
    'services/cache_proxy/gas_cache.py',
    'services/cache_proxy/coin_cache.py',
    'services/cache_proxy/routes_v2.py',
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
else:
    print('ERROR: some files failed to compile')
    exit(1)
\"" 2>&1

echo ""
echo "=== 8. Restarting coinceeper-api service ==="
gcloud compute ssh "$SERVER" --zone "$ZONE" --command="sudo systemctl restart coinceeper-api && echo 'Service restarted successfully'" 2>&1

echo ""
echo "=== 9. Waiting for service to be ready ==="
sleep 8

echo ""
echo "=== 10. Checking service status ==="
gcloud compute ssh "$SERVER" --zone "$ZONE" --command="sudo systemctl status coinceeper-api --no-pager 2>&1 | head -20" 2>&1

echo ""
echo "=== 11. Testing V2 endpoints (health, then coins) ==="
gcloud compute ssh "$SERVER" --zone "$ZONE" --command="echo '--- Health ---' && curl -s --max-time 5 http://127.0.0.1:5000/api/v2/health 2>&1 | python -m json.tool 2>/dev/null || echo 'health timeout'" 2>&1

echo ""
echo "=== 12. Testing coins endpoint ==="
gcloud compute ssh "$SERVER" --zone "$ZONE" --command="echo '--- Coins ---' && curl -s --max-time 8 http://127.0.0.1:5000/api/v2/coins 2>&1 | python -c 'import sys,json; d=json.load(sys.stdin); print(f\"success={d.get(chr(115)+chr(117)+chr(99)+chr(99)+chr(101)+chr(115)+chr(115))} count={d.get(chr(99)+chr(111)+chr(117)+chr(110)+chr(116))} status={d.get(chr(99)+chr(97)+chr(99)+chr(104)+chr(101)+chr(95)+chr(115)+chr(116)+chr(97)+chr(116)+chr(117)+chr(115))}\")' 2>&1" 2>&1

echo ""
echo "============================================"
echo "✅ Deployment complete!"
echo "============================================"
