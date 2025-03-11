from flask import Blueprint, jsonify, request
from datetime import datetime
from sqlalchemy import and_

from database import SessionLocal
from database.wallets import Wallets
from database.Address import Address
from database.Blockchains import Blockchains
from security.validators import InputValidator, SecurityUtils, ValidationError
from services.transaction_service import TransactionService
from utils.error_handlers import handle_api_errors
from utils.logging_config import get_logger
from schemas import (
    ReceiveTransactionRequest,
    ReceiveTransactionResponse,
    ErrorResponse
)

# Configure logging
logger = get_logger(__file__)
logger.info("Initializing receive transaction module")

# تعریف Blueprint
receive_bp = Blueprint('receive', __name__)

def get_user_address(session, user_id, blockchain_symbol):
    """Get user's public address from database"""
    try:
        # First, find the wallet associated with the user
        wallet = session.query(Wallets).filter(
            Wallets.UserID == user_id
        ).first()
        
        if not wallet:
            logger.warning(f"No wallet found for user: {user_id}")
            raise ValidationError("No wallet found for this user")

        # Debug: List all available blockchains
        available_blockchains = session.query(Blockchains).all()
        logger.debug(f"Available blockchain symbols: {[chain.Symbol for chain in available_blockchains]}")

        # Get blockchain ID from blockchain symbol
        blockchain = session.query(Blockchains).filter(
            Blockchains.Symbol == blockchain_symbol
        ).first()
        
        if not blockchain:
            logger.warning(f"Invalid blockchain symbol: {blockchain_symbol}. Available symbols are: {[chain.Symbol for chain in available_blockchains]}")
            raise ValidationError(f"Invalid blockchain symbol. Available symbols are: {[chain.Symbol for chain in available_blockchains]}")

        # Get the address for this wallet and blockchain
        address = session.query(Address).filter(and_(
            Address.WalletID == wallet.WalletID,
            Address.BlockchainID == blockchain.BlockchainID
        )).first()
        
        if not address:
            logger.warning(f"No address found for wallet {wallet.WalletID} on blockchain {blockchain_symbol}")
            raise ValidationError(f"No address found for {blockchain_symbol}")

        return address.PublicAddress

    except Exception as e:
        logger.error(f"Error getting address from database: {str(e)}")
        raise

@receive_bp.route('/Recive', methods=['POST'])
@SecurityUtils.rate_limit(requests=50, window=60)
@handle_api_errors
def receive_transaction():
    """
    Receive transaction
    ---
    tags:
      - Transactions
    requestBody:
      required: true
      content:
        application/json:
          schema:
            $ref: '#/components/schemas/ReceiveTransactionRequest'
    responses:
      200:
        description: Transaction received successfully
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/ReceiveTransactionResponse'
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
            logger.warning("Invalid request data in receive_transaction")
            raise ValidationError("Invalid request data")

        user_id = InputValidator.validate_uuid(
            data.get('UserID', ''),
            "UserID"
        )
        blockchain_symbol = InputValidator.validate_string(
            data.get('BlockchainName', ''),  # Keep the request parameter name same for backward compatibility
            "BlockchainName",
            pattern=r'^[a-zA-Z0-9_]+$'
        )

        logger.debug(f"Processing transaction receive request for user: {user_id} on blockchain symbol: {blockchain_symbol}")
        
        # Get user's public address from database
        public_address = get_user_address(session, user_id, blockchain_symbol)

        logger.info(f"Successfully processed transaction receive for user: {user_id} on blockchain symbol: {blockchain_symbol}")
        return jsonify({
            'PublicAddress': public_address,
            'success': True
        }), 200

    except ValidationError as e:
        logger.warning(f"Validation error in receive_transaction: {str(e)}")
        return jsonify({
            'message': str(e),
            'success': False
        }), 400
    except Exception as e:
        logger.error(f"Error in receive_transaction: {str(e)}", exc_info=True)
        return jsonify({
            'message': f"An unexpected error occurred: {str(e)}",
            'success': False
        }), 500
    finally:
        session.close()