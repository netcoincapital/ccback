from flask import Blueprint, jsonify, request
from sqlalchemy.orm import Session
import logging
import json
from web3 import Web3
from decimal import Decimal
import uuid

from database import SessionLocal, Users, Wallets, Address, Blockchains, Currencies
from security.validators import InputValidator, SecurityUtils, ValidationError
from security.encryption import decrypt_private_key_aes
from utils.error_handlers import handle_api_errors
from utils.logging_config import get_logger
from services.balance_service import BalanceService
from services.transaction_signer_service import TransactionSignerService
from services.smart_contract_service import SmartContractService
from config.api_config import Web3Manager, ERC20_ABI, EXTERNAL_APIS
from services.blockchain_service import BlockchainService

# Configure logging
logger = get_logger(__file__)
logger.info("Initializing send transaction module")

send_bp = Blueprint('send', __name__)

# Transaction URLs for different blockchains
TRANSACTION_URLS = {
    "Ethereum": "https://etherscan.io/tx/{}",
    "Bitcoin": "https://www.blockchain.com/btc/tx/{}",
    "Tron": "https://tronscan.org/#/transaction/{}",
    "Binance": "https://bscscan.com/tx/{}",
    "Polygon": "https://polygonscan.com/tx/{}",
    "Avalanche": "https://snowtrace.io/tx/{}",
    "Arbitrum": "https://arbiscan.io/tx/{}",
    "Polkadot": "https://polkadot.subscan.io/extrinsic/{}",
    "XRP": "https://xrpscan.com/tx/{}",
    "Solana": "https://explorer.solana.com/tx/{}"
}

def get_transaction_url(blockchain_name, txn_id):
    """Get transaction URL for a specific blockchain"""
    url_template = TRANSACTION_URLS.get(blockchain_name)
    if url_template:
        return url_template.format(txn_id)
    return None

def get_user_wallet_and_address(session, user_id, blockchain_name):
    """Get user's wallet and address for a specific blockchain"""
    try:
        # Get user's wallet
        wallet = session.query(Wallets).join(Users).filter(Users.UserID == user_id).first()
        
        if not wallet:
            logger.warning(f"No wallet found for user {user_id}")
            return None, None, "No wallet found for this user"
        
        # Get blockchain ID
        blockchain = session.query(Blockchains).filter(Blockchains.BlockchainName == blockchain_name).first()
        
        if not blockchain:
            logger.warning(f"Blockchain {blockchain_name} not found")
            return None, None, f"Blockchain {blockchain_name} not supported"
        
        # Get user's address for this blockchain
        address = session.query(Address).filter(
            Address.WalletID == wallet.WalletID,
            Address.BlockchainID == blockchain.BlockchainID
        ).first()
        
        if not address:
            logger.warning(f"No {blockchain_name} address found for user {user_id}")
            return None, None, f"No {blockchain_name} address found for this user"
        
        # Decrypt private key
        try:
            private_key = decrypt_private_key_aes(address.PrivateKey)
        except Exception as e:
            logger.error(f"Error decrypting private key: {str(e)}")
            return None, None, "Error accessing wallet credentials"
        
        return address.PublicAddress, private_key, None
    
    except Exception as e:
        logger.error(f"Error getting user wallet and address: {str(e)}")
        return None, None, f"Error: {str(e)}"

def get_currency_details(session, currency_name, blockchain_name):
    """Get currency details for a specific blockchain"""
    try:
        # Get blockchain ID
        blockchain = session.query(Blockchains).filter(Blockchains.BlockchainName == blockchain_name).first()
        
        if not blockchain:
            logger.warning(f"Blockchain {blockchain_name} not found")
            return None, f"Blockchain {blockchain_name} not supported"
        
        # Get currency details
        currency = session.query(Currencies).filter(
            Currencies.Symbol == currency_name,
            Currencies.BlockchainID == blockchain.BlockchainID
        ).first()
        
        if not currency:
            logger.warning(f"Currency {currency_name} not found on {blockchain_name}")
            return None, f"Currency {currency_name} not found on {blockchain_name}"
        
        return currency, None
    
    except Exception as e:
        logger.error(f"Error getting currency details: {str(e)}")
        return None, f"Error: {str(e)}"

