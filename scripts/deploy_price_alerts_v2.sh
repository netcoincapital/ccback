#!/bin/bash
# deploy_price_alerts_v2.sh — Deploy new dual-type price alert system
set -e

SERVER="coinceeper"
ZONE="us-central1-f"
REMOTE_DIR="/opt/coinceeper/CC"

echo "=== Deploying Price Alert V2 (Custom + Percentage) ==="

echo ""
echo "=== 1. Transferring new database model ==="
gcloud compute scp --zone "$ZONE" \
  database/price_alert.py \
  "${SERVER}:${REMOTE_DIR}/database/price_alert.py" --quiet
echo "  OK: database/price_alert.py"

echo ""
echo "=== 2. Transferring updated database __init__ ==="
gcloud compute scp --zone "$ZONE" \
  database/__init__.py \
  "${SERVER}:${REMOTE_DIR}/database/__init__.py" --quiet
echo "  OK: database/__init__.py"

echo ""
echo "=== 3. Transferring updated notification admin API ==="
gcloud compute scp --zone "$ZONE" \
  api/notifications_admin_api.py \
  "${SERVER}:${REMOTE_DIR}/api/notifications_admin_api.py" --quiet
echo "  OK: api/notifications_admin_api.py"

echo ""
echo "=== 4. Transferring updated scheduler ==="
gcloud compute scp --zone "$ZONE" \
  services/notifications/scheduler.py \
  "${SERVER}:${REMOTE_DIR}/services/notifications/scheduler.py" --quiet
echo "  OK: services/notifications/scheduler.py"

echo ""
echo "=== 5. Transferring migration SQL ==="
gcloud compute scp --zone "$ZONE" \
  migrations/add_price_alerts_table.sql \
  "${SERVER}:${REMOTE_DIR}/migrations/add_price_alerts_table.sql" --quiet
echo "  OK: migrations/add_price_alerts_table.sql"

echo ""
echo "=== 6. Syntax check on server ==="
gcloud compute ssh "$SERVER" --zone "$ZONE" --command="cd ${REMOTE_DIR} && source /opt/coinceeper/venv/bin/activate && python3 -c '
import py_compile
files = [
    \"database/price_alert.py\",
    \"database/__init__.py\",
    \"api/notifications_admin_api.py\",
    \"services/notifications/scheduler.py\",
]
ok = True
for f in files:
    try:
        py_compile.compile(f, doraise=True)
        print(f\"  OK: {f}\")
    except py_compile.PyCompileError as e:
        print(f\"  FAIL: {f}: {e}\")
        ok = False
if ok:
    print(\"All files compiled successfully\")
else:
    print(\"ERROR: some files failed\")
    exit(1)
'" 2>&1

echo ""
echo "=== 7. Restarting service ==="
gcloud compute ssh "$SERVER" --zone "$ZONE" --command="sudo systemctl restart coinceeper-api && echo 'Service restarted successfully'" 2>&1

echo ""
echo "=== 8. Waiting for service to be ready ==="
sleep 10

echo ""
echo "=== 9. Checking service status ==="
gcloud compute ssh "$SERVER" --zone "$ZONE" --command="sudo systemctl status coinceeper-api --no-pager 2>&1 | head -20" 2>&1

echo ""
echo "=== 10. Testing price alert APIs ==="
echo "--- Creating test price alert (custom) ---"
gcloud compute ssh "$SERVER" --zone "$ZONE" --command="curl -s --max-time 5 -X POST http://127.0.0.1:5000/api/notifications/price-alert -H 'Content-Type: application/json' -d '{\"UserID\":\"deploy-test\",\"Symbol\":\"BTC\",\"AlertType\":\"above\",\"TargetPrice\":100000}' 2>&1" 2>&1

echo ""
echo "--- Creating test price alert (percentage) ---"
gcloud compute ssh "$SERVER" --zone "$ZONE" --command="curl -s --max-time 5 -X POST http://127.0.0.1:5000/api/notifications/price-alert -H 'Content-Type: application/json' -d '{\"UserID\":\"deploy-test\",\"Symbol\":\"ETH\",\"AlertType\":\"percent_up\",\"TargetPercent\":10}' 2>&1" 2>&1

echo ""
echo "--- Listing alerts ---"
gcloud compute ssh "$SERVER" --zone "$ZONE" --command="curl -s --max-time 5 http://127.0.0.1:5000/api/notifications/price-alerts/deploy-test 2>&1" 2>&1

echo ""
echo "--- Testing bulk prices ---"
gcloud compute ssh "$SERVER" --zone "$ZONE" --command="curl -s --max-time 5 'http://127.0.0.1:5000/api/notifications/price-alerts/prices?symbols=BTC,ETH,SOL' 2>&1" 2>&1

echo ""
echo "=== 11. Cleaning up test data ==="
gcloud compute ssh "$SERVER" --zone "$ZONE" --command="cd ${REMOTE_DIR} && source /opt/coinceeper/venv/bin/activate && python3 -c '
from database import SessionLocal, PriceAlert
session = SessionLocal()
session.query(PriceAlert).filter(PriceAlert.user_id == \"deploy-test\").delete()
session.commit()
session.close()
print(\"Test data cleaned\")
'" 2>&1

echo ""
echo "=== Deployment Complete! ==="
echo ""
echo "New Features Deployed:"
echo "  1. Custom Price Alerts (above/below with exact price)"
echo "  2. Quick Percentage Alerts (percent_up/percent_down with auto-reference)"
echo "  3. Bulk Price endpoint (solves N+1 client issue)"
echo "  4. In-memory cache with 30s TTL"
echo "  5. Dedicated price_alerts table"
echo ""
echo "See docs: api-docs/frontend-price-alert-guide.md"
