#!/usr/bin/env python3
"""Replace ad image with a new UUID filename to bust Cloudflare cache."""
import uuid
import shutil
import sys
sys.path.insert(0, '/opt/coinceeper/CC')

from database import SessionLocal, Ads

new_name = uuid.uuid4().hex + '.png'
src = '/opt/coinceeper/CC/uploads/ads/1.png'
dst = f'/opt/coinceeper/CC/uploads/ads/{new_name}'

shutil.copy2(src, dst)
print(f'New file created: {new_name}')

s = SessionLocal()
try:
    a = s.query(Ads).first()
    if a:
        a.image_url = f'/uploads/ads/{new_name}'
        s.commit()
        print(f'DB updated: id={a.id}, image_url={a.image_url}')
    else:
        print('No ads found')
finally:
    s.close()

# Delete the old 1.png
import os
if os.path.exists(src):
    os.remove(src)
    print(f'Old file deleted: 1.png')
