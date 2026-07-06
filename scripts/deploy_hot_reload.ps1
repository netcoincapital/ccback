# deploy_hot_reload.ps1 — Deploy key_pool.py + routes_v3.py hot-reload update
$ErrorActionPreference = "Stop"

$SERVER = "coinceeper"
$ZONE = "us-central1-f"
$REMOTE_DIR = "/opt/coinceeper/CC"

Write-Host "============================================"
Write-Host "  Deploy Hot-Reload Key Pool Update"
Write-Host "============================================"
Write-Host ""

# 1. Transfer updated files
Write-Host "=== 1. Transferring key_pool.py ==="
gcloud compute scp --zone "$ZONE" `
  "services/cache_proxy/core/key_pool.py" `
  "${SERVER}:${REMOTE_DIR}/services/cache_proxy/core/" 2>&1

Write-Host "=== 2. Transferring routes_v3.py ==="
gcloud compute scp --zone "$ZONE" `
  "services/cache_proxy/routes_v3.py" `
  "${SERVER}:${REMOTE_DIR}/services/cache_proxy/" 2>&1

Write-Host "=== 3. Transferring guide file ==="
gcloud compute scp --zone "$ZONE" `
  "scripts/hot_reload_keys_guide.txt" `
  "${SERVER}:${REMOTE_DIR}/scripts/" 2>&1

# 2. Clean pycache & set ownership
Write-Host "=== 4. Cleaning pycache & setting ownership ==="
gcloud compute ssh "$SERVER" --zone "$ZONE" --command="
find ${REMOTE_DIR}/services/cache_proxy -name __pycache__ -type d -exec rm -rf {} + 2>/dev/null
chown mohammad:mohammad ${REMOTE_DIR}/services/cache_proxy/core/key_pool.py
chown mohammad:mohammad ${REMOTE_DIR}/services/cache_proxy/routes_v3.py
echo 'done'
" 2>&1

# 3. Syntax check
Write-Host "=== 5. Syntax check ==="
gcloud compute ssh "$SERVER" --zone "$ZONE" --command="
cd ${REMOTE_DIR} && source /opt/coinceeper/venv/bin/activate && python -c \"
import py_compile
files = [
    'services/cache_proxy/core/key_pool.py',
    'services/cache_proxy/routes_v3.py',
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
\"
" 2>&1

# 4. Restart service
Write-Host "=== 6. Restarting coinceeper-api service ==="
gcloud compute ssh "$SERVER" --zone "$ZONE" --command="
sudo systemctl restart coinceeper-api
echo 'Service restarted'
" 2>&1

# 5. Wait & test
Write-Host "=== 7. Waiting 8s for service ready ==="
Start-Sleep -Seconds 8

Write-Host "=== 8. Testing health endpoint ==="
gcloud compute ssh "$SERVER" --zone "$ZONE" --command="
curl -s --max-time 5 http://127.0.0.1:5000/api/v2/proxy-health 2>&1 | python -c '
import sys, json
d = json.load(sys.stdin)
pools = d.get(\"modules\", {}).get(\"key_pools\", {})
print(f\"Active pools: {len(pools)}\")
for name, status in pools.items():
    total = status.get(\"total\", 0)
    avail = status.get(\"available\", 0)
    print(f\"  {name}: {total} keys, {avail} available\")
'
" 2>&1

Write-Host "=== 9. Testing reload endpoint ==="
gcloud compute ssh "$SERVER" --zone "$ZONE" --command="
curl -s --max-time 5 -X POST http://127.0.0.1:5000/api/v2/admin/reload-keys -H 'Content-Type: application/json' -d '{}' 2>&1 | python -m json.tool
" 2>&1

Write-Host ""
Write-Host "============================================"
Write-Host "  DEPLOY COMPLETE!"
Write-Host "============================================"
Write-Host ""
Write-Host "To add new keys and hot-reload:"
Write-Host "  1. Edit secrets/vm_api_keys.env (add KEY_N+1)"
Write-Host "  2. curl -X POST http://.../api/v2/admin/reload-keys"
Write-Host "  3. Check curl http://.../api/v2/proxy-health"
