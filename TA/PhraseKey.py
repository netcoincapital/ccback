from flask import Blueprint, jsonify, request
import logging
from datetime import datetime

from database import SessionLocal
from security.validators import InputValidator, SecurityUtils, ValidationError
from services.wallet_service import WalletService
from utils.error_handlers import handle_api_errors

# تعریف Blueprint
phrase_key_bp = Blueprint('phrase_key', __name__)

# مسیر برای دریافت Phrase Key
@phrase_key_bp.route('/get_phrase_key', methods=['POST'])
@SecurityUtils.rate_limit(requests=3, window=300)  # 3 درخواست در 5 دقیقه
@handle_api_errors
def get_phrase_key():
    """دریافت کلید عبارت بازیابی"""
    session = SessionLocal()
    try:
        data = request.get_json()
        if not data:
            raise ValidationError("Invalid request data")

        user_id = InputValidator.validate_uuid(
            data.get('UserID', ''),
            "UserID"
        )

        wallet_service = WalletService(session)
        phrase_key = wallet_service.get_phrase_key(user_id)

        return jsonify({
            'phrase_key': phrase_key,
            'success': True
        }), 200

    finally:
        session.close()