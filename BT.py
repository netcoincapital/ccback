import time
import requests
from database import SessionLocal
from database.wallets import Wallets

def main():
    # ایجاد Session برای ارتباط با دیتابیس
    session = SessionLocal()

    try:
        # واکشی تمام UserIDهای یکتا از جدول Wallets
        user_records = session.query(Wallets.UserID).distinct().all()
        user_ids = [row[0] for row in user_records]

        chunk_size = 15  # در هر دسته 15 کاربر
        url = "http://127.0.0.1:5000/balance"  # روتی که می‌خواهید تست کنید

        for i in range(0, len(user_ids), chunk_size):
            # گرفتن 15 UserID در هر بخش
            current_batch = user_ids[i : i + chunk_size]

            print(f"Sending batch {i // chunk_size + 1} to /balance ...")

            # ارسال درخواست برای هر UserID در این دسته
            for uid in current_batch:
                payload = {"UserID": uid}
                try:
                    response = requests.post(url, json=payload, timeout=10)
                    if response.status_code == 200:
                        print(f"  [OK] Balance request for UserID={uid}")
                    else:
                        print(f"  [ERR] UserID={uid} => {response.status_code} - {response.text}")
                except Exception as e:
                    print(f"  [EXC] Error for UserID={uid} => {str(e)}")

            # تا زمانی که به آخرین گروه نرسیدیم، 60 ثانیه صبر می‌کنیم
            if i + chunk_size < len(user_ids):
                print("Waiting 60 seconds before sending the next batch...")
                time.sleep(60)

    finally:
        session.close()

if __name__ == "__main__":
    main()
