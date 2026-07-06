#!/usr/bin/env python3
"""Check server status: database, files, and service."""
import os, sys
from sqlalchemy import create_engine, inspect, text
from urllib.parse import quote_plus

os.chdir('/opt/coinceeper/CC')

# Load env
env = {}
with open('.env') as f:
    for line in f:
        line = line.strip()
        if line and not line.startswith('#') and '=' in line:
            k, v = line.split('=', 1)
            env[k.strip()] = v.strip()

DB_USER = env.get('DB_USER', 'coincee')
DB_PASSWORD = quote_plus(env.get('DB_PASSWORD', ''))
DB_HOST = env.get('DB_HOST', '127.0.0.1')
DB_NAME = env.get('DB_NAME', 'coincee')

print('=== SERVER STATUS CHECK ===')
print()

# System
import subprocess
print('--- Uptime ---')
subprocess.run(['uptime'])
print()

print('--- Disk ---')
subprocess.run(['df', '-h', '/'])
print()

print('--- Memory ---')
subprocess.run(['free', '-h'])
print()

# Service
print('--- Service ---')
r = subprocess.run(['systemctl', 'is-active', 'coinceeper-api'], capture_output=True, text=True)
print(f'coinceeper-api: {r.stdout.strip()}')
print()

# MySQL
print('--- MySQL ---')
try:
    r = subprocess.run(['systemctl', 'is-active', 'mysql'], capture_output=True, text=True)
    print(f'mysql: {r.stdout.strip()}')
except:
    print('mysql: service not found')
print()

# Database tables
print('--- Database ---')
try:
    engine = create_engine(f'mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}/{DB_NAME}')
    with engine.connect() as conn:
        r = conn.execute(text('SELECT DATABASE()'))
        db_name = r.scalar()
        print(f'Connected to: {db_name}')
        
        insp = inspect(engine)
        tables = insp.get_table_names()
        print(f'Tables ({len(tables)}): {", ".join(tables)}')
        print(f'ads table exists: {"ads" in tables}')
        
        if 'ads' in tables:
            cols = [c['name'] for c in insp.get_columns('ads')]
            print(f'ads columns: {", ".join(cols)}')
            
            r = conn.execute(text('SELECT COUNT(*) FROM ads'))
            count = r.scalar()
            print(f'ads records: {count}')
except Exception as e:
    print(f'DB Error: {e}')
print()

# Check files
print('--- Files ---')
for path in ['api/ads_api.py', 'database/ads.py', 'database/__init__.py', 'uploads/ads']:
    full = f'/opt/coinceeper/CC/{path}'
    if os.path.exists(full):
        print(f'OK: {path}')
    else:
        print(f'MISSING: {path}')

print()
print('=== DONE ===')
