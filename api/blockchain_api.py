"""
API endpoints for blockchain operations
"""
import json
import logging
from flask import Blueprint, request, jsonify
from services.blockchain_router import BlockchainServiceRouter
from utils.logging_config import get_logger

# Initialize logger
logger = get_logger(__file__)

# Initialize blockchain service router
blockchain_router = BlockchainServiceRouter()

# Create Blueprint
blockchain_api = Blueprint('blockchain_api', __name__)

# Generic handler for prepare transaction endpoint
def handle_prepare(blockchain_name, data):
    """Handle prepare transaction request for any blockchain"""
    try:
        # Log detailed information about the request
        logger.info(f"Processing prepare transaction request for blockchain: {blockchain_name}")
        logger.debug(f"Request data: {data}")
        
        # Get UserID if present in any format
        user_id = (data.get('UserId') or data.get('userId') or 
                  data.get('UserID') or data.get('userid') or 
                  data.get('user_id'))
        
        # UserID is required for transaction preparation
        if not user_id:
            logger.warning("Missing UserID in prepare transaction request")
            return jsonify({
                "success": False, 
                "message": "UserID is required for transaction preparation"
            }), 400
        
        # Get blockchain service
        service = blockchain_router.get_service(blockchain_name)
        if not service:
            logger.error(f"Blockchain service not available for: {blockchain_name}")
            return jsonify({
                "success": False, 
                "message": f"Blockchain {blockchain_name} is not supported"
            }), 400
        
        # Extract transaction parameters
        sender_address = data.get('sender_address')
        recipient_address = data.get('recipient_address')
        amount = data.get('amount')
        smart_contract_address = data.get('smart_contract_address', '')
        
        # Validate required parameters
        if not sender_address:
            return jsonify({
                "success": False, 
                "message": "sender_address is required"
            }), 400
            
        if not recipient_address:
            return jsonify({
                "success": False, 
                "message": "recipient_address is required"
            }), 400
            
        if not amount:
            return jsonify({
                "success": False, 
                "message": "amount is required"
            }), 400
        
        # Prepare transaction
        result, error = service.prepare_transaction(
            sender_address=sender_address,
            recipient_address=recipient_address,
            amount=amount
        )
        
        if error:
            logger.error(f"Error preparing transaction: {error}")
            return jsonify({
                "success": False, 
                "message": f"Server error: {error}"
            }), 500
        
        # Add UserID to response
        if result:
            result['UserID'] = user_id
            
        logger.info(f"Successfully prepared transaction for {blockchain_name}")
        return jsonify(result), 200
        
    except Exception as e:
        logger.error(f"Unexpected error in prepare transaction: {str(e)}")
        return jsonify({
            "success": False, 
            "message": f"Server error: {str(e)}"
        }), 500

# Generic handler for confirm transaction endpoint
def handle_confirm(blockchain_name, data):
    """Handle confirm transaction request for any blockchain"""
    try:
        # Log detailed information about the request
        logger.info(f"Processing confirm transaction request for blockchain: {blockchain_name}")
        logger.debug(f"Request data: {data}")
        
        # Get UserID if present in any format
        user_id = (data.get('UserId') or data.get('userId') or 
                  data.get('UserID') or data.get('userid') or 
                  data.get('user_id'))
        
        # UserID is required for transaction confirmation
        if not user_id:
            logger.warning("Missing UserID in confirm transaction request")
            return jsonify({
                "success": False, 
                "message": "UserID is required for transaction confirmation"
            }), 400
        
        # Get blockchain service
        service = blockchain_router.get_service(blockchain_name)
        if not service:
            logger.error(f"Blockchain service not available for: {blockchain_name}")
            return jsonify({
                "success": False, 
                "message": f"Blockchain {blockchain_name} is not supported"
            }), 400
        
        # Extract transaction parameters
        transaction_id = data.get('transaction_id')
        private_key = data.get('private_key')
        
        # Validate required parameters
        if not transaction_id:
            return jsonify({
                "success": False, 
                "message": "transaction_id is required"
            }), 400
            
        if not private_key:
            return jsonify({
                "success": False, 
                "message": "private_key is required"
            }), 400
        
        # Send transaction
        result, error = service.send_transaction(
            transaction_id=transaction_id,
            private_key=private_key
        )
        
        if error:
            logger.error(f"Error confirming transaction: {error}")
            return jsonify({
                "success": False, 
                "message": f"Server error: {error}"
            }), 500
        
        # Add UserID to response
        if result:
            result['UserID'] = user_id
            
        logger.info(f"Successfully confirmed transaction for {blockchain_name}")
        return jsonify(result), 200
        
    except Exception as e:
        logger.error(f"Unexpected error in confirm transaction: {str(e)}")
        return jsonify({
            "success": False, 
            "message": f"Server error: {str(e)}"
        }), 500

