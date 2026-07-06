#!/usr/bin/env python3
"""Update ad image_url to clean path."""
import sys
sys.path.insert(0, '/opt/coinceeper/CC')

from database import SessionLocal, Ads

s = SessionLocal()
try:
    a = s.query(Ads).first()
    if a:
        a.image_url = "/uploads/ads/1.png"
        s.commit()
        print(f"Updated: id={a.id}, title='{a.title}', image_url='{a.image_url}'")
    else:
        print("No ads found in database")
finally:
    s.close()
