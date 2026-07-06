import uuid, os, shutil, sys
sys.path.insert(0, '/opt/coinceeper/CC')
from database import SessionLocal, Ads

new_name = uuid.uuid4().hex + '.png'
src = '/opt/coinceeper/CC/uploads/ads/1.png'
dst = '/opt/coinceeper/CC/uploads/ads/' + new_name

shutil.copy2(src, dst)
print('New file: ' + new_name + ' (' + str(os.path.getsize(dst)) + ' bytes)')

s = SessionLocal()
a = s.query(Ads).first()
old_url = a.image_url
a.image_url = '/uploads/ads/' + new_name
s.commit()
s.close()

old_name = old_url.split('/')[-1]
old_path = '/opt/coinceeper/CC/uploads/ads/' + old_name
if os.path.exists(old_path):
    os.remove(old_path)
    print('Deleted old: ' + old_name)
os.remove(src)
print('Deleted temp 1.png')
print('Done - new URL: /uploads/ads/' + new_name)