def estimate_transaction_fee(blockchain_name, is_token=False):
    """Estimate transaction fee for a specific blockchain"""
    try:
        session = SessionLocal()
        blockchain_service = BlockchainService(session)
        
        # Get real-time gas fee from blockchain service
        fee_data = blockchain_service.get_gas_fee(blockchain_name)
        
        if "error" in fee_data:
            logger.error(f"Error getting gas fee for {blockchain_name}: {fee_data['error']}")
            return None
            
        gas_fee = fee_data.get("gas_fee")
        
        # For token transfers, we typically need more gas
        if is_token:
            gas_fee = gas_fee * 1.5 if gas_fee else None
            
        logger.info(f"Estimated gas fee for {blockchain_name}: {gas_fee} {'(token transfer)' if is_token else ''}")
        return gas_fee
        
    except Exception as e:
        logger.error(f"Error estimating transaction fee: {str(e)}")
        return None
    finally:
        session.close()

def validate_transaction_inputs(user_id, currency_name, recipient_address, amount, smart_contract_address=None):
    """Validate transaction inputs"""
    errors = []
    
    # Validate UserID
    try:
        InputValidator.validate_uuid(user_id, "UserID")
    except ValidationError as e:
        errors.append(str(e))
    
    # Validate CurrencyName
    try:
        InputValidator.validate_string(currency_name, "CurrencyName", pattern=r'^[A-Z0-9]+$')
    except ValidationError as e:
        errors.append(str(e))
    
    # Validate RecipientAddress
    try:
        InputValidator.validate_string(recipient_address, "RecipientAddress", min_length=10, max_length=100)
    except ValidationError as e:
        errors.append(str(e))
    
    # Validate Amount
    try:
        amount_value = float(amount)
        if amount_value <= 0:
            errors.append("Amount must be greater than 0")
    except ValueError:
        errors.append("Amount must be a valid number")
    
    # Validate SmartContractAddress - now required for tokens
    if smart_contract_address is None:
        errors.append("SmartContractAddress is required for token transactions")
    else:
        try:
            InputValidator.validate_string(smart_contract_address, "SmartContractAddress", min_length=10, max_length=100)
        except ValidationError as e:
            errors.append(str(e))
    
    return errors

def prepare_evm_transaction(web3, sender_address, private_key, recipient_address, amount, smart_contract_address, currency_name):
    """Prepare an EVM transaction"""
    try:
        # Get sender's balance
        sender_balance = web3.eth.get_balance(sender_address)
        
        # Get real-time gas price
        gas_price = web3.eth.gas_price
        
        # Estimate gas limit based on transaction type
        if smart_contract_address:
            # For token transfers
            contract = web3.eth.contract(address=web3.to_checksum_address(smart_contract_address), abi=ERC20_ABI)
            amount_in_wei = web3.to_wei(float(amount), 'ether')
            gas_limit = contract.functions.transfer(recipient_address, amount_in_wei).estimate_gas({'from': sender_address})
        else:
            # For native currency transfers
            gas_limit = web3.eth.estimate_gas({
                'from': sender_address,
                'to': recipient_address,
                'value': web3.to_wei(float(amount), 'ether')
            })
        
        # Calculate total fee
        total_fee = gas_price * gas_limit
        total_fee_in_eth = web3.from_wei(total_fee, 'ether')
        
        # Calculate balance after transaction
        if smart_contract_address:
            # For tokens, only gas fee affects native balance
            balance_after = web3.from_wei(sender_balance - total_fee, 'ether')
        else:
            # For native currency, both amount and fee affect balance
            amount_in_wei = web3.to_wei(float(amount), 'ether')
            balance_after = web3.from_wei(sender_balance - amount_in_wei - total_fee, 'ether')
        
        return {
            'sender_address': sender_address,
            'recipient_address': recipient_address,
            'amount': amount,
            'token_symbol': currency_name,
            'sender_balance_before': web3.from_wei(sender_balance, 'ether'),
            'estimated_fee': total_fee_in_eth,
            'gas_limit': gas_limit,
            'gas_price': gas_price,
            'balance_after_tx': balance_after
        }, None
        
    except Exception as e:
        logger.error(f"Error preparing EVM transaction: {str(e)}")
        return None, str(e)

