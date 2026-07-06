#!/bin/bash
# deploy_notifications.sh — Deploy notification system (priorities 2-5)
set -e

SERVER="coinceeper"
ZONE="us-central1-f"
REMOTE_DIR="/opt/coinceeper/CC"

echo "=== Deploying Notification System (Priorities 2-5) ==="

echo ""
echo "=== 1. Transferring notification modules ==="
gcloud compute scp --zone "$ZONE" \
  services/notifications/__init__.py \
  services/notifications/base.py \
  services/notifications/security.py \
  services/notifications/price_alerts.py \
  services/notifications/network.py \
  services/notifications/engagement.py \
  services/notifications/scheduler.py \
  "${SERVER}:${REMOTE_DIR}/services/notifications/" --quiet

echo ""
echo "=== 2. Transferring admin notification API ==="
gcloud compute scp --zone "$ZONE" \
  api/notifications_admin_api.py \
  "${SERVER}:${REMOTE_DIR}/api/" --quiet

echo ""
echo "=== 3. Transferring updated app.py ==="
gcloud compute scp --zone "$ZONE" \
  app.py \
  "${SERVER}:${REMOTE_DIR}/app.py" --quiet

echo ""
echo "=== 4. Syntax check on server ==="
gcloud compute ssh "$SERVER" --zone "$ZONE" --command="cd ${REMOTE_DIR} && source /opt/coinceeper/venv/bin/activate && python3 -c '
import py_compile
files = [
    \"services/notifications/__init__.py\",
    \"services/notifications/base.py\",
    \"services/notifications/security.py\",
    \"services/notifications/price_alerts.py\",
    \"services/notifications/network.py\",
    \"services/notifications/engagement.py\",
    \"services/notifications/scheduler.py\",
    \"api/notifications_admin_api.py\",
    \"api/notification_api.py\",
    \"app.py\",
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
echo "=== 5. Restarting service ==="
gcloud compute ssh "$SERVER" --zone "$ZONE" --command="sudo systemctl restart coinceeper-api && echo 'Service restarted successfully'" 2>&1

echo ""
echo "=== 6. Waiting for service to be ready ==="
sleep 8

echo ""
echo "=== 7. Checking service status ==="
gcloud compute ssh "$SERVER" --zone "$ZONE" --command="sudo systemctl status coinceeper-api --no-pager 2>&1 | head -20" 2>&1

echo ""
echo "=== 8. Testing notification APIs ==="
echo "--- Security Login (requires valid UserID) ---"
gcloud compute ssh "$SERVER" --zone "$ZONE" --command="curl -s --max-time 5 -X POST http://127.0.0.1:5000/api/notifications/security/login -H 'Content-Type: application/json' -d '{\"UserID\":\"test\",\"DeviceName\":\"Test\",\"IPAddress\":\"1.2.3.4\"}' 2>&1" 2>&1

echo ""
echo "=== Deployment complete! ==="
