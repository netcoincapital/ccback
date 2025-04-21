#!/usr/bin/env python3
"""
اسکریپت برای ایجاد جدول balance_update_log در دیتابیس

این جدول برای جلوگیری از پردازش مجدد تراکنش‌ها استفاده می‌شود
"""

import sys
import os
import logging
from sqlalchemy import text

# اضافه کردن مسیر پروژه به سیستم
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import Base, engine, BalanceUpdateLog, SessionLocal
from utils.logging_config import setup_logging, get_logger

# تنظیم لاگر
setup_logging()
logger = get_logger(__name__)

def create_balance_update_log_table():
    """
    ایجاد جدول balance_update_log در دیتابیس
    """
    try:
        logger.info("Creating balance_update_log table...")
        
        # ایجاد جدول با استفاده از metadata از SQLAlchemy
        BalanceUpdateLog.__table__.create(engine, checkfirst=True)
        
        logger.info("✅ balance_update_log table created successfully")
        
        # بررسی و اضافه کردن محدودیت یکتا اگر وجود ندارد
        session = SessionLocal()
        try:
            # بررسی وجود محدودیت یکتا
            check_constraint = text("""
                SELECT COUNT(*) FROM INFORMATION_SCHEMA.TABLE_CONSTRAINTS 
                WHERE TABLE_NAME = 'balance_update_log' 
                AND CONSTRAINT_NAME = 'uq_wallet_tx_direction' 
                AND CONSTRAINT_TYPE = 'UNIQUE'
            """)
            constraint_exists = session.execute(check_constraint).scalar() > 0
            
            if not constraint_exists:
                logger.info("اضافه کردن محدودیت یکتا به جدول balance_update_log")
                add_constraint = text("""
                    ALTER TABLE balance_update_log 
                    ADD CONSTRAINT uq_wallet_tx_direction 
                    UNIQUE (wallet_id, tx_id, direction)
                """)
                session.execute(add_constraint)
                session.commit()
                logger.info("✅ محدودیت یکتا با موفقیت به جدول balance_update_log اضافه شد")
        except Exception as e:
            logger.warning(f"⚠️ خطا در اضافه کردن محدودیت یکتا: {str(e)}")
            session.rollback()
        finally:
            session.close()
        
        return True
    except Exception as e:
        logger.error(f"❌ Error creating balance_update_log table: {str(e)}")
        return False

if __name__ == "__main__":
    create_balance_update_log_table() 