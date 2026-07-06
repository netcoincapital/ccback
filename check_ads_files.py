#!/usr/bin/env python3
"""Check ads files on server."""
import os, sys
sys.path.insert(0, '/opt/coinceeper/CC')

print("=== Files in uploads/ads/ ===")
for f in os.listdir('/opt/coinceeper/CC/uploads/ads/'):
    fp = os.path.join('/opt/coinceeper/CC/uploads/ads/', f)
    print(f"  {f}: {os.path.getsize(fp)} bytes")

print("\n=== DB Record ===")
from database import SessionLocal, Ads
s = SessionLocal()
ads = s.query(Ads).all()
for a in ads:
    print(f"  id={a.id}, title={a.title}, image_url={a.image_url}")
s.close()

print("\n=== File exists at DB path? ===")
a = SessionLocal().query(Ads).first()
if a:
    path = '/opt/coinceeper/CC' + a.image_url
    print(f"  Full path: {path}")
    print(f"  Exists: {os.path.exists(path)}")
