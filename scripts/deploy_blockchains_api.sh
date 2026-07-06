#!/bin/bash
set -e

SERVER="coinceeper"
PROJECT="omega-bearing-446811-p5"
ZONE="us-central1-a"
REMOTE_DIR="/opt/coinceeper/CC"

echo "=== 1. Copying blockchains_api.py ==="
gcloud compute scp --project "$PROJECT" --zone "$ZONE" \
  "api/blockchains_api.py" \
  "${SERVER}:${REMOTE_DIR}/api/blockchains_api.py"

echo "=== 2. Setting ownership ==="
gcloud compute ssh "$SERVER" --project "$PROJECT" --zone "$ZONE" --command="sudo chown mohammad:mohammad ${REMOTE_DIR}/api/blockchains_api.py"

echo "=== 3. Adding import to app.py ==="
gcloud compute ssh "$SERVER" --project "$PROJECT" --zone "$ZONE" --command="
cd ${REMOTE_DIR}
# Add import line after app_version_api import
if ! grep -q 'blockchains_api' app.py; then
  sudo sed -i '/^from api.app_version_api import app_version_bp$/a from api.blockchains_api import blockchains_bp' app.py
  echo 'Import added'
fi
"

echo "=== 4. Adding blueprint registration ==="
gcloud compute ssh "$SERVER" --project "$PROJECT" --zone "$ZONE" --command="
cd ${REMOTE_DIR}
if grep -q 'blockchains_api' app.py; then
  # Check if registration already exists
  if grep -q 'register_blueprint(blockchains_bp' app.py; then
    echo 'Registration already exists'
  else
    # Find the line with app_version_api logger and add after it
    sudo sed -i '/logger.info(\"Registered app_version_api\")$/a\\n    # Register Blockchains List API\n    app.register_blueprint(blockchains_bp, url_prefix=\"'"'"'/api'"'"'\)\n    logger.info(\"Registered blockchains_api\")' app.py
    echo 'Registration added'
  fi
fi
"

echo "=== 5. Verifying ==="
gcloud compute ssh "$SERVER" --project "$PROJECT" --zone "$ZONE" --command="grep -n 'blockchains' ${REMOTE_DIR}/app.py"

echo "=== 6. Restarting service ==="
gcloud compute ssh "$SERVER" --project "$PROJECT" --zone "$ZONE" --command="sudo systemctl restart coinceeper-api && echo 'Service restarted'"

echo "=== 7. Waiting 8s ==="
sleep 8

echo "=== 8. Testing endpoint ==="
gcloud compute ssh "$SERVER" --project "$PROJECT" --zone "$ZONE" --command="curl -s --max-time 5 http://127.0.0.1:5000/api/blockchains | python -m json.tool"

echo ""
echo "=== ✅ Deployment complete ==="
