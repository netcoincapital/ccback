from flask import Blueprint, jsonify, request
import logging
from datetime import datetime
import os

from database import SessionLocal, Address
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
            
        # Get user IP and device info
        user_ip = request.remote_addr
        user_device = request.headers.get('User-Agent', 'Unknown Device')
        
        logger.info(f"Import wallet request from IP: {user_ip}, Device: {user_device}")

        # Import the wallet
        session = SessionLocal()
        try:
            # Use service to validate mnemonic first
            wallet_service = WalletService(session)
            
            # Validate mnemonic before importing
            is_valid = wallet_service.validate_mnemonic(mnemonic)
            if not is_valid:
                logger.warning(f"Invalid mnemonic phrase provided")
                return jsonify({
                    'message': 'Invalid mnemonic phrase. Please check your recovery phrase and try again.',
                    'status': 'False'
                }), 400
            
            # If mnemonic is valid, proceed with import
            with session.begin():
                try:
                    wallet_id, user_id, addresses_dict, mnemonic_phrase = wallet_service.import_wallet(mnemonic, user_ip, user_device)
                    
                    # Check if this is an existing wallet or a new one
                    existing_wallet = session.query(Address).filter_by(WalletID=wallet_id).count() > len(addresses_dict)
                    
                    # Log success (without sensitive information)
                    if existing_wallet:
                        logger.info(f"Existing wallet accessed with ID: {wallet_id}")
                        message = "Wallet successfully accessed."
                    else:
                        logger.info(f"New wallet imported with ID: {wallet_id}")
                        message = "Wallet successfully imported."
                    
                    # Convert addresses from dictionary to list of objects
                    addresses_list = []
                    for blockchain_name, public_address in addresses_dict.items():
                        addresses_list.append({
                            'BlockchainName': blockchain_name,
                            'PublicAddress': public_address
                        })
                    
                    return jsonify({
                        'data': {
                            'UserID': user_id,
                            'WalletID': wallet_id,
                            'Mnemonic': mnemonic_phrase,
                            'Addresses': addresses_list
                        },
                        'message': message,
                        'status': 'True'
                    }), 200
                except ValueError as ve:
                    # Handle specific errors from wallet service
                    logger.warning(f"Wallet import failed: {str(ve)}")
                    return jsonify({
                        'message': str(ve),
                        'status': 'False'
                    }), 400
                
        finally:
            session.close()

    except ValidationError as e:
        # Log validation error
        logger.warning(f"Validation error in import_wallet: {str(e)}")
        return jsonify({
            'message': str(e),
            'status': 'False'
        }), 400
    except Exception as e:
        # Log other errors
        logger.error(f"Error in import_wallet: {str(e)}", exc_info=True)
        return jsonify({
            'message': f"An unexpected error occurred: {str(e)}",
            'status': 'False'
        }), 500

@import_bp.route('/validate_mnemonic', methods=['POST'])
@SecurityUtils.rate_limit(requests=10, window=60)
@handle_api_errors
def validate_mnemonic():
    """
    Validate a mnemonic phrase without importing
    ---
    tags:
      - Wallet Management
    requestBody:
      required: true
      content:
        application/json:
          schema:
            $ref: '#/components/schemas/MnemonicValidationRequest'
    responses:
      200:
        description: Mnemonic validation result
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/MnemonicValidationResponse'
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

        # Get mnemonic from request
        mnemonic = data.get('mnemonic', '')
        if not mnemonic:
            raise ValidationError("Mnemonic is required")

        # Check mnemonic word count
        mnemonic_words = mnemonic.split()
        word_count = len(mnemonic_words)
        
        # Validate mnemonic
        session = SessionLocal()
        try:
            wallet_service = WalletService(session)
            is_valid = wallet_service.validate_mnemonic(mnemonic)
            
            return jsonify({
                'data': {
                    'is_valid': is_valid,
                    'word_count': word_count
                },
                'message': 'Mnemonic validation completed.',
                'status': 'True'
            }), 200
        finally:
            session.close()

    except ValidationError as e:
        # Log validation error
        logger.warning(f"Validation error in validate_mnemonic: {str(e)}")
        return jsonify({
            'message': str(e),
            'status': 'False'
        }), 400
    except Exception as e:
        # Log other errors
        logger.error(f"Error in validate_mnemonic: {str(e)}", exc_info=True)
        return jsonify({
            'message': f"An unexpected error occurred: {str(e)}",
            'status': 'False'
        }), 500