from flask import Blueprint, jsonify, request
import logging
from datetime import datetime
import os

from database import SessionLocal
from security.validators import InputValidator, SecurityUtils, ValidationError
from services.wallet_service import WalletService
from utils.error_handlers import handle_api_errors
from utils.logging_config import get_logger
from schemas import (
    WalletImportRequest,
    WalletImportResponse,
    ErrorResponse
)

# Configure logging
logger = get_logger(__file__)
logger.info("Initializing wallet import module")

import_bp = Blueprint('import_bp', __name__)

@import_bp.route('/import_wallet', methods=['POST'])
@SecurityUtils.rate_limit(requests=5, window=300)
@handle_api_errors
def import_wallet():
    """
    Import wallet using recovery phrase
    ---
    tags:
      - Wallet Management
    requestBody:
      required: true
      content:
        application/json:
          schema:
            $ref: '#/components/schemas/WalletImportRequest'
    responses:
      200:
        description: Wallet imported successfully
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/WalletImportResponse'
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
    try:
        data = request.get_json()
        if not data:
            raise ValidationError("Invalid request data")

        # Validate mnemonic phrase
        mnemonic = InputValidator.validate_string(
            data.get('mnemonic', ''),
            "Mnemonic",
            min_length=12,
            max_length=1000,
            pattern=r'^[a-zA-Z ]+$'
        )

        # Check mnemonic word count
        mnemonic_words = mnemonic.split()
        if len(mnemonic_words) not in [12, 18, 24]:
            raise ValidationError("Mnemonic must contain 12, 18, or 24 words")

        # Import the wallet
        session = SessionLocal()
        try:
            # Use service to import wallet
            wallet_service = WalletService(session)
            with session.begin():
                wallet_id, addresses = wallet_service.import_wallet(mnemonic)

            # Log success (without sensitive information)
            logger.info(f"Wallet imported successfully with ID: {wallet_id}")

            return jsonify({
                'WalletID': wallet_id,
                'Addresses': addresses,
                'success': True
            }), 200
        finally:
            session.close()

    except ValidationError as e:
        # Log validation error
        logger.warning(f"Validation error in import_wallet: {str(e)}")
        raise
    except Exception as e:
        # Log other errors
        logger.error(f"Error in import_wallet: {str(e)}", exc_info=True)
        raise