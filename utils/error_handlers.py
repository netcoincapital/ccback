from flask import Blueprint, jsonify, request
import logging
from datetime import datetime
import os
from typing import Tuple, Dict, Any
from functools import wraps

from database import SessionLocal
from security.validators import InputValidator, SecurityUtils, ValidationError
# Removing the circular import
# from services.wallet_service import WalletService

# تنظیمات لاگ
LOG_DIR = "Log"
os.makedirs(LOG_DIR, exist_ok=True)
log_file = os.path.join(LOG_DIR, f"{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.log")

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler()
    ]
)

class APIErrorHandler:
    """کلاس مدیریت یکپارچه خطاها در API"""

    @staticmethod
    def handle_error(e: Exception, request) -> Tuple[Dict[str, Any], int]:
        """
        مدیریت یکپارچه خطاها و تولید پاسخ مناسب
        """
        if isinstance(e, ValidationError):
            # ثبت تلاش ناموفق برای خطاهای اعتبارسنجی
            SecurityUtils.log_failed_attempt(
                request.remote_addr,
                request.endpoint,
                str(e)
            )
            return {
                "success": False,
                "error_type": "validation_error",
                "message": str(e)
            }, 400

        elif isinstance(e, PermissionError):
            # خطاهای مربوط به دسترسی
            logging.error(f"Permission error: {str(e)}")
            return {
                "success": False,
                "error_type": "permission_error",
                "message": "You don't have permission to perform this action"
            }, 403

        else:
            # سایر خطاهای پیش‌بینی نشده
            logging.error(f"Unexpected error: {str(e)}", exc_info=True)
            return {
                "success": False,
                "error_type": "internal_error",
                "message": "Internal server error"
            }, 500

    @staticmethod
    def create_error_response(error_data: Dict[str, Any], status_code: int):
        """
        ایجاد پاسخ خطای یکپارچه
        """
        return jsonify(error_data), status_code

def handle_api_errors(f):
    """دکوراتور برای مدیریت خطاهای API"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except Exception as e:
            error_data, status_code = APIErrorHandler.handle_error(e, request)
            return jsonify(error_data), status_code
    return decorated_function
