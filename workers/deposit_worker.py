import sys
import os
import logging
import time
from datetime import datetime, timedelta
import requests
import json

# Add the parent directory to the sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import SessionLocal, Users, Wallets, Address, Blockchains, Currencies, Transfers
from services.transfer_service import TransferService
from services.balance_service import BalanceService
from services.tatum_service import TatumService
from utils.logging_config import setup_logging, get_logger
from config.api_config import EXTERNAL_APIS

# Configure logging
logger = get_logger(__file__)

# Initialize Tatum service with API key
TATUM_API_KEY = EXTERNAL_APIS.get('TATUM_API_KEY', '')
tatum_service = TatumService(TATUM_API_KEY)

# How often to scan for new deposits (in seconds)
SCAN_INTERVAL = 60

# How far back to look for transactions (in hours)
LOOKBACK_PERIOD = 12

def process_address_deposits(address_obj, blockchain_name, session):
    """
    Check for new deposits to an address and record them
    
    Args:
        address_obj: Address object from database
        blockchain_name: Name of the blockchain
        session: Database session
    """
    try:
        public_address = address_obj.PublicAddress
        
        # Get transactions for this address
        transactions, error = tatum_service.get_account_transactions(
            blockchain_name, 
            public_address,
            start_timestamp=int((datetime.now() - timedelta(hours=LOOKBACK_PERIOD)).timestamp())
        )
        
        if error:
            logger.error(f"Error getting transactions for {public_address} on {blockchain_name}: {error}")
            return
            
        if not transactions or not isinstance(transactions, list):
            logger.debug(f"No transactions found for {public_address} on {blockchain_name}")
            return
            
        logger.info(f"Found {len(transactions)} transactions for {public_address} on {blockchain_name}")
        
        # Create transfer service to record transactions
        transfer_service = TransferService(session)
        
        # Keep track of processed transactions to avoid duplicates
        processed_tx_hashes = set()
        
        # Process each transaction
        for tx in transactions:
            # Skip if missing critical information
            if not tx.get('hash') or not tx.get('from') or not tx.get('to'):
                continue
                
            tx_hash = tx.get('hash')
            
            # Skip outgoing transactions
            if tx.get('from').lower() == public_address.lower():
                continue
                
            # Skip transactions where this address isn't the recipient
            if tx.get('to').lower() != public_address.lower():
                continue
                
            # Skip if we've already processed this tx in this run
            if tx_hash in processed_tx_hashes:
                continue
                
            # Check if transaction is already recorded
            existing_tx = session.query(Transfers).filter(
                Transfers.TxHash == tx_hash,
                Transfers.AddressID == address_obj.AddressID
            ).first()
            
            if existing_tx:
                logger.debug(f"Transaction {tx_hash} already recorded for {public_address}")
                continue
                
            # Get transaction amount and token info
            amount = tx.get('amount', '0')
            token_symbol = tx.get('currency', '')
            asset_type = 'token' if tx.get('tokenAddress') else 'native'
            token_contract = tx.get('tokenAddress')
            
            # Record the incoming transaction
            try:
                logger.info(f"Recording new deposit: {tx_hash} to {public_address} for {amount} {token_symbol}")
                
                transfer = transfer_service.record_incoming_transaction(
                    tx_hash=tx_hash,
                    blockchain_name=blockchain_name,
                    recipient_address=public_address,
                    sender_address=tx.get('from'),
                    amount=amount,
                    token_symbol=token_symbol,
                    asset_type=asset_type,
                    token_contract=token_contract
                )
                
                processed_tx_hashes.add(tx_hash)
                
                logger.info(f"Successfully recorded deposit with ID: {transfer.TransferID}")
                
            except Exception as e:
                logger.error(f"Error recording deposit {tx_hash}: {str(e)}")
                
    except Exception as e:
        logger.error(f"Error processing deposits for {address_obj.PublicAddress} on {blockchain_name}: {str(e)}")
 
def scan_for_deposits():
    """
    Scan the blockchain for new deposits to user addresses
    """
    session = SessionLocal()
    try:
        # Get all active blockchains
        blockchains = session.query(Blockchains).all()
        
        # Get all active addresses
        addresses = session.query(Address).all()
        
        logger.info(f"Scanning {len(addresses)} addresses across {len(blockchains)} blockchains for deposits")
        
        # Process each address
        for address_obj in addresses:
            # Get the blockchain for this address
            blockchain = next((b for b in blockchains if b.BlockchainID == address_obj.BlockchainID), None)
            
            if not blockchain:
                logger.warning(f"Blockchain not found for address {address_obj.PublicAddress}")
                continue
                
            blockchain_name = blockchain.BlockchainName
            
            # Process deposits for this address
            process_address_deposits(address_obj, blockchain_name, session)
            
        logger.info("Deposit scan completed")
        
    except Exception as e:
        logger.error(f"Error scanning for deposits: {str(e)}")
    finally:
        session.close()

def run_deposit_worker():
    """
    Start the deposit worker to scan for new deposits
    """
    logger.info("Starting deposit monitor worker")
    
    try:
        while True:
            try:
                # Scan for new deposits
                scan_for_deposits()
                
                # Sleep until next scan
                logger.debug(f"Sleeping for {SCAN_INTERVAL} seconds until next scan")
                time.sleep(SCAN_INTERVAL)
                
            except Exception as e:
                logger.error(f"Error in deposit scan cycle: {str(e)}")
                time.sleep(SCAN_INTERVAL)  # Still sleep before retrying
                
    except KeyboardInterrupt:
        logger.info("Deposit worker stopped by user")
        
if __name__ == "__main__":
    # Configure logging
    setup_logging()
    logging.info("Starting deposit worker")
    
    try:
        # Run the deposit worker
        run_deposit_worker()
    except KeyboardInterrupt:
        logging.info("Deposit worker stopped by user")
    except Exception as e:
        logging.error(f"Deposit worker encountered an error: {str(e)}") 