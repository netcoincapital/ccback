"""
Script to upload ad image directly to database and file system.
Run: python _upload_ad.py
"""
import os
import sys
import shutil
import uuid

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from database import SessionLocal, Ads
from datetime import datetime

UPLOAD_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads', 'ads')
os.makedirs(UPLOAD_DIR, exist_ok=True)

# Source image
src = os.path.join(os.path.dirname(os.path.abspath(__file__)), '1.png')
if not os.path.exists(src):
    print(f"Error: {src} not found!")
    sys.exit(1)

# Copy with UUID name
ext = 'png'
dest_name = f"{uuid.uuid4().hex}.{ext}"
dest_path = os.path.join(UPLOAD_DIR, dest_name)
shutil.copy2(src, dest_path)
print(f"Image copied to: {dest_path}")

image_url = f"/uploads/ads/{dest_name}"

# Insert into database
session = SessionLocal()
try:
    ad = Ads(
        title="GOLDEN RATIO SYSTEM",
        image_url=image_url,
        backlink="https://coinceeper.com",
        short_desc="سیستم نسبت طلایی",
        is_active=True,
        start_date=datetime.now(),
        end_date=None,
    )
    session.add(ad)
    session.commit()
    session.refresh(ad)
    print(f"Ad created successfully!")
    print(f"  ID: {ad.id}")
    print(f"  Title: {ad.title}")
    print(f"  Image URL: {ad.image_url}")
    print(f"  Backlink: {ad.backlink}")
finally:
    session.close()