def send_evm_transaction(web3, sender_address, private_key, recipient_address, amount, tx_details):
    """Send transaction for EVM-compatible blockchains"""
    try:
        # If it's a token transfer
        if tx_details["is_token"]:
            contract_address = tx_details["contract_address"]
            contract = web3.eth.contract(address=Web3.to_checksum_address(contract_address), abi=ERC20_ABI)
            
            # Get token decimals
            decimals = contract.functions.decimals().call()
            
            # Convert amount to token units
            amount_in_token_units = int(float(amount) * (10 ** decimals))
            
            # Build transaction
            nonce = web3.eth.get_transaction_count(sender_address)
            
            tx = contract.functions.transfer(
                Web3.to_checksum_address(recipient_address),
                amount_in_token_units
            ).build_transaction({
                'chainId': web3.eth.chain_id,
                'gas': tx_details["gas_limit"],
                'gasPrice': tx_details["gas_price"],
                'nonce': nonce,
            })
            
        else:
            # Native currency transfer
            # Convert amount to wei
            amount_wei = web3.to_wei(float(amount), 'ether')
            
            # Build transaction
            nonce = web3.eth.get_transaction_count(sender_address)
            
            tx = {
                'nonce': nonce,
                'to': recipient_address,
                'value': amount_wei,
                'gas': tx_details["gas_limit"],
                'gasPrice': tx_details["gas_price"],
                'chainId': web3.eth.chain_id
            }
        
        # Sign transaction
        signed_tx = web3.eth.account.sign_transaction(tx, private_key)
        
        # Send transaction
        tx_hash = web3.eth.send_raw_transaction(signed_tx.rawTransaction)
        
        # Wait for transaction receipt
        tx_receipt = web3.eth.wait_for_transaction_receipt(tx_hash)
        
        # Get actual gas used
        actual_gas_used = tx_receipt.gasUsed
        actual_fee_wei = actual_gas_used * tx_details["gas_price"]
        actual_fee_eth = web3.from_wei(actual_fee_wei, 'ether')
        
        # Get sender balance after transaction
        sender_balance_after = web3.eth.get_balance(sender_address)
        sender_balance_after_eth = web3.from_wei(sender_balance_after, 'ether')
        
        # Prepare result
        result = {
            "transaction_hash": tx_hash.hex(),
            "status": "Success" if tx_receipt.status == 1 else "Failed",
            "actual_fee": actual_fee_eth,
            "sender_balance_after": sender_balance_after_eth,
            "block_number": tx_receipt.blockNumber,
            "gas_used": actual_gas_used
        }
        
        return result, None
    
    except Exception as e:
        logger.error(f"Error sending EVM transaction: {str(e)}")
        return None, f"Error sending transaction: {str(e)}"

