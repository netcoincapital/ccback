# deploy_airdrops.ps1 — Deploy airdrop API (CryptoRank V2) to server
$ErrorActionPreference = "Stop"

$SERVER = "coinceeper"
$ZONE = "us-central1-a"
$PROJECT = "omega-bearing-446811-p5"
$REMOTE_DIR = "/opt/coinceeper/CC"
$LOCAL_SRC = "services/cache_proxy"

Write-Host "============================================"
Write-Host "  Deploying Airdrop API (CryptoRank V2)"
Write-Host "  Project: $PROJECT"
Write-Host "  Zone: $ZONE"
Write-Host "============================================"
Write-Host ""

# 1. Transfer cache_proxy files
Write-Host "=== 1. Transferring cache_proxy files ==="
$files = @(
    "price_cache.py",
    "chart_cache.py",
    "gas_cache.py",
    "coin_cache.py",
    "routes_v2.py",
    "airdrop_cache.py",
    "__init__.py"
)
foreach ($f in $files) {
    Write-Host "  Transferring $f..."
    $src = Join-Path $LOCAL_SRC $f
    gcloud compute scp --zone "$ZONE" --project "$PROJECT" "$src" "${SERVER}:${REMOTE_DIR}/${LOCAL_SRC}/" 2>&1
}

# 2. Transfer .env with CRYPTORANK_API_KEY
Write-Host "=== 2. Transferring .env (with CRYPTORANK_API_KEY) ==="
gcloud compute scp --zone "$ZONE" --project "$PROJECT" ".env" "${SERVER}:${REMOTE_DIR}/.env" 2>&1

# 3. Clean pycache & set ownership
Write-Host "=== 3. Cleaning pycache & setting ownership ==="
gcloud compute ssh "$SERVER" --zone "$ZONE" --project "$PROJECT" --command="find ${REMOTE_DIR}/services/cache_proxy -name __pycache__ -type d -exec rm -rf {} + 2>/dev/null; chown -R mohammad:mohammad ${REMOTE_DIR}/services/cache_proxy; chown mohammad:mohammad ${REMOTE_DIR}/.env; echo 'cleaned and owned'" 2>&1

# 4. Verify transferred files
Write-Host "=== 4. Verifying transferred files ==="
gcloud compute ssh "$SERVER" --zone "$ZONE" --project "$PROJECT" --command="ls -la ${REMOTE_DIR}/services/cache_proxy/" 2>&1

# 5. Syntax check
Write-Host "=== 5. Syntax check ==="
gcloud compute ssh "$SERVER" --zone "$ZONE" --project "$PROJECT" --command="cd ${REMOTE_DIR} && source /opt/coinceeper/venv/bin/activate && python -m py_compile services/cache_proxy/airdrop_cache.py && echo 'OK: airdrop_cache.py' && python -m py_compile services/cache_proxy/routes_v2.py && echo 'OK: routes_v2.py' && python -m py_compile services/cache_proxy/__init__.py && echo 'OK: __init__.py'" 2>&1

# 6. Restart service
Write-Host "=== 6. Restarting coinceeper-api service ==="
gcloud compute ssh "$SERVER" --zone "$ZONE" --project "$PROJECT" --command="sudo systemctl restart coinceeper-api && echo 'Service restarted'" 2>&1

# 7. Wait
Write-Host "=== 7. Waiting 10s for service to be ready ==="
Start-Sleep -Seconds 10

# 8. Check service status
Write-Host "=== 8. Checking service status ==="
gcloud compute ssh "$SERVER" --zone "$ZONE" --project "$PROJECT" --command="sudo systemctl status coinceeper-api --no-pager 2>&1 | head -20" 2>&1

# 9. Test health
Write-Host "=== 9. Testing health endpoint ==="
gcloud compute ssh "$SERVER" --zone "$ZONE" --project "$PROJECT" --command="curl -s --max-time 10 http://127.0.0.1:5000/api/v2/health | python -m json.tool 2>/dev/null || echo 'timeout'" 2>&1

# 10. Upload test script
Write-Host "=== 10. Uploading test script ==="
@"
import sys, json, requests

def test(url, label):
    try:
        resp = requests.get(url, timeout=30)
        data = resp.json()
        print(f'  [{label}] {resp.status_code} success={data.get("success")}')
        return data
    except Exception as e:
        print(f'  [{label}] ERROR: {e}')
        return None

base = 'http://127.0.0.1:5000/api/v2'

print('--- Health ---')
d = test(f'{base}/health', 'health')
if d and 'caches' in d:
    for name, info in d['caches'].items():
        print(f'    {name}: {info}')

print('')
print('--- Airdrops List ---')
d = test(f'{base}/airdrops', 'airdrops')
if d:
    items = d.get('airdrops', [])
    print(f'    count={d.get("count")} total={d.get("total")} cache_status={d.get("cache_status")}')
    if items:
        first = items[0]
        aid = first.get('id') or first.get('name', '?')
        print(f'    First airdrop ID/Name: {aid}')

        print('')
        print('--- Airdrop Detail ---')
        test(f'{base}/airdrops/{aid}', 'detail')

        print('')
        print('--- Airdrop Tasks ---')
        test(f'{base}/airdrops/{aid}/tasks', 'tasks')

print('')
print('All tests completed.')
"@ | Out-File -FilePath "test_airdrops.py" -Encoding UTF8

gcloud compute scp --zone "$ZONE" --project "$PROJECT" "test_airdrops.py" "${SERVER}:${REMOTE_DIR}/test_airdrops.py" 2>&1

# 11. Run tests
Write-Host "=== 11. Running test script on server ==="
gcloud compute ssh "$SERVER" --zone "$ZONE" --project "$PROJECT" --command="cd ${REMOTE_DIR} && source /opt/coinceeper/venv/bin/activate && python test_airdrops.py 2>&1" 2>&1

# Cleanup
Remove-Item -Force "test_airdrops.py" -ErrorAction SilentlyContinue

Write-Host ""
Write-Host "============================================"
Write-Host "  Airdrop API deployment complete!"
Write-Host "============================================"
