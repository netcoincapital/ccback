from flask import Blueprint, jsonify, request
import logging
from datetime import datetime

from database import SessionLocal
from security.validators import InputValidator, SecurityUtils, ValidationError
from services.transaction_service import TransactionService
from utils.error_handlers import handle_api_errors

# تعریف Blueprint
receive_bp = Blueprint('receive', __name__)

@receive_bp.route('/Recive', methods=['POST'])
@SecurityUtils.rate_limit(requests=50, window=60)
@handle_api_errors
def receive_transaction():
    """دریافت تراکنش"""
    session = SessionLocal()
    try:
        data = request.get_json()
        if not data:
            raise ValidationError("Invalid request data")

        user_id = InputValidator.validate_uuid(
            data.get('UserID', ''),
            "UserID"
        )
        blockchain = InputValidator.validate_string(
            data.get('BlockchainName', ''),
            "BlockchainName",
            pattern=r'^[a-zA-Z0-9_]+$'
        )

        transaction_service = TransactionService(session)
        transaction = transaction_service.receive_transaction(user_id, blockchain)

        return jsonify({
            'transaction': transaction,
            'success': True
        }), 200

    finally:
        session.close()