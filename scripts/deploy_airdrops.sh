#!/bin/bash
# deploy_airdrops.sh — Deploy new airdrop API (CryptoRank) to server
set -e

SERVER="coinceeper"
ZONE="us-central1-f"
REMOTE_DIR="/opt/coinceeper/CC"
LOCAL_SRC="services/cache_proxy"

echo "============================================"
echo "  Deploying Airdrop API (CryptoRank V2)"
echo "============================================"

echo ""
echo "=== 1. Transferring cache_proxy files (with airdrop_cache) ==="
for f in price_cache.py chart_cache.py gas_cache.py coin_cache.py routes_v2.py airdrop_cache.py __init__.py; do
  echo "  Transferring $f..."
  gcloud compute scp --zone "$ZONE" "${LOCAL_SRC}/${f}" "${SERVER}:${REMOTE_DIR}/${LOCAL_SRC}/" 2>&1
done

echo ""
echo "=== 2. Transferring .env (with CRYPTORANK_API_KEY) ==="
gcloud compute scp --zone "$ZONE" ".env" "${SERVER}:${REMOTE_DIR}/.env" 2>&1

echo ""
echo "=== 3. Cleaning server pycache ==="
gcloud compute ssh "$SERVER" --zone "$ZONE" --command="find ${REMOTE_DIR}/services/cache_proxy -name __pycache__ -type d -exec rm -rf {} + 2>/dev/null; echo 'pycache cleaned'" 2>&1

echo ""
echo "=== 4. Setting file ownership ==="
gcloud compute ssh "$SERVER" --zone "$ZONE" --command="chown -R mohammad:mohammad ${REMOTE_DIR}/services/cache_proxy && chown mohammad:mohammad ${REMOTE_DIR}/.env && echo 'ownership set'" 2>&1

echo ""
echo "=== 5. Verifying transferred files ==="
gcloud compute ssh "$SERVER" --zone "$ZONE" --command="echo '--- cache_proxy files ---' && ls -la ${REMOTE_DIR}/services/cache_proxy/ && echo '--- .env ---' && ls -la ${REMOTE_DIR}/.env" 2>&1

echo ""
echo "=== 6. Syntax check (compile Python files) ==="
gcloud compute ssh "$SERVER" --zone "$ZONE" --command="cd ${REMOTE_DIR} && source /opt/coinceeper/venv/bin/activate && python -c \"
import py_compile
files = [
    'services/cache_proxy/__init__.py',
    'services/cache_proxy/price_cache.py',
    'services/cache_proxy/chart_cache.py',
    'services/cache_proxy/gas_cache.py',
    'services/cache_proxy/coin_cache.py',
    'services/cache_proxy/airdrop_cache.py',
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
echo "=== 7. Restarting coinceeper-api service ==="
gcloud compute ssh "$SERVER" --zone "$ZONE" --command="sudo systemctl restart coinceeper-api && echo 'Service restarted successfully'" 2>&1

echo ""
echo "=== 8. Waiting for service to be ready ==="
sleep 8

echo ""
echo "=== 9. Checking service status ==="
gcloud compute ssh "$SERVER" --zone "$ZONE" --command="sudo systemctl status coinceeper-api --no-pager 2>&1 | head -20" 2>&1

echo ""
echo "=== 10. Testing health endpoint ==="
gcloud compute ssh "$SERVER" --zone "$ZONE" --command="echo '--- Health ---' && curl -s --max-time 10 http://127.0.0.1:5000/api/v2/health 2>&1 | python -m json.tool 2>/dev/null || echo 'health timeout'" 2>&1

echo ""
echo "=== 11. Testing airdrops endpoint ==="
gcloud compute ssh "$SERVER" --zone "$ZONE" --command="echo '--- Airdrops List ---' && curl -s --max-time 15 http://127.0.0.1:5000/api/v2/airdrops 2>&1 | python -c \"
import sys, json
try:
    d = json.load(sys.stdin)
    print(f'success={d.get(\\\"success\\\")} count={d.get(\\\"count\\\")} total={d.get(\\\"total\\\")} status={d.get(\\\"cache_status\\\")}')
    if d.get(\\\"airdrops\\\"):
        print(f'First airdrop: {json.dumps(d[\\\"airdrops\\\"][0], indent=2)[:300]}')
except Exception as e:
    print(f'Parse error: {e}')
\"" 2>&1

echo ""
echo "=== 12. Testing airdrops detail endpoint (if any exist) ==="
gcloud compute ssh "$SERVER" --zone "$ZONE" --command="echo '--- Airdrop Detail ---' && FIRST_ID=\$(curl -s --max-time 15 http://127.0.0.1:5000/api/v2/airdrops 2>&1 | python -c \"
import sys, json
try:
    d = json.load(sys.stdin)
    items = d.get(\\\"airdrops\\\", [])
    if items:
        first = items[0]
        print(first.get(\\\"id\\\", first.get(\\\"name\\\", \\\"\\\")))
    else:
        print('')
except:
    print('')
\" 2>&1) && if [ -n \"\$FIRST_ID\" ]; then echo \"Testing detail for: \$FIRST_ID\" && curl -s --max-time 10 \"http://127.0.0.1:5000/api/v2/airdrops/\$FIRST_ID\" 2>&1 | python -m json.tool 2>/dev/null | head -40; else echo 'No airdrops to test detail'; fi" 2>&1

echo ""
echo "============================================"
echo "  Airdrop API deployment complete!"
echo "============================================"
