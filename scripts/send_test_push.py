import sys
import os

sys.path.insert(0, '/opt/coinceeper/CC')
sys.path.insert(0, '/opt/coinceeper')
os.chdir('/opt/coinceeper/CC')

from config.firebase import send_notification, initialize_firebase, firebase_initialized

print("Firebase already initialized:", firebase_initialized)
if not firebase_initialized:
    ok = initialize_firebase()
    print("Firebase init result:", ok)

token = 'f0lh9BMOQgaymAEk8DGsGP:APA91bGhOH-L-DHF_fYoXe7oPX089jBKXdf3VKGxXp__sj8wu_bMZVY8QCtcexC_apzLsZdCmlROeWMEre5nTKo-4tL9GBryP6-oyXoAZs0uHbfGW0ZdG6M'
result = send_notification(
    token=token,
    title='Coinceeper Test',
    body='This is a test push notification from server',
    data={'type': 'test', 'timestamp': '2026-06-02'},
    priority='high'
)
print('Send result:', result)
