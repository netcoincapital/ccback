#!/usr/bin/env python3
"""
سرویس آپدیت نرخ ارزهای فیات
این اسکریپت روزانه نرخ تبدیل USD به سایر ارزها را از API دریافت و در دیتابیس ذخیره می‌کند
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import requests
import logging
from datetime import datetime
from sqlalchemy import text
from database import engine
from utils.logging_config import get_logger

logger = get_logger(__file__)

FIAT_CURRENCIES = [
    'USD', 'EUR', 'GBP', 'JPY', 'CNY', 'KRW', 'RUB', 'TRY', 
    'INR', 'BRL', 'AUD', 'CAD', 'CHF', 'MXN', 'AED', 'IRR'
]

def get_exchange_rates_from_api():
    """
    دریافت نرخ ارز از API
    """
    try:
        url = "https://api.exchangerate-api.com/v4/latest/USD"
        
        logger.info(f"Fetching exchange rates from: {url}")
        response = requests.get(url, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            rates = data.get('rates', {})
            logger.info(f"Successfully fetched {len(rates)} exchange rates")
            return rates
        else:
            logger.error(f"API returned status code: {response.status_code}")
            return None
            
    except Exception as e:
        logger.error(f"Error fetching exchange rates: {str(e)}", exc_info=True)
        return None

def update_fiat_rates_in_db(rates):
    """
    آپدیت نرخ ارزها در دیتابیس
    """
    if not rates:
        logger.warning("No rates to update")
        return False
    
    try:
        with engine.connect() as conn:
            updated_count = 0
            
            for currency in FIAT_CURRENCIES:
                if currency == 'USD':
                    rate = 1.0
                elif currency in rates:
                    rate = rates[currency]
                else:
                    logger.warning(f"Rate for {currency} not found in API response")
                    continue
                
                sql = text("""
                    INSERT INTO fiat_rates (base_currency, quote_currency, rate, last_updated)
                    VALUES ('USD', :currency, :rate, :updated)
                    ON DUPLICATE KEY UPDATE
                        rate = VALUES(rate),
                        last_updated = VALUES(last_updated)
                """)
                
                conn.execute(sql, {
                    'currency': currency,
                    'rate': rate,
                    'updated': datetime.now()
                })
                
                updated_count += 1
                logger.debug(f"Updated {currency}: {rate}")
            
            conn.commit()
            logger.info(f"✓ Successfully updated {updated_count} fiat rates")
            return True
            
    except Exception as e:
        logger.error(f"Error updating fiat rates in database: {str(e)}", exc_info=True)
        return False

def verify_rates():
    """
    نمایش نرخ‌های به‌روزرسانی شده
    """
    try:
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT quote_currency, rate, last_updated 
                FROM fiat_rates 
                ORDER BY quote_currency
            """))
            
            logger.info("Current fiat rates in database:")
            for row in result:
                logger.info(f"  {row[0]}: {row[1]:.8f} (updated: {row[2]})")
                
    except Exception as e:
        logger.error(f"Error verifying rates: {str(e)}")

def main():
    """
    تابع اصلی
    """
    logger.info("=" * 60)
    logger.info("Starting Fiat Rate Update Service")
    logger.info("=" * 60)
    
    rates = get_exchange_rates_from_api()
    
    if rates:
        success = update_fiat_rates_in_db(rates)
        
        if success:
            verify_rates()
            logger.info("✓ Fiat rates update completed successfully")
            return 0
        else:
            logger.error("✗ Failed to update fiat rates in database")
            return 1
    else:
        logger.error("✗ Failed to fetch exchange rates from API")
        return 1

if __name__ == '__main__':
    import sys
    sys.exit(main())

