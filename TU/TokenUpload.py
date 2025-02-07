import os
import sys
import csv
import logging
from datetime import datetime, timezone

# تنظیم لاگینگ
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# افزودن مسیر پروژه به sys.path برای وارد کردن ماژول database
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from database.Currencies import Currencies
from database import SessionLocal

# مسیر فایل CSV (در همان پوشه فایل Python)
CSV_FILE_PATH = os.path.join(os.path.dirname(__file__), 'tokens_with_contracts.csv')

# تابع برای بررسی و اضافه کردن اطلاعات از فایل CSV به جدول
def process_csv_and_insert_to_db():
    logging.info("Starting the process of inserting data from CSV to the database.")
    session = SessionLocal()
    try:
        if not os.path.exists(CSV_FILE_PATH):
            logging.error(f"CSV file not found at path: {CSV_FILE_PATH}")
            return

        with open(CSV_FILE_PATH, mode='r', encoding='utf-8') as file:
            csv_reader = csv.DictReader(file)

            for row_number, row in enumerate(csv_reader, start=1):
                try:
                    # بررسی وجود ستون‌های موردنیاز در سطر
                    required_keys = ['Name', 'Platform', 'Symbol', 'ContractAddress']
                    if not all(key in row for key in required_keys):
                        logging.warning(f"Row {row_number} skipped: Missing required keys.")
                        continue

                    # بررسی وجود اطلاعات در دیتابیس با استفاده از CurrencyID و SmartContractAddress
                    currency_id = row['Symbol'].strip().upper()

                    if session.query(Currencies).filter_by(CurrencyID=currency_id).first():
                        logging.info(f"Row {row_number}: CurrencyID {currency_id} already exists. Skipping.")
                        continue

                    if session.query(Currencies).filter_by(SmartContractAddress=row['ContractAddress']).first():
                        logging.info(f"Row {row_number}: SmartContractAddress {row['ContractAddress']} already exists. Skipping.")
                        continue

                    # تبدیل مقدار Platform به عدد یا مقدار مشخص برای Ethereum
                    if row['Platform'] == 'Ethereum':
                        blockchain_id = 1
                    else:
                        try:
                            blockchain_id = int(row['Platform'])
                        except ValueError:
                            logging.warning(f"Row {row_number}: Invalid Platform value '{row['Platform']}'. Setting BlockchainID to 0.")
                            blockchain_id = 0

                    # ایجاد یک شی جدید برای جدول Currencies
                    new_currency = Currencies(
                        CurrencyID=currency_id,  # مقدار Symbol به عنوان CurrencyID استفاده می‌شود
                        CurrencyName=row['Name'],
                        Icon=None,  # مقدار Icon به صورت null تنظیم شده است
                        Symbol=row['Symbol'],
                        BlockchainID=blockchain_id,  # مقدار تبدیل شده یا پیش‌فرض
                        DecimalPlaces=18,  # مقدار DecimalPlaces به صورت پیش‌فرض 18 است
                        IsToken=1,  # مقدار IsToken به صورت پیش‌فرض 1 است
                        SmartContractAddress=row['ContractAddress'],
                        CreatedAt=datetime.now(timezone.utc),
                        UpdatedAt=datetime.now(timezone.utc)
                    )

                    # اضافه کردن شی جدید به سشن
                    session.add(new_currency)
                    session.commit()

                except Exception as row_error:
                    logging.error(f"Error processing row {row_number}: {row_error}")
                    session.rollback()

    except Exception as e:
        session.rollback()
        logging.error(f"An error occurred during the process: {e}")
    finally:
        session.close()
        logging.info("Database session closed.")

if __name__ == "__main__":
    process_csv_and_insert_to_db()