@send_bp.route('/balance/<blockchain_name>', methods=['POST'])
@SecurityUtils.rate_limit(requests=10, window=60)
@handle_api_errors
def send_transaction(blockchain_name):
    """
    Send a transaction on a specific blockchain
    ---
    tags:
      - Transactions
    parameters:
      - name: blockchain_name
        in: path
        required: true
        schema:
          type: string
        description: Name of the blockchain
    requestBody:
      required: true
      content:
        application/json:
          schema:
            type: object
            required:
              - UserID
              - CurrencyName
              - RecipientAddress
              - Amount
            properties:
              UserID:
                type: string
                description: User ID
              CurrencyName:
                type: string
                description: Currency symbol
              SmartContractAddress:
                type: string
                description: Smart contract address (for tokens)
              RecipientAddress:
                type: string
                description: Recipient address
              Amount:
                type: string
                description: Amount to send
    responses:
      200:
        description: Transaction details before sending
      201:
        description: Transaction sent successfully
      400:
        description: Invalid input data
      404:
        description: Wallet or currency not found
      429:
        description: Rate limit exceeded
      500:
        description: Server error
    """
    session = SessionLocal()
    try:
        # Get request data
        data = request.get_json()
        if not data:
            return jsonify({
                "message": "Invalid request data",
                "success": False
            }), 400
        
        # Extract parameters
        user_id = data.get('UserID', '')
        currency_name = data.get('CurrencyName', '')
        recipient_address = data.get('RecipientAddress', '')
        amount = data.get('Amount', '')
        
        # Get currency details first to check if it's a token
        currency, error = get_currency_details(session, currency_name, blockchain_name)
        if error:
            return jsonify({
                "message": error,
                "success": False
            }), 404
            
        # Check if it's a token
        is_token = currency.IsToken
        smart_contract_address = data.get('SmartContractAddress') if is_token else None
        
        # For tokens, SmartContractAddress is required
        if is_token and not smart_contract_address:
            return jsonify({
                "message": "SmartContractAddress is required for token transactions",
                "success": False
            }), 400
        
        # Validate inputs
        validation_errors = validate_transaction_inputs(
            user_id, currency_name, recipient_address, amount, smart_contract_address
        )
        
        if validation_errors:
            return jsonify({
                "message": "Validation errors",
                "errors": validation_errors,
                "success": False
            }), 400
        
        # Get user's wallet and address
        sender_address, private_key, error = get_user_wallet_and_address(session, user_id, blockchain_name)
        if error:
            return jsonify({
                "message": error,
                "success": False
            }), 404
        
        # Initialize Web3 provider
        web3_providers = Web3Manager.get_web3_providers()
        web3 = web3_providers.get(blockchain_name)
        
        if not web3 and blockchain_name in ["Ethereum", "Binance", "Polygon", "Avalanche", "Arbitrum"]:
            return jsonify({
                "message": f"Could not connect to {blockchain_name} network",
                "success": False
            }), 500
        
        # For EVM-compatible blockchains
        if blockchain_name in ["Ethereum", "Binance", "Polygon", "Avalanche", "Arbitrum"]:
            # Prepare transaction
            tx_details, error = prepare_evm_transaction(
                web3, sender_address, private_key, recipient_address, 
                amount, smart_contract_address, currency_name
            )
            
            if error:
                return jsonify({
                    "message": error,
                    "success": False
                }), 400
            
            # Format transaction details before sending
            before_sending = {
                "details": f"\n📌 **Transaction Details (Before Sending):**\n"
                          f"   🔹 Sender Address: {tx_details['sender_address']}\n"
                          f"   🔹 Recipient Address: {tx_details['recipient_address']}\n"
                          f"   🔹 Smart Contract: {smart_contract_address if is_token else 'N/A'}\n"
                          f"   🔹 Amount: {tx_details['amount']} {tx_details['token_symbol']}\n"
                          f"   🔹 Sender Balance (Before): {tx_details['sender_balance_before']} {tx_details['token_symbol']}\n"
                          f"   🔹 Estimated Fee: {tx_details['estimated_fee']} {blockchain_name}\n"
                          f"   🔹 Gas Limit: {tx_details['gas_limit']}\n"
                          f"   🔹 Gas Price: {web3.from_wei(tx_details['gas_price'], 'gwei')} Gwei\n"
                          f"   🔹 Sender Balance (After): {tx_details['balance_after_tx']} {blockchain_name}\n",
                "transaction_id": str(uuid.uuid4()),
                "success": True
            }
            
            return jsonify(before_sending), 200
            
        # For non-EVM blockchains (would need specific implementations)
        else:
            return jsonify({
                "message": f"Sending on {blockchain_name} is not yet implemented",
                "success": False
            }), 501
    
    except Exception as e:
        logger.error(f"Error in send_transaction: {str(e)}", exc_info=True)
        return jsonify({
            "message": f"An unexpected error occurred: {str(e)}",
            "success": False
        }), 500
    finally:
        session.close()

