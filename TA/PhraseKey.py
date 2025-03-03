from flask import Blueprint, jsonify, request
from datetime import datetime

from database import SessionLocal
from security.validators import InputValidator, SecurityUtils, ValidationError
from services.wallet_service import WalletService
from utils.error_handlers import handle_api_errors
from utils.logging_config import get_logger
from schemas import (
    PhraseKeyRequest,
    PhraseKeyResponse,
    ErrorResponse
)

# Configure logging
logger = get_logger(__file__)
logger.info("Initializing phrase key module")

# تعریف Blueprint
phrase_key_bp = Blueprint('phrase_key', __name__)

# مسیر برای دریافت Phrase Key
@phrase_key_bp.route('/get_phrase_key', methods=['POST'])
@SecurityUtils.rate_limit(requests=3, window=300)  # 3 درخواست در 5 دقیقه
@handle_api_errors
def get_phrase_key():
    """
    Get recovery phrase key
    ---
    tags:
      - Wallet
    requestBody:
      required: true
      content:
        application/json:
          schema:
            $ref: '#/components/schemas/PhraseKeyRequest'
    responses:
      200:
        description: Recovery phrase key retrieved successfully
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/PhraseKeyResponse'
      400:
        description: Invalid input data
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/ErrorResponse'
      429:
        description: Rate limit exceeded
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/ErrorResponse'
    """
    session = SessionLocal()
    try:
        data = request.get_json()
        if not data:
            logger.warning("Invalid request data in get_phrase_key")
            raise ValidationError("Invalid request data")

        user_id = InputValidator.validate_uuid(
            data.get('UserID', ''),
            "UserID"
        )
        
        logger.debug(f"Retrieving phrase key for user: {user_id}")
        wallet_service = WalletService(session)
        phrase_key = wallet_service.get_phrase_key(user_id)
        
        logger.info(f"Successfully retrieved phrase key for user: {user_id}")
        return jsonify({
            'phrase_key': phrase_key,
            'success': True
        }), 200

    except ValidationError as e:
        logger.warning(f"Validation error in get_phrase_key: {str(e)}")
        raise
    except Exception as e:
        logger.error(f"Error in get_phrase_key: {str(e)}", exc_info=True)
        raise
    finally:
        session.close()