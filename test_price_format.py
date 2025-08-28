#!/usr/bin/env python3
import os
import sys

# Set environment variables
os.environ['DB_USER'] = 'coincee'
os.environ['DB_PASSWORD'] = '09387270277Mn!!??'
os.environ['DB_HOST'] = '127.0.0.1'
os.environ['DB_NAME'] = 'coincee'

sys.path.insert(0, os.getcwd())

from Currencies.currency_price_service import dynamic_decimal_format

# تست فرمت کردن قیمت‌های مختلف
test_prices = [
    0.0,
    0.00002345,  # SHIB price example
    0.000000012,  # Very small price
    0.0001,
    0.01,
    1.5,
    1234.56
]

print("Testing price formatting:")
for price in test_prices:
    formatted = dynamic_decimal_format(price)
    print(f"Price: {price:e} -> Formatted: {formatted}")

# تست دیتابیس برای SHIB
try:
    from database import engine
    from sqlalchemy.orm import Session
    from database.prices import Price
    
    session = Session(bind=engine)
    
    # بررسی قیمت SHIB در دیتابیس
    shib_price = session.query(Price).filter(
        Price.crypto_id == '27',  # SHIB ID from SQL
        Price.currency == 'USD'
    ).first()
    
    if shib_price:
        print(f"\nSHIB price in database: {shib_price.price}")
        print(f"SHIB change_24h: {shib_price.change_24h}")
    else:
        print("\nNo SHIB price found in database")
    
    session.close()
    
except Exception as e:
    print(f"Database error: {e}")
