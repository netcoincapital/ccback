from web3 import Web3
from eth_account import Account
import json
import os
from typing import Dict, Any
import logging

class SmartContractService:
    """Service for interacting with smart contracts"""
    
    def __init__(self):
        self.w3 = Web3(Web3.HTTPProvider(os.getenv('ETH_RPC_URL')))
        
    def load_contract(self, address: str, abi: list) -> Any:
        """Load a smart contract instance"""
        try:
            return self.w3.eth.contract(address=address, abi=abi)
        except Exception as e:
            logging.error(f"Error loading contract: {str(e)}")
            raise
            
    def call_contract_function(
        self,
        contract: Any,
        function_name: str,
        *args,
        **kwargs
    ) -> Any:
        """Call a read-only contract function"""
        try:
            func = getattr(contract.functions, function_name)
            return func(*args).call(**kwargs)
        except Exception as e:
            logging.error(f"Error calling contract function: {str(e)}")
            raise
            
    def send_contract_transaction(
        self,
        contract: Any,
        function_name: str,
        private_key: str,
        *args,
        **kwargs
    ) -> str:
        """Send a contract transaction"""
        try:
            account = Account.from_key(private_key)
            func = getattr(contract.functions, function_name)
            
            # Build transaction
            transaction = func(*args).build_transaction({
                'from': account.address,
                'nonce': self.w3.eth.get_transaction_count(account.address),
                'gas': kwargs.get('gas', 200000),
                'gasPrice': kwargs.get('gasPrice', self.w3.eth.gas_price),
            })
            
            # Sign and send transaction
            signed_txn = account.sign_transaction(transaction)
            tx_hash = self.w3.eth.send_raw_transaction(signed_txn.rawTransaction)
            return tx_hash.hex()
            
        except Exception as e:
            logging.error(f"Error sending contract transaction: {str(e)}")
            raise
            
    def decode_contract_event(self, contract: Any, event_name: str, event_data: Dict) -> Dict:
        """Decode contract event data"""
        try:
            event = getattr(contract.events, event_name)
            return event().process_log(event_data)
        except Exception as e:
            logging.error(f"Error decoding event: {str(e)}")
            raise 