from flask import Blueprint, jsonify, request
from datetime import datetime
from sqlalchemy import and_

from database import SessionLocal
from database.wallets import Wallets
from database.Address import Address
from database.Blockchains import Blockchains
from security.validators import InputValidator, SecurityUtils, ValidationError
from services.transaction_service import TransactionService
from services.transfer_service import TransferService
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
        # Normalize blockchain symbol
        blockchain_symbol = blockchain_symbol.lower().strip()
        
        # Map common variations to standard names
        name_mapping = {
            "eth": "ethereum",
            "ethereum": "ethereum",
            "bsc": "binance smart chain",
            "binance": "binance smart chain",
            "binance smart chain": "binance smart chain",
            "bs": "binance smart chain",
            "bnb": "binance smart chain",
            "btc": "bitcoin",
            "bitcoin": "bitcoin",
            "trx": "tron",
            "tron": "tron",
            "matic": "polygon",
            "polygon": "polygon",
            "avax": "avalanche",
            "avalanche": "avalanche",
            "arb": "arbitrum",
            "arbitrum": "arbitrum",
            "op": "optimism",
            "optimism": "optimism"
        }
        
        # Get normalized blockchain name
        normalized_blockchain = name_mapping.get(blockchain_symbol, blockchain_symbol)
        
        # Find the blockchain ID - search by all possible fields
        blockchain = session.query(Blockchains).filter(
            Blockchains.BlockchainName.ilike(normalized_blockchain)
        ).first()
        
        # If not found by BlockchainName, try ChainCode
        if not blockchain:
            blockchain = session.query(Blockchains).filter(
                Blockchains.ChainCode.ilike(blockchain_symbol)
            ).first()
        
        # If still not found, try Symbol
        if not blockchain:
            blockchain = session.query(Blockchains).filter(
                Blockchains.Symbol.ilike(blockchain_symbol)
            ).first()
        
        if not blockchain:
            logger.warning(f"Blockchain not found for symbol: {blockchain_symbol} (normalized: {normalized_blockchain})")
            # Log available blockchains for debugging
            all_chains = session.query(Blockchains).all()
            if all_chains:
                chain_info = [f"{chain.BlockchainName}(Symbol:{chain.Symbol}, ChainCode:{chain.ChainCode})" for chain in all_chains]
                logger.info(f"Available blockchains: {', '.join(chain_info)}")
            return None
            
        # Find the user's wallet
        wallet = session.query(Wallets).filter(
            Wallets.UserID == user_id
        ).first()
        
        if not wallet:
            logger.warning(f"Wallet not found for user: {user_id}")
            return None
            
        # Find the user's address for this blockchain
        address = session.query(Address).filter(
            and_(
                Address.WalletID == wallet.WalletID,
                Address.BlockchainID == blockchain.BlockchainID
            )
        ).first()
        
        if not address:
            logger.warning(f"Address not found for user: {user_id} on blockchain: {blockchain.BlockchainName}")
            return None
            
        # Return the public address
        return address.PublicAddress
        
    except Exception as e:
        logger.error(f"Error in get_user_address: {str(e)}")
        return None

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
            pattern=r'^[a-zA-Z0-9_\s]+$'  # Allow spaces in blockchain names
        )

        logger.debug(f"Processing transaction receive request for user: {user_id} on blockchain: {blockchain_symbol}")
        
        # Get user's public address from database
        public_address = get_user_address(session, user_id, blockchain_symbol)
        
        if not public_address:
            logger.warning(f"No address found for user {user_id} on blockchain {blockchain_symbol}")
            return jsonify({
                'message': f"Address not found for blockchain: {blockchain_symbol}",
                'success': False
            }), 404

        logger.info(f"Successfully processed transaction receive for user: {user_id} on blockchain: {blockchain_symbol}")
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

@receive_bp.route('/record-deposit', methods=['POST'])
@SecurityUtils.rate_limit(requests=20, window=60)
@handle_api_errors
def record_deposit():
    """
    Record an incoming deposit/transfer
    ---
    tags:
      - Transactions
    requestBody:
      required: true
      content:
        application/json:
          schema:
            type: object
            required:
              - TxHash
              - BlockchainName
              - RecipientAddress
              - SenderAddress
              - Amount
              - TokenSymbol
            properties:
              TxHash:
                type: string
                description: Transaction hash
              BlockchainName:
                type: string
                description: Blockchain name
              RecipientAddress:
                type: string
                description: Recipient address
              SenderAddress:
                type: string
                description: Sender address
              Amount:
                type: string
                description: Amount received
              TokenSymbol:
                type: string
                description: Token symbol
              AssetType:
                type: string
                enum: [native, token]
                default: native
                description: Asset type (native or token)
              TokenContract:
                type: string
                description: Token contract address (for tokens)
              ExplorerUrl:
                type: string
                description: URL to view transaction on blockchain explorer
    responses:
      201:
        description: Deposit recorded successfully
      400:
        description: Invalid input data
      500:
        description: Server error
    """
    session = SessionLocal()
    try:
        data = request.get_json()
        if not data:
            logger.warning("Invalid request data in record_deposit")
            raise ValidationError("Invalid request data")

        # Validate required fields
        tx_hash = InputValidator.validate_string(
            data.get('TxHash', ''),
            "TxHash"
        )
        blockchain_name = InputValidator.validate_string(
            data.get('BlockchainName', ''),
            "BlockchainName"
        )
        recipient_address = InputValidator.validate_string(
            data.get('RecipientAddress', ''),
            "RecipientAddress"
        )
        sender_address = InputValidator.validate_string(
            data.get('SenderAddress', ''),
            "SenderAddress"
        )
        amount = InputValidator.validate_string(
            data.get('Amount', ''),
            "Amount"
        )
        token_symbol = InputValidator.validate_string(
            data.get('TokenSymbol', ''),
            "TokenSymbol"
        )
        
        # Optional fields
        asset_type = data.get('AssetType', 'native')
        token_contract = data.get('TokenContract')
        explorer_url = data.get('ExplorerUrl')
        
        # Create transfer service
        transfer_service = TransferService(session)
        
        # Record the incoming transaction
        transfer = transfer_service.record_incoming_transaction(
            tx_hash=tx_hash,
            blockchain_name=blockchain_name,
            recipient_address=recipient_address,
            sender_address=sender_address,
            amount=amount,
            token_symbol=token_symbol,
            asset_type=asset_type,
            token_contract=token_contract,
            explorer_url=explorer_url
        )
        
        logger.info(f"Successfully recorded incoming transaction with ID: {transfer.TransferID}")
        
        return jsonify({
            'TransferID': transfer.TransferID,
            'success': True,
            'message': 'Deposit recorded successfully'
        }), 201
        
    except ValidationError as e:
        logger.warning(f"Validation error in record_deposit: {str(e)}")
        return jsonify({
            'message': str(e),
            'success': False
        }), 400
    except Exception as e:
        logger.error(f"Error in record_deposit: {str(e)}", exc_info=True)
        return jsonify({
            'message': f"An unexpected error occurred: {str(e)}",
            'success': False
        }), 500
    finally:
        session.close()