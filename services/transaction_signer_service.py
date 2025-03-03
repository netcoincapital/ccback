from eth_account import Account
from web3 import Web3
from typing import Dict
import json
import logging
import os

class TransactionSignerService:
    """Service for signing blockchain transactions"""
    
    def __init__(self):
        self.w3 = Web3(Web3.HTTPProvider(os.getenv('ETH_RPC_URL')))
        
    def sign_ethereum_transaction(self, private_key: str, transaction: Dict) -> str:
        """Sign an Ethereum transaction"""
        try:
            account = Account.from_key(private_key)
            
            # Ensure proper transaction format
            tx = {
                'nonce': self.w3.eth.get_transaction_count(account.address),
                'gasPrice': transaction.get('gasPrice', self.w3.eth.gas_price),
                'gas': transaction.get('gas', 21000),
                'to': transaction['to'],
                'value': transaction['value'],
                'data': transaction.get('data', ''),
                'chainId': transaction.get('chainId', 1)
            }
            
            # Sign transaction
            signed = account.sign_transaction(tx)
            return signed.rawTransaction.hex()
            
        except Exception as e:
            logging.error(f"Error signing Ethereum transaction: {str(e)}")
            raise
            
    def sign_bitcoin_transaction(self, private_key: str, transaction: Dict) -> str:
        """Sign a Bitcoin transaction"""
        try:
            # Implement Bitcoin transaction signing
            # This is a placeholder - implement actual Bitcoin signing logic
            pass
        except Exception as e:
            logging.error(f"Error signing Bitcoin transaction: {str(e)}")
            raise
            
    def verify_ethereum_signature(self, address: str, message: str, signature: str) -> bool:
        """Verify an Ethereum signature"""
        try:
            # Verify the signature
            message_hash = self.w3.eth.account.hash_message(text=message)
            recovered_address = Account.recover_message(message_hash, signature=signature)
            return recovered_address.lower() == address.lower()
        except Exception as e:
            logging.error(f"Error verifying signature: {str(e)}")
            return False 