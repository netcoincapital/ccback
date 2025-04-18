import os
import sys
import csv
import logging
from datetime import datetime, timezone

# تنظیم لاگینگ
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# افزودن مسیر پروژه به sys.path برای وارد کردن ماژول‌های لازم
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from database.Currencies import Currencies
from database import SessionLocal

# مسیر فایل CSV
CSV_FILE_PATH = os.path.join(os.path.dirname(__file__), 'cryptocurrencies.csv')

# دیکشنری تعیین شناسه برای کارنسی‌های اصلی
+ = {
    "Bitcoin": 1,
    "Ethreum": 2,
    "BNB": 3,
    "NCC": 4,
    "Polygon": 5,
    "Tron": 6,
    "Solona": 7,
    "Polkadot": 8,
    "Avalanche": 9,
    "XRP": 10,
    "USDT": 11,
    "Arbitrom": 12,
    "DOGE": 13,
    "SHIB": 14
}

# دیکشنری تعیین BlockchainID ها
PLATFORM_MAP = {
    "ETH": 1,
    "TRX": 2,
    "BNB": 3,
    "BTC": 4,
    "MATIC": 5,
    "ARB": 6,
    "XRP": 11,
    "SOL": 12,
    "AVAX": 13,
    "DOT": 14
}

def process_csv_and_insert_to_db():
    logging.info("Starting the process of inserting data from CSV to the database.")
    session = SessionLocal()

    # شمارندهٔ شناسه‌ها برای کارنسی‌هایی که در TOP_CURRENCIES تعریف نشده‌اند
    next_id = 15
    assigned_ids = {}

    try:
        if not os.path.exists(CSV_FILE_PATH):
            logging.error(f"CSV file not found at path: {CSV_FILE_PATH}")
            return

        with open(CSV_FILE_PATH, mode='r', encoding='utf-8') as file:
            csv_reader = csv.DictReader(file)

            for row_number, row in enumerate(csv_reader, start=1):
                # Process only rows from 2 to 1006
                if row_number < 5007 or row_number > 6006:
                    continue
                try:
                    # ستون‌های مورد نیاز
                    required_keys = ['Name', 'Symbol', 'Platform', 'ContractAddress', 'Image']
                    if not all(key in row for key in required_keys):
                        logging.warning(f"Row {row_number} skipped: Missing required keys.")
                        continue

                    currency_name = row['Name'].strip()
                    symbol_upper = row['Symbol'].strip().upper()
                    contract_address = row['ContractAddress'].strip()
                    image_name = row['Image'].strip()

                    # تعیین شناسه برای CurrencyID بر اساس اولویت مشخص
                    if currency_name in TOP_CURRENCIES:
                        currency_id_num = TOP_CURRENCIES[currency_name]
                    else:
                        # اگر قبلاً این ارز شناسایی و ID گرفته، همان را استفاده می‌کنیم
                        if currency_name in assigned_ids:
                            currency_id_num = assigned_ids[currency_name]
                        else:
                            currency_id_num = next_id
                            assigned_ids[currency_name] = next_id
                            next_id += 1

                    # تخصیص BlockchainID از دیکشنری PLATFORM_MAP
                    platform_str = row['Platform'].strip()
                    blockchain_id = PLATFORM_MAP.get(platform_str)

                    if not blockchain_id:
                        logging.warning(
                            f"Row {row_number}: Invalid/Unknown Platform '{platform_str}'. Skipping this row."
                        )
                        continue

                    # ساخت مقدار Icon با فرمت موردنظر
                    icon_url = f"https://coinceeper.com/CC/cryptoicons/{image_name}"

                    # ساخت شی جدید برای درج در دیتابیس
                    new_currency = Currencies(
                        CurrencyID=str(currency_id_num),
                        CurrencyName=currency_name,
                        Icon=icon_url,
                        Symbol=symbol_upper,
                        BlockchainID=blockchain_id,
                        DecimalPlaces=18,  # پیش‌فرض ۱۸
                        IsToken=True,      # پیش‌فرض True
                        SmartContractAddress=contract_address if contract_address else None,
                        CreatedAt=datetime.now(timezone.utc),
                        UpdatedAt=datetime.now(timezone.utc)
                    )

                    # درج یا به‌روزرسانی در دیتابیس
                    session.merge(new_currency)
                    session.commit()

                    logging.info(f"Row {row_number}: Inserted '{currency_name}' with CurrencyID {currency_id_num}")

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