# Dynamic endpoint registration
def register_blockchain_endpoint(blockchain_name):
    """Register prepare and confirm endpoints for a blockchain"""
    
    @blockchain_api.route(f'/{blockchain_name}/prepare', methods=['POST'])
    def prepare_endpoint():
        data = request.get_json()
        return handle_prepare(blockchain_name, data)
    
    @blockchain_api.route(f'/{blockchain_name}/confirm', methods=['POST'])
    def confirm_endpoint():
        data = request.get_json()
        return handle_confirm(blockchain_name, data)
    
    # Register endpoints with unique names
    prepare_endpoint.__name__ = f'{blockchain_name}_prepare'
    confirm_endpoint.__name__ = f'{blockchain_name}_confirm'

# Register endpoints for all supported blockchains
supported_blockchains = [
    'ethereum', 'bitcoin', 'tron', 'bsc', 'polygon', 
    'arbitrum', 'avalanche', 'solana', 'polkadot', 
    'litecoin', 'dogecoin', 'dash', 'xrp'
]

for blockchain in supported_blockchains:
    register_blockchain_endpoint(blockchain)

# Status endpoint
@blockchain_api.route('/status', methods=['GET'])
def get_status():
    """Get status of all blockchain services"""
    try:
        available_services = blockchain_router.get_available_services()
        
        # Get active and disabled blockchains
        active_blockchains = list(available_services.keys())
        disabled_blockchains = []
        
        # Create name variants mapping
        name_variants = {
            'ethereum': ['eth'],
            'bitcoin': ['btc'],
            'tron': ['trx'],
            'bsc': ['binance', 'binance-smart-chain', 'bnb'],
            'polygon': ['matic'],
            'arbitrum': ['arb'],
            'avalanche': ['avax'],
            'solana': ['sol'],
            'polkadot': ['dot'],
            'litecoin': ['ltc'],
            'dogecoin': ['doge'],
            'ripple': ['xrp']
        }
        
        # Create status details
        status_details = {}
        for blockchain in active_blockchains:
            # Check if service is actually working
            try:
                service = blockchain_router.get_service(blockchain)
                if service:
                    status_details[blockchain] = 'ok'
                else:
                    status_details[blockchain] = 'error'
                    if blockchain not in disabled_blockchains:
                        disabled_blockchains.append(blockchain)
            except Exception as e:
                status_details[blockchain] = 'error'
                if blockchain not in disabled_blockchains:
                    disabled_blockchains.append(blockchain)
        
        # Remove disabled blockchains from active list
        active_blockchains = [b for b in active_blockchains if b not in disabled_blockchains]
        
        return jsonify({
            'active_blockchains': active_blockchains,
            'disabled_blockchains': disabled_blockchains,
            'name_variants': name_variants,
            'status_details': status_details
        })
        
    except Exception as e:
        logger.error(f"Error getting blockchain status: {str(e)}")
        return jsonify({
            'error': str(e),
            'active_blockchains': [],
            'disabled_blockchains': [],
            'name_variants': {},
            'status_details': {}
        }), 500 