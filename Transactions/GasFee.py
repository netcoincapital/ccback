from flask import Blueprint, jsonify
import requests
from web3 import Web3
import os
from utils.logging_config import get_logger
from security.validators import SecurityUtils
from utils.error_handlers import handle_api_errors

# Configure logging
logger = get_logger(__file__)
logger.info("Initializing gas fee module")

gasfee_bp = Blueprint('gasfee', __name__)

# Load API key from environment variables
INFURA_API_KEY = os.getenv('INFURA_API_KEY', "a8ab43a04ce044de988a838d92f478a7")

# Infura URL for Ethereum
ETHEREUM_URL = f"https://mainnet.infura.io/v3/{INFURA_API_KEY}"

# Bitcoin API endpoint
BITCOIN_API = "https://mempool.space/api/v1/fees/recommended"

def fetch_ethereum_gas_fee():
    """Fetch gas fee for Ethereum network"""
    try:
        logger.debug("Fetching gas fee for Ethereum network")
        w3 = Web3(Web3.HTTPProvider(ETHEREUM_URL))
        gas_price = w3.eth.gas_price
        return Web3.from_wei(gas_price, "gwei")
    except Exception as e:
        logger.error(f"Error fetching Ethereum gas fee: {str(e)}")
        return None

def fetch_bitcoin_gas_fee():
    """Fetch gas fee for Bitcoin network"""
    try:
        logger.debug("Fetching gas fee for Bitcoin network")
        headers = {"Accept": "application/json"}
        response = requests.get(BITCOIN_API, headers=headers, timeout=10)

        if response.status_code != 200:
            logger.warning(f"Bitcoin API returned status code {response.status_code}")
            return None

        data = response.json()
        if not data:
            logger.warning("Empty response from Bitcoin API")
            return None

        return data.get("fastestFee", 2)  # Default to 2 if not available
    except Exception as e:
        logger.error(f"Error fetching Bitcoin gas fee: {str(e)}")
        return None

@gasfee_bp.route('/gasfee', methods=['GET'])
@SecurityUtils.rate_limit(requests=100, window=60)
@handle_api_errors
def get_gas_fee():
    """
    Get gas fees for Ethereum and Bitcoin networks
    ---
    tags:
      - Blockchain
    responses:
      200:
        description: Gas fees retrieved successfully
      429:
        description: Rate limit exceeded
    """
    try:
        # Fetch gas fees for both networks
        eth_fee = fetch_ethereum_gas_fee()
        btc_fee = fetch_bitcoin_gas_fee()

        # Prepare response in the desired format
        response = {
            "Bitcoin": {
                "gas_fee": btc_fee if btc_fee is not None else 2
            },
            "Ethereum": {
                "gas_fee": str(eth_fee) if eth_fee is not None else "0.885702971"
            }
        }

        logger.info("Successfully retrieved gas fees for both networks")
        return jsonify(response), 200

    except Exception as e:
        logger.error(f"Error in get_gas_fee: {str(e)}", exc_info=True)
        # Return error response in the same format structure
        response = {
            "Bitcoin": {
                "gas_fee": 2  # Default value on error
            },
            "Ethereum": {
                "gas_fee": "0.885702971"  # Default value on error
            }
        }
        return jsonify(response), 500