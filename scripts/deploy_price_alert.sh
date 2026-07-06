#!/bin/bash
# deploy_price_alert.sh — Deploy price alert scheduler fix
set -e

SERVER="coinceeper"
ZONE="us-central1-f"
REMOTE_DIR="/opt/coinceeper/CC"

echo "=== Deploying Price Alert Scheduler Fix ==="

echo ""
echo "=== 1. Transferring updated scheduler.py ==="
gcloud compute scp --zone "$ZONE" \
  services/notifications/scheduler.py \
  "${SERVER}:${REMOTE_DIR}/services/notifications/scheduler.py" --quiet

echo ""
echo "=== 2. Syntax check on server ==="
gcloud compute ssh "$SERVER" --zone "$ZONE" --command="cd ${REMOTE_DIR} && source /opt/coinceeper/venv/bin/activate && python3 -c '
import py_compile
try:
    py_compile.compile(\"services/notifications/scheduler.py\", doraise=True)
    print(\"  OK: services/notifications/scheduler.py\")
except py_compile.PyCompileError as e:
    print(f\"  FAIL: {e}\")
    exit(1)
print(\"Syntax check passed\")
'" 2>&1

echo ""
echo "=== 3. Restarting service ==="
gcloud compute ssh "$SERVER" --zone "$ZONE" --command="sudo systemctl restart coinceeper-api && echo 'Service restarted successfully'" 2>&1

echo ""
echo "=== 4. Waiting for service to be ready ==="
sleep 8

echo ""
echo "=== 5. Checking service status ==="
gcloud compute ssh "$SERVER" --zone "$ZONE" --command="sudo systemctl status coinceeper-api --no-pager 2>&1 | head -20" 2>&1

echo ""
echo "=== Deployment complete! ==="
echo "The price alert scheduler now runs every 10 minutes."
