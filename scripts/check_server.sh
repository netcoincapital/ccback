#!/bin/bash
# Check server deps and state for cache proxy deployment
source /opt/coinceeper/venv/bin/activate

echo "=== Python ==="
python --version

echo "=== Requests ==="
python -c "import requests; print('requests:', requests.__version__)" 2>&1

echo "=== Flask ==="
python -c "import flask; print('flask:', flask.__version__)" 2>&1

echo "=== services/ dir ==="
ls -la /opt/coinceeper/CC/services/

echo "=== app.py modified? ==="
head -10 /opt/coinceeper/CC/app.py

echo "=== nginx config ==="
cat /etc/nginx/sites-enabled/coinceeper 2>/dev/null || cat /etc/nginx/conf.d/coinceeper.conf 2>/dev/null || echo "nginx config not found at standard paths"

echo "=== Disk space ==="
df -h /opt/coinceeper

echo "=== Checking if requests needs upgrade ==="
python -c "import urllib3; print('urllib3:', urllib3.__version__)" 2>&1
