import re
from decimal import Decimal
import json
from typing import Dict, Any, Optional, List, Union

from CC.utils.logging_config import get_logger

logger = get_logger(__name__)

def parse_ada_input_data(input_data: str) -> Dict[str, Any]:
    """
    Parse Cardano transaction metadata or input data.
    
    Args:
        input_data: The transaction metadata or input data
        
    Returns:
        Dictionary containing the parsed data
    """
    result = {
        "method_id": None,
        "method_name": None,
        "params": []
    }
    
    if not input_data or input_data == "0x" or input_data == "":
        return result
    
    try:
        # For Cardano, the input data is often in CBOR or JSON metadata
        # This is a simplified version - in production you would need to parse CBOR properly
        # or handle actual transaction metadata formats
        
        # Try to parse as JSON if it looks like JSON
        if input_data.startswith('{'):
            data = json.loads(input_data)
            result["method_id"] = str(data.get("transaction_type", ""))
            result["method_name"] = str(data.get("action", ""))
            result["params"] = data.get("parameters", [])
        else:
            # Simple heuristic detection of possible method types based on first few bytes
            # In production, this would be more sophisticated
            if len(input_data) >= 8:
                result["method_id"] = input_data[:8]
                
                # Map common method IDs (this is just an example)
                method_map = {
                    "a9059cbb": "token_transfer",
                    "095ea7b3": "token_approval",
                    # Add more method mappings as needed
                }
                
                result["method_name"] = method_map.get(result["method_id"], "unknown")
                
                # For some known methods, we could parse parameters
                if result["method_name"] == "token_transfer" and len(input_data) >= 136:
                    # Extract parameters (simplified example)
                    result["params"] = [
                        input_data[8:72],  # recipient address (padded)
                        input_data[72:136]  # amount (padded)
                    ]
    except Exception:
        # If parsing fails, return default structure
        pass
    
    return result

def format_ada_address(address: str) -> str:
    """
    Format a Cardano address to ensure consistency.
    Cardano addresses are case-sensitive and don't typically have a prefix.
    
    Args:
        address: The Cardano address to format
        
    Returns:
        The formatted address
    """
    if not address:
        return ""
    
    # Remove any whitespace
    return address.strip()

def is_valid_ada_address(address: str) -> bool:
    """
    Validate if a string is a proper Cardano address.
    Cardano addresses are typically 58-104 characters long.
    
    Args:
        address: The address to validate
        
    Returns:
        True if the address is valid, False otherwise
    """
    if not address:
        return False
    
    # Basic validation - Cardano addresses are typically between 58-104 characters
    # and use base58 encoding (alphanumeric without 0, O, I, l)
    pattern = r'^[1-9A-HJ-NP-Za-km-z]{58,104}$'
    
    # Byron era addresses may start with Ae2
    # Shelley era addresses may start with addr1
    # This is a simplified validation - production would need more robust checks
    if address.startswith('addr1') or address.startswith('Ae2'):
        return bool(re.match(pattern, address))
    
    return False

def calculate_ada_fee(gas_price: Union[int, str, Decimal], gas_used: Union[int, str, Decimal]) -> Decimal:
    """
    Calculate the transaction fee for a Cardano transaction.
    For Cardano, fees are typically calculated differently than gas-based blockchains.
    This is a simplified version.
    
    Args:
        gas_price: The gas price (used to maintain API compatibility)
        gas_used: The gas used (used to maintain API compatibility)
        
    Returns:
        The calculated fee as a Decimal
    """
    # Convert arguments to Decimal for precise calculation
    if isinstance(gas_price, str):
        gas_price = Decimal(gas_price.replace(',', ''))
    else:
        gas_price = Decimal(str(gas_price))
    
    if isinstance(gas_used, str):
        gas_used = Decimal(gas_used.replace(',', ''))
    else:
        gas_used = Decimal(str(gas_used))
    
    # Calculate fee (gas_price * gas_used)
    # In Cardano, fees are in Lovelace, but we'll keep the calculation similar
    # for API compatibility
    fee = gas_price * gas_used
    
    return fee

def lovelace_to_ada(lovelace: Union[int, str, Decimal]) -> Decimal:
    """
    Convert Lovelace (smallest unit) to ADA.
    1 ADA = 1,000,000 Lovelace
    
    Args:
        lovelace: Amount in Lovelace
        
    Returns:
        Equivalent amount in ADA as Decimal
    """
    if isinstance(lovelace, str):
        lovelace = Decimal(lovelace.replace(',', ''))
    else:
        lovelace = Decimal(str(lovelace))
    
    return lovelace / Decimal('1000000')

def ada_to_lovelace(ada: Union[int, str, Decimal]) -> Decimal:
    """
    Convert ADA to Lovelace (smallest unit).
    1 ADA = 1,000,000 Lovelace
    
    Args:
        ada: Amount in ADA
        
    Returns:
        Equivalent amount in Lovelace as Decimal
    """
    if isinstance(ada, str):
        ada = Decimal(ada.replace(',', ''))
    else:
        ada = Decimal(str(ada))
    
    return ada * Decimal('1000000')

def is_token_transfer(input_data: str) -> bool:
    """
    Determine if a transaction is a token transfer based on input data.
    
    Args:
        input_data: The transaction input data
        
    Returns:
        True if it's a token transfer, False otherwise
    """
    if not input_data or input_data == "0x" or input_data == "":
        return False
    
    parsed_data = parse_ada_input_data(input_data)
    
    # Check if the method matches a token transfer
    return parsed_data["method_name"] == "token_transfer"

def get_token_details(transaction_data):
    """
    استخراج جزئیات توکن از داده‌های تراکنش
    
    Args:
        transaction_data (dict): داده‌های تراکنش
        
    Returns:
        list: لیستی از دیکشنری‌های حاوی اطلاعات توکن‌ها
    """
    tokens = []
    try:
        # بررسی خروجی‌ها برای توکن‌ها
        if 'outputs' in transaction_data and isinstance(transaction_data['outputs'], list):
            for output in transaction_data['outputs']:
                if 'assets' in output and output['assets']:
                    for policy_id, assets in output['assets'].items():
                        for asset_name, amount in assets.items():
                            tokens.append({
                                'policy_id': policy_id,
                                'asset_name': asset_name,
                                'amount': amount,
                                'recipient': output.get('address', '')
                            })
        
        return tokens
    except Exception as e:
        logger.error(f"Error getting ADA token details: {e}")
        return [] 