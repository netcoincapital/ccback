#!/usr/bin/env python3
"""
اسکریپت ریست کردن شبیه‌ساز قیمت NCC
این اسکریپت همه قیمت‌های NCC (8517 و 8519) را حذف کرده و از 22 سنت شروع می‌کند
با الگوریتم طبیعی جدید که در 9 ماه به 80 سنت می‌رسد
"""

import sys
import os

# اضافه کردن مسیر اصلی پروژه به sys.path
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(current_dir)

from utils.price_simulator.NCCPRICE import reset_price_simulator, init_ncc
from utils.logging_config import get_logger

# تنظیم لاگر
logger = get_logger(__file__)

def main():
    """
    تابع اصلی برای ریست کردن شبیه‌ساز NCC
    """
    logger.info("==================== شروع ریست شبیه‌ساز قیمت NCC ====================")
    
    try:
        # مقداردهی اولیه NCC
        if not init_ncc():
            logger.error("❌ مقداردهی اولیه NCC با شکست مواجه شد")
            return False
        
        # ریست کردن شبیه‌ساز
        if reset_price_simulator():
            logger.info("✅ شبیه‌ساز قیمت NCC با موفقیت ریست شد")
            logger.info("🎯 هر دو توکن NCC (8517 و 8519) حالا قیمت 22 سنت ($0.22) دارند")
            logger.info("🚀 الگوریتم طبیعی با نوسانات شروع شد - هدف 80 سنت در 9 ماه")
            return True
        else:
            logger.error("❌ خطا در ریست کردن شبیه‌ساز قیمت NCC")
            return False
            
    except Exception as e:
        logger.error(f"❌ خطای غیرمنتظره: {str(e)}")
        return False
    finally:
        logger.info("==================== پایان ریست شبیه‌ساز قیمت NCC ====================")

if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1) 