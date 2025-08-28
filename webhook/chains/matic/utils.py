from CC.utils.logging_config import get_logger

logger = get_logger(__name__)

def parse_matic_input_data(input_data):
    """
    Parse Polygon (MATIC) transaction input data
    
    Args:
        input_data (str): Transaction input data
        
    Returns:
        dict: Extracted information
    """
    logger.debug(f"Parsing MATIC input data: {input_data[:10]}...")
    
    # If input data is empty or too short, return an empty dictionary
    if not input_data or len(input_data) < 10:
        return {}
        
    # Extract method ID (first 4 bytes or 8 hex characters after 0x)
    method_id = input_data[:10]  # includes 0x and 8 hex characters
    
    # Implementation of parameter parsing based on method ID
    # This section will expand based on project needs
    
    # Recognize some common method IDs
    if method_id == '0xa9059cbb':  # transfer(address,uint256)
        return {
            'method_id': method_id,
            'method_name': 'transfer',
            'type': 'token_transfer'
        }
    elif method_id == '0x095ea7b3':  # approve(address,uint256)
        return {
            'method_id': method_id,
            'method_name': 'approve',
            'type': 'token_approval'
        }
    elif method_id == '0x23b872dd':  # transferFrom(address,address,uint256)
        return {
            'method_id': method_id,
            'method_name': 'transferFrom',
            'type': 'token_transfer_from'
        }
    
    # For other methods, just return the method ID
    return {
        'method_id': method_id,
        'type': 'unknown'
    }

def format_matic_address(address):
    """
    Format Polygon (MATIC) address (convert to standard format with lowercase letters)
    
    Args:
        address (str): MATIC address
        
    Returns:
        str: Formatted address
    """
    if not address:
        return None
        
    # Ensure the address starts with 0x
    if not address.startswith('0x'):
        address = '0x' + address
        
    # Convert to lowercase
    return address.lower()

def is_valid_matic_address(address):
    """
    Validate Polygon (MATIC) address
    
    Args:
        address (str): MATIC address
        
    Returns:
        bool: Whether the address is valid
    """
    if not address:
        return False
        
    # Check address length (0x + 40 hex characters)
    if not address.startswith('0x') or len(address) != 42:
        return False
        
    # Check valid characters (0-9, a-f, A-F)
    try:
        int(address[2:], 16)  # Convert hex part to a number
        return True
    except ValueError:
        return False 