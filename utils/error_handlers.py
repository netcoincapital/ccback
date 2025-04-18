from flask import Blueprint, jsonify, request
import os
from typing import Tuple, Dict, Any
from functools import wraps
import traceback
from sqlalchemy.exc import SQLAlchemyError, OperationalError, DisconnectionError, TimeoutError, InvalidRequestError, NoSuchModuleError

from database import SessionLocal
from security.validators import InputValidator, SecurityUtils, ValidationError
# Removing the circular import
# from services.wallet_service import WalletService

# Import proper logging configuration
from utils.logging_config import get_logger

# Create a dedicated logger for error handling
logger = get_logger(__file__)
logger.info("Initializing error handling module")

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
            logger.warning(f"Validation error from {request.remote_addr}: {str(e)}")
            return {
                "success": False,
                "error_type": "validation_error",
                "message": str(e)
            }, 400

        elif isinstance(e, PermissionError):
            # خطاهای مربوط به دسترسی
            logger.error(f"Permission error: {str(e)}")
            return {
                "success": False,
                "error_type": "permission_error",
                "message": "You don't have permission to perform this action"
            }, 403
            
        elif isinstance(e, (OperationalError, DisconnectionError, TimeoutError, NoSuchModuleError)):
            # خطاهای مربوط به دیتابیس
            logger.error(f"Database connection error: {str(e)}", exc_info=True)
            return {
                "success": False,
                "error_type": "database_error",
                "message": "Database connection error. Please try again later."
            }, 503
            
        elif isinstance(e, InvalidRequestError):
            # خطاهای درخواست نامعتبر SQLAlchemy
            logger.error(f"Invalid SQLAlchemy request: {str(e)}", exc_info=True)
            return {
                "success": False,
                "error_type": "invalid_request",
                "message": "Invalid database request"
            }, 500
            
        elif isinstance(e, SQLAlchemyError):
            # سایر خطاهای پایگاه داده
            logger.error(f"Database error: {str(e)}", exc_info=True)
            return {
                "success": False,
                "error_type": "database_error",
                "message": "A database error occurred. Please try again later."
            }, 500

        else:
            # سایر خطاهای پیش‌بینی نشده
            logger.error(f"Unexpected error: {str(e)}", exc_info=True)
            logger.error(f"Error traceback: {traceback.format_exc()}")
            
            # Check if in development mode
            is_development = os.environ.get('FLASK_ENV') == 'development'
            
            if is_development:
                # در محیط توسعه، جزئیات خطا را نشان بده
                error_details = traceback.format_exc()
                return {
                    "success": False,
                    "error_type": "internal_error",
                    "message": "Internal server error",
                    "debug_info": {
                        "error": str(e),
                        "traceback": error_details
                    }
                }, 500
            else:
                # در محیط تولید، فقط پیام کلی خطا را نشان بده
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
            logger.error(f"Error in {f.__name__}: {str(e)}", exc_info=True)
            error_data, status_code = APIErrorHandler.handle_error(e, request)
            return jsonify(error_data), status_code
    return decorated_function
