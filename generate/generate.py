from flask import Blueprint, jsonify, request
import logging
from datetime import datetime
import os
import uuid
import json

from database import SessionLocal
from security.validators import InputValidator, SecurityUtils, ValidationError
from services.wallet_service import WalletService
from utils.error_handlers import handle_api_errors
from schemas import (
    WalletGenerationRequest, 
    WalletGenerationResponse,
    ErrorResponse
)
from utils.logging_config import get_logger

# Configure logging
logger = get_logger(__file__)
logger.info("Initializing wallet generation module")

generate_bp = Blueprint('generate_wallet', __name__)

@generate_bp.route('/generate-wallet', methods=['POST'])
@SecurityUtils.rate_limit(requests=3, window=300)
@handle_api_errors
def generate_wallet():
    """
    Generate a new wallet
    ---
    tags:
      - Wallet Management
    requestBody:
      required: true
      content:
        application/json:
          schema:
            $ref: '#/components/schemas/WalletGenerationRequest'
    responses:
      201:
        description: Wallet generated successfully
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/WalletGenerationResponse'
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

        # Validate wallet name - check both camelCase and PascalCase versions
        wallet_name = data.get('WalletName', data.get('walletName', ''))
        
        wallet_name = InputValidator.validate_string(
            wallet_name,
            "WalletName",
            min_length=3,
            max_length=50,
            pattern=r'^[a-zA-Z0-9_\- ]+$'
        )
        
        # Generate wallet synchronously
        session = SessionLocal()
        try:
            # Use service to create wallet
            wallet_service = WalletService(session)
            with session.begin():
                user_id, mnemonic, addresses = wallet_service.create_wallet(wallet_name)

            # Log success
            logger.info(f"Wallet generated for user {user_id}")

            return jsonify({
                'UserID': user_id,
                'Mnemonic': mnemonic,
                'Addresses': addresses,
                'success': True
            }), 201
        finally:
            session.close()

    except Exception as e:
        logger.error(f"Error in generate_wallet: {str(e)}")
        raise