@send_bp.route('/<blockchain_name>/confirm', methods=['POST'])
@SecurityUtils.rate_limit(requests=5, window=60)
@handle_api_errors
def confirm_transaction(blockchain_name):
    """
    Confirm and send a transaction
    ---
    tags:
      - Transactions
    parameters:
      - name: blockchain_name
        in: path
        required: true
        schema:
          type: string
        description: Name of the blockchain
    requestBody:
      required: true
      content:
        application/json:
          schema:
            type: object
            required:
              - UserID
              - CurrencyName
              - RecipientAddress
              - Amount
              - TransactionID
              - Confirm
            properties:
              UserID:
                type: string
                description: User ID
              CurrencyName:
                type: string
                description: Currency symbol
              SmartContractAddress:
                type: string
                description: Smart contract address (for tokens)
              RecipientAddress:
                type: string
                description: Recipient address
              Amount:
                type: string
                description: Amount to send
              TransactionID:
                type: string
                description: Transaction ID from previous request
              Confirm:
                type: boolean
                description: Whether to confirm the transaction
    responses:
      201:
        description: Transaction sent successfully
      400:
        description: Invalid input data
      404:
        description: Wallet or currency not found
      429:
        description: Rate limit exceeded
      500:
        description: Server error
    """
    session = SessionLocal()
    try:
        # Get request data
        data = request.get_json()
        if not data:
            return jsonify({
                "message": "Invalid request data",
                "success": False
            }), 400
        
        # Extract parameters
        user_id = data.get('UserID', '')
        currency_name = data.get('CurrencyName', '')
        recipient_address = data.get('RecipientAddress', '')
        amount = data.get('Amount', '')
        transaction_id = data.get('TransactionID', '')
        confirm = data.get('Confirm', False)
        
        # Get currency details first to check if it's a token
        currency, error = get_currency_details(session, currency_name, blockchain_name)
        if error:
            return jsonify({
                "message": error,
                "success": False
            }), 404
            
        # Check if it's a token
        is_token = currency.IsToken
        smart_contract_address = data.get('SmartContractAddress') if is_token else None
        
        # For tokens, SmartContractAddress is required
        if is_token and not smart_contract_address:
            return jsonify({
                "message": "SmartContractAddress is required for token transactions",
                "success": False
            }), 400
        
        # Check if user confirmed the transaction
        if not confirm:
            return jsonify({
                "message": "Transaction cancelled by user",
                "success": False
            }), 400
        
        # Validate inputs
        validation_errors = validate_transaction_inputs(
            user_id, currency_name, recipient_address, amount, smart_contract_address
        )
        
        if validation_errors:
            return jsonify({
                "message": "Validation errors",
                "errors": validation_errors,
                "success": False
            }), 400
        
        # Get user's wallet and address
        sender_address, private_key, error = get_user_wallet_and_address(session, user_id, blockchain_name)
        if error:
            return jsonify({
                "message": error,
                "success": False
            }), 404
        
        # Initialize Web3 provider
        web3_providers = Web3Manager.get_web3_providers()
        web3 = web3_providers.get(blockchain_name)
        
        if not web3 and blockchain_name in ["Ethereum", "Binance", "Polygon", "Avalanche", "Arbitrum"]:
            return jsonify({
                "message": f"Could not connect to {blockchain_name} network",
                "success": False
            }), 500
        
        # For EVM-compatible blockchains
        if blockchain_name in ["Ethereum", "Binance", "Polygon", "Avalanche", "Arbitrum"]:
            # Prepare transaction
            tx_details, error = prepare_evm_transaction(
                web3, sender_address, private_key, recipient_address, 
                amount, smart_contract_address, currency_name
            )
            
            if error:
                return jsonify({
                    "message": error,
                    "success": False
                }), 400
            
            # Send transaction
            result, error = send_evm_transaction(
                web3, sender_address, private_key, recipient_address, 
                amount, tx_details
            )
            
            if error:
                return jsonify({
                    "message": error,
                    "success": False
                }), 500
            
            # Get transaction URL
            transaction_url = get_transaction_url(blockchain_name, result["transaction_hash"])
            
            # Format transaction details after sending
            after_sending = {
                "details": f"\n✅ **Transaction Successfully Sent!**\n"
                          f"   🔹 Transaction Hash: {result['transaction_hash']}\n"
                          f"   🔹 Transaction URL: {transaction_url}\n"
                          f"   🔹 Actual Fee: {result['actual_fee']} {blockchain_name}\n"
                          f"   🔹 Sender Balance (After): {result['sender_balance_after']} {blockchain_name}\n"
                          f"   🔹 Block Number: {result['block_number']}\n"
                          f"   🔹 Gas Used: {result['gas_used']}\n"
                          f"   🔹 Status: {result['status']}\n",
                "success": True
            }
            
            return jsonify(after_sending), 201
            
        # For non-EVM blockchains (would need specific implementations)
        else:
            return jsonify({
                "message": f"Sending on {blockchain_name} is not yet implemented",
                "success": False
            }), 501
    
    except Exception as e:
        logger.error(f"Error in confirm_transaction: {str(e)}", exc_info=True)
        return jsonify({
            "message": f"An unexpected error occurred: {str(e)}",
            "success": False
        }), 500
    finally:
        session.close() 