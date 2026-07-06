#!/bin/bash
# deploy_anonymous_deviceid.sh — Deploy anonymous DeviceID changes for push notifications
set -e

SERVER="${1:-coinceeper}"
ZONE="us-central1-f"
REMOTE_DIR="/opt/coinceeper/CC"
LOCAL_DIR="e:/coinceeper/backend/coinceeper.com/CC"

echo "=== Deploying Anonymous DeviceID Support ==="

echo ""
echo "=== 1. Transferring modified files ==="
gcloud compute scp --zone "$ZONE" \
  "$LOCAL_DIR/services/notifications/base.py" \
  "${SERVER}:${REMOTE_DIR}/services/notifications/base.py" --quiet
echo "  -> services/notifications/base.py"

gcloud compute scp --zone "$ZONE" \
  "$LOCAL_DIR/api/notification_api.py" \
  "${SERVER}:${REMOTE_DIR}/api/notification_api.py" --quiet
echo "  -> api/notification_api.py"

gcloud compute scp --zone "$ZONE" \
  "$LOCAL_DIR/api/notifications_admin_api.py" \
  "${SERVER}:${REMOTE_DIR}/api/notifications_admin_api.py" --quiet
echo "  -> api/notifications_admin_api.py"

echo ""
echo "=== 2. Syntax check on server ==="
gcloud compute ssh "$SERVER" --zone "$ZONE" --command="cd ${REMOTE_DIR} && source /opt/coinceeper/venv/bin/activate && python3 -c '
import py_compile
files = [
    \"services/notifications/base.py\",
    \"api/notification_api.py\",
    \"api/notifications_admin_api.py\",
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
echo "=== 3. Restarting service ==="
gcloud compute ssh "$SERVER" --zone "$ZONE" --command="sudo systemctl restart coinceeper-api && echo 'Service restarted successfully'" 2>&1

echo ""
echo "=== 4. Waiting for service to be ready ==="
sleep 10

echo ""
echo "=== 5. Checking service status ==="
gcloud compute ssh "$SERVER" --zone "$ZONE" --command="sudo systemctl status coinceeper-api --no-pager 2>&1 | head -20" 2>&1

echo ""
echo "=== Deployment complete! ==="
echo "Now run the diagnostic test to verify anonymous DeviceID flow."
