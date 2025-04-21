import json
from decimal import Decimal
from typing import Dict, Any, Optional, List, Union
from enum import Enum

# Replace the incorrect import with a local enum
class TransactionType(Enum):
    NATIVE = "native"
    TOKEN = "token"
    CONTRACT = "contract"

from webhook.transaction_processor import TransactionProcessor
from webhook.chains.ada.utils import (
    parse_ada_input_data,
    format_ada_address,
    is_valid_ada_address,
    calculate_ada_fee,
    lovelace_to_ada,
    is_token_transfer,
    get_token_details
)
from utils.logging_config import get_logger

logger = get_logger(__name__)


class CardanoProcessor(TransactionProcessor):
    """Processor for Cardano (ADA) blockchain transactions."""
    
    def __init__(self):
        """Initialize the Cardano processor."""
        super().__init__()
        logger.info("Cardano Processor initialized")
        self.chain = "cardano"
        self.native_token = "ADA"
    
    def process_webhook(self, webhook_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process webhook data for Cardano transactions.
        
        Args:
            webhook_data: The webhook data to process
            
        Returns:
            Processed transaction data
        """
        logger.info(f"Processing Cardano webhook data: {webhook_data}")
        
        # Normalize the webhook data
        normalized_data = self._normalize_webhook_data(webhook_data)
        
        # Extract essential transaction information
        transaction_hash = normalized_data.get("hash")
        from_address = normalized_data.get("from")
        to_address = normalized_data.get("to")
        value = normalized_data.get("value", "0")
        input_data = normalized_data.get("input", "")
        
        # Determine if it's a contract call or token transfer
        is_token = is_token_transfer(input_data)
        parsed_input = parse_ada_input_data(input_data)
        
        # Calculate the transaction fee
        gas_price = normalized_data.get("gasPrice", "0")
        gas_used = normalized_data.get("gasUsed", "0")
        fee = calculate_ada_fee(gas_price, gas_used)
        
        # Determine transaction type
        transaction_type = TransactionType.TOKEN.value if is_token else TransactionType.NATIVE.value
        
        # Create the processed transaction data
        processed_data = {
            "hash": transaction_hash,
            "from_address": format_ada_address(from_address),
            "to_address": format_ada_address(to_address),
            "value": lovelace_to_ada(value),
            "fee": fee,
            "chain": self.chain,
            "token": parsed_input.get("token_symbol", self.native_token),
            "type": transaction_type,
            "input_data": input_data,
            "method_id": parsed_input.get("method_id"),
            "method_name": parsed_input.get("method_name"),
            "raw_data": json.dumps(webhook_data)
        }
        
        logger.info(f"Processed Cardano transaction: {processed_data}")
        return processed_data
    
    def _normalize_webhook_data(self, webhook_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Normalize webhook data to a standard format.
        
        Args:
            webhook_data: The raw webhook data
            
        Returns:
            Normalized webhook data
        """
        normalized = {}
        
        # Map webhook fields to our standard format
        field_mapping = {
            "tx_hash": "hash",
            "transaction_hash": "hash",
            "hash": "hash",
            "from_address": "from",
            "sender": "from",
            "to_address": "to",
            "recipient": "to",
            "amount": "value",
            "value": "value",
            "fee": "fee",
            "gas_price": "gasPrice",
            "gasPrice": "gasPrice",
            "gas_used": "gasUsed",
            "gasUsed": "gasUsed",
            "input": "input",
            "data": "input",
            "metadata": "input"
        }
        
        # Apply the field mapping
        for original_field, standard_field in field_mapping.items():
            if original_field in webhook_data:
                normalized[standard_field] = webhook_data[original_field]
        
        # Ensure important fields exist
        for field in ["hash", "from", "to", "value", "gasPrice", "gasUsed", "input"]:
            if field not in normalized:
                normalized[field] = ""
        
        return normalized
    
    def update_transaction(self, transaction_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Update transaction data for Cardano chain.
        
        Args:
            transaction_data: The transaction data to update
            
        Returns:
            Updated transaction data
        """
        # Ensure addresses are properly formatted
        if "from_address" in transaction_data:
            transaction_data["from_address"] = format_ada_address(transaction_data["from_address"])
        
        if "to_address" in transaction_data:
            transaction_data["to_address"] = format_ada_address(transaction_data["to_address"])
        
        # Set the chain
        transaction_data["chain"] = self.chain
        
        # If it's a native transfer, ensure token is set to ADA
        if transaction_data.get("type") == TransactionType.NATIVE.value:
            transaction_data["token"] = self.native_token
        
        # Process the transaction based on its recipient
        if transaction_data.get("to_address"):
            transaction_data = self._process_address_transaction(transaction_data)
        else:
            transaction_data = self._process_contract_event(transaction_data)
        
        return transaction_data
    
    def _process_address_transaction(self, transaction_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process a transaction sent to an address.
        
        Args:
            transaction_data: The transaction data
            
        Returns:
            Processed transaction data
        """
        # Check if the recipient address is valid
        to_address = transaction_data.get("to_address", "")
        if not is_valid_ada_address(to_address):
            logger.warning(f"Invalid Cardano recipient address: {to_address}")
            transaction_data["status"] = "error"
            transaction_data["error_message"] = "Invalid recipient address"
            return transaction_data
        
        # Check if it's a token transfer
        input_data = transaction_data.get("input_data", "")
        if is_token_transfer(input_data):
            # Parse token details
            parsed_input = parse_ada_input_data(input_data)
            transaction_data["method_id"] = parsed_input.get("method_id")
            transaction_data["method_name"] = parsed_input.get("method_name")
            
            # If we have token information, add it
            if "token_symbol" in parsed_input:
                transaction_data["token"] = parsed_input["token_symbol"]
            
            transaction_data["type"] = TransactionType.TOKEN.value
        else:
            transaction_data["type"] = TransactionType.NATIVE.value
        
        return transaction_data
    
    def _process_contract_event(self, transaction_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process a contract event transaction.
        
        Args:
            transaction_data: The transaction data
            
        Returns:
            Processed transaction data
        """
        # For smart contract interactions
        transaction_data["type"] = TransactionType.CONTRACT.value
        
        # Parse the input data
        input_data = transaction_data.get("input_data", "")
        parsed_input = parse_ada_input_data(input_data)
        
        transaction_data["method_id"] = parsed_input.get("method_id")
        transaction_data["method_name"] = parsed_input.get("method_name")
        
        return transaction_data 