import sys, os
# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from database import SessionLocal, UserDevices
s = SessionLocal()
devices = s.query(UserDevices).limit(10).all()
for d in devices:
    token_preview = (d.DeviceToken[:60] + '...') if len(d.DeviceToken) > 60 else d.DeviceToken
    print(f"ID={d.DeviceID} UserID={d.UserID} WalletID={d.WalletID} Token={token_preview}")
print(f"Total registered devices: {s.query(UserDevices).count()}")
s.close()
