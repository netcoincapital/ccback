#!/bin/bash
echo "=== MySQL User Check ==="
sudo mysql -e "SELECT user,host FROM mysql.user WHERE user='coincee';" 2>&1
echo ""
echo "=== MySQL coincee password test ==="
source /opt/coinceeper/venv/bin/activate
cd /opt/coinceeper/CC
python3 -c "
import os
from dotenv import load_dotenv
load_dotenv()
pw = os.getenv('DB_PASSWORD', '')
print(f'Password from env: present={bool(pw)} len={len(pw)}')
"
echo ""
echo "=== Testing connection with DB_PASSWORD ==="
python3 -c "
import os
from urllib.parse import quote_plus
from sqlalchemy import create_engine, text

pw = os.getenv('DB_PASSWORD', '')
user = os.getenv('DB_USER', 'coincee')
host = os.getenv('DB_HOST', '127.0.0.1')
db = os.getenv('DB_NAME', 'coincee')
driver = os.getenv('DB_DRIVER', 'pymysql')
url = f'mysql+{driver}://{user}:{quote_plus(pw)}@{host}/{db}'

try:
    engine = create_engine(url, pool_pre_ping=True)
    with engine.connect() as conn:
        r = conn.execute(text('SELECT 1')).first()
        print(f'SUCCESS: {r[0]}')
except Exception as e:
    print(f'FAILED: {type(e).__name__}: {str(e)[:300]}')
"
