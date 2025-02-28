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
log_file = os.path.join(LOG_DIR, f"import_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.log")

logging.basicConfig(level=logging.DEBUG)

import_bp = Blueprint('import_bp', __name__)

@import_bp.route('/import_wallet', methods=['POST'])
@SecurityUtils.rate_limit(requests=5, window=300)
@handle_api_errors
def import_wallet():
    """وارد کردن کیف پول با استفاده از عبارت بازیابی"""
    session = SessionLocal()
    try:
        data = request.get_json()
        if not data:
            raise ValidationError("Invalid request data")

        # اعتبارسنجی عبارت بازیابی
        mnemonic = InputValidator.validate_string(
            data.get('mnemonic', ''),
            "Mnemonic",
            min_length=12,
            max_length=1000,
            pattern=r'^[a-zA-Z ]+$'
        )

        # بررسی تعداد کلمات Mnemonic
        mnemonic_words = mnemonic.split()
        if len(mnemonic_words) not in [12, 18, 24]:
            raise ValidationError("تعداد کلمات عبارت بازیابی باید 12، 18 یا 24 باشد.")

        # استفاده از سرویس برای وارد کردن کیف پول
        wallet_service = WalletService(session)
        with session.begin():
            wallet_id, addresses = wallet_service.import_wallet(mnemonic)

        return jsonify({
            'WalletID': wallet_id,
            'Addresses': addresses,
            'success': True
        }), 200

    finally:
        session.close()