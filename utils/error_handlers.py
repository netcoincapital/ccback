from flask import Blueprint, jsonify, request
import logging
from datetime import datetime
import os
from typing import Tuple, Dict, Any
from functools import wraps

from database import SessionLocal
from security.validators import InputValidator, SecurityUtils, ValidationError
from services.wallet_service import WalletService
from utils.error_handlers import handle_api_errors

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

generate_bp = Blueprint('generate_wallet', __name__)

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
            }, e.status_code

        elif isinstance(e, PermissionError):
            # خطاهای مربوط به دسترسی
            logging.error(f"Permission error: {str(e)}")
            return {
                "success": False,
                "error_type": "permission_error",
                "message": "You don't have permission to perform this action"
            }, 403

        elif isinstance(e, ValueError):
            # خطاهای مربوط به مقادیر نامعتبر
            logging.error(f"Value error: {str(e)}")
            return {
                "success": False,
                "error_type": "value_error",
                "message": str(e)
            }, 400

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
            return APIErrorHandler.create_error_response(error_data, status_code)
    return decorated_function

@generate_bp.route('/generate-wallet', methods=['POST'])
@SecurityUtils.rate_limit(requests=3, window=300)
@handle_api_errors
def generate_wallet():
    """ایجاد کیف پول جدید"""
    session = SessionLocal()
    try:
        data = request.get_json()
        if not data:
            raise ValidationError("Invalid request data")

        # اعتبارسنجی نام کیف پول
        wallet_name = InputValidator.validate_string(
            data.get('WalletName', ''),
            "WalletName",
            min_length=3,
            max_length=50,
            pattern=r'^[a-zA-Z0-9_\- ]+$'
        )

        # استفاده از سرویس برای ایجاد کیف پول
        wallet_service = WalletService(session)
        with session.begin():
            user_id, mnemonic, addresses = wallet_service.create_wallet(wallet_name)

        return jsonify({
            'UserID': user_id,
            'Mnemonic': mnemonic,
            'Addresses': addresses,
            'success': True
        }), 201

    finally:
        session.close()
