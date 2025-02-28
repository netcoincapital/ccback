from flask import Blueprint, jsonify, request
import logging
from datetime import datetime
import os

from database import SessionLocal
from security.validators import InputValidator, SecurityUtils, ValidationError
from services.wallet_service import WalletService
from utils.error_handlers import handle_api_errors

# تنظیمات لاگ
LOG_DIR = "Log"
os.makedirs(LOG_DIR, exist_ok=True)
log_file = os.path.join(LOG_DIR, f"generate_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.log")

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler()
    ]
)

generate_bp = Blueprint('generate_wallet', __name__)

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
