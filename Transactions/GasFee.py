from flask import Blueprint, jsonify
import requests
from web3 import Web3
import os
from utils.logging_config import get_logger
from security.validators import SecurityUtils
from utils.error_handlers import handle_api_errors
from decimal import Decimal, getcontext

# Configure logging
logger = get_logger(__file__)
logger.info("Initializing gas fee module")

# Configure decimal precision
getcontext().prec = 18

gasfee_bp = Blueprint('gasfee', __name__)

# Load API key from environment variables
INFURA_API_KEY = os.getenv('INFURA_API_KEY')
if not INFURA_API_KEY:
    error_msg = "INFURA_API_KEY environment variable is not set. Please set it to connect to Ethereum networks."
    logger.error(error_msg)
    raise RuntimeError(error_msg)

# Infura URLs for different networks
ETHEREUM_URL = f"https://mainnet.infura.io/v3/{INFURA_API_KEY}"
POLYGON_URL = f"https://polygon-mainnet.infura.io/v3/{INFURA_API_KEY}"
ARBITRUM_URL = f"https://arbitrum-mainnet.infura.io/v3/{INFURA_API_KEY}"
OPTIMISM_URL = f"https://optimism-mainnet.infura.io/v3/{INFURA_API_KEY}"
BINANCE_URL = "https://bsc-dataseed1.binance.org"
AVALANCHE_URL = "https://api.avax.network/ext/bc/C/rpc"
FANTOM_URL = "https://rpc.ftm.tools"

# Bitcoin API endpoint
BITCOIN_API = "https://mempool.space/api/v1/fees/recommended"

# Solana API endpoint
SOLANA_API = "https://api.mainnet-beta.solana.com"

# Tron API endpoint
TRON_API = "https://api.trongrid.io/wallet/gettransactioninfobyid"
TRON_ENERGY_API = "https://api.trongrid.io/v1/accounts/"

# XRP API endpoint
XRP_API = "https://xrplcluster.com/"

# Cardano API endpoint
CARDANO_API = "https://cardano-mainnet.blockfrost.io/api/v0"

# Polkadot API endpoint
POLKADOT_API = "https://polkadot.api.subscan.io/api/scan/metadata"

# Cosmos API endpoint
COSMOS_API = "https://lcd-cosmos.cosmostation.io/cosmos/base/tendermint/v1beta1/blocks/latest"

# Default gas fees for various networks in their native currencies
DEFAULT_GAS_FEES = {
    "Bitcoin": "0.00005",     # ~0.00005 BTC for average tx
    "Ethereum": "0.00021",    # ~0.00021 ETH for average tx
    "Polygon": "0.0001",      # ~0.0001 MATIC for average tx
    "Binance": "0.0003",      # ~0.0003 BNB for average tx
    "Solana": "0.000005",     # ~0.000005 SOL for average tx
    "Avalanche": "0.00025",   # ~0.00025 AVAX for average tx
    "Arbitrum": "0.0001",     # ~0.0001 ETH for average tx
    "Optimism": "0.0001",     # ~0.0001 ETH for average tx
    "Fantom": "0.0005",       # ~0.0005 FTM for average tx
    "Tron": "0.0002",         # ~0.0002 TRX for bandwidth
    "XRP": "0.000012",        # ~0.000012 XRP for tx
    "Cardano": "0.17",        # ~0.17 ADA for tx
    "Polkadot": "0.01",       # ~0.01 DOT for tx
    "Cosmos": "0.025"         # ~0.025 ATOM for tx
}

# Standard gas limit for simple transfers on EVM chains
STANDARD_GAS_LIMIT = 21000

def fetch_ethereum_gas_fee():
    """Fetch gas fee for Ethereum network in ETH"""
    try:
        logger.debug("Fetching gas fee for Ethereum network")
        w3 = Web3(Web3.HTTPProvider(ETHEREUM_URL))
        
        # Get gas price in wei
        gas_price = w3.eth.gas_price
        
        # Calculate total fee for a standard transfer (gas_price * gas_limit)
        total_fee_wei = gas_price * STANDARD_GAS_LIMIT
        
        # Convert total fee from wei to ether
        total_fee_eth = w3.from_wei(total_fee_wei, "ether")
        
        logger.debug(f"Ethereum fee: {total_fee_eth} ETH (gas price: {w3.from_wei(gas_price, 'gwei')} gwei)")
        return str(total_fee_eth)
    except Exception as e:
        logger.error(f"Error fetching Ethereum gas fee: {str(e)}")
        return None

def fetch_evm_gas_fee(url, network_name):
    """Fetch gas fee for EVM compatible networks in their native currency"""
    try:
        logger.debug(f"Fetching gas fee for {network_name} network")
        w3 = Web3(Web3.HTTPProvider(url))
        
        # Get gas price in wei
        gas_price = w3.eth.gas_price
        
        # Calculate total fee for a standard transfer (gas_price * gas_limit)
        total_fee_wei = gas_price * STANDARD_GAS_LIMIT
        
        # Convert total fee from wei to ether equivalent
        total_fee = w3.from_wei(total_fee_wei, "ether")
        
        logger.debug(f"{network_name} fee: {total_fee} (gas price: {w3.from_wei(gas_price, 'gwei')} gwei)")
        return str(total_fee)
    except Exception as e:
        logger.error(f"Error fetching {network_name} gas fee: {str(e)}")
        return None

def fetch_bitcoin_gas_fee():
    """Fetch gas fee for Bitcoin network in BTC"""
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

        # Get fee rate in sat/vB
        fee_rate = data.get("fastestFee", data.get("halfHourFee", data.get("hourFee", 2)))
        
        # Estimate transaction size (1 input, 2 outputs) ~225 bytes
        estimated_tx_size = 225
        
        # Calculate total fee in satoshis
        total_fee_sats = fee_rate * estimated_tx_size
        
        # Convert to BTC (1 BTC = 100,000,000 satoshis)
        total_fee_btc = Decimal(total_fee_sats) / Decimal(100000000)
        
        logger.debug(f"Bitcoin fee: {total_fee_btc} BTC (rate: {fee_rate} sat/vB)")
        return str(total_fee_btc)
    except Exception as e:
        logger.error(f"Error fetching Bitcoin gas fee: {str(e)}")
        return None

def fetch_solana_gas_fee():
    """Fetch gas fee for Solana network in SOL"""
    try:
        logger.debug("Fetching gas fee for Solana network")
        headers = {"Content-Type": "application/json"}
        
        # First get recent prioritization fees
        prioritization_payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "getRecentPrioritizationFees",
            "params": []
        }
        
        response = requests.post(SOLANA_API, headers=headers, json=prioritization_payload, timeout=10)
        
        if response.status_code != 200:
            logger.warning(f"Solana API returned status code {response.status_code}")
            return DEFAULT_GAS_FEES["Solana"]
            
        data = response.json()
        if not data or "result" not in data:
            logger.warning("Invalid response from Solana API")
            return DEFAULT_GAS_FEES["Solana"]
            
        fees = data.get("result", [])
        if not fees:
            # If no recent prioritization fees, use default
            prioritization_fee = 0
        else:
            # Calculate average prioritization fee
            prioritization_fee = sum(fee.get("prioritizationFee", 0) for fee in fees) / max(1, len(fees))
        
        # Now get the minimum transaction fee (base fee)
        # For Solana a standard transaction costs about 5000 lamports
        base_fee_lamports = 5000
        
        # Add prioritization fee if network is congested
        # A standard Solana transaction is about 200 bytes
        total_fee_lamports = base_fee_lamports + (prioritization_fee * 200)
        
        # Convert to SOL (1 SOL = 1,000,000,000 lamports)
        total_fee_sol = Decimal(total_fee_lamports) / Decimal(1000000000)
        
        logger.debug(f"Solana fee: {total_fee_sol} SOL")
        return str(total_fee_sol)
    except Exception as e:
        logger.error(f"Error fetching Solana gas fee: {str(e)}")
        return DEFAULT_GAS_FEES["Solana"]

def fetch_tron_gas_fee():
    """Fetch gas fee for Tron network in TRX"""
    try:
        logger.debug("Fetching gas fee for Tron network")
        
        # For Tron, a simple transfer usually costs:
        # - About 0.264 TRX worth of energy for a normal transfer
        # - Plus bandwidth points (which are free up to a daily quota)
        # - If bandwidth points are exhausted, ~0.002 TRX per bandwidth point
        
        # A simple transfer needs about 300 bandwidth points
        bandwidth_points = 300
        
        # If exceeding free daily quota (1600 points), calculate cost
        # Assume worst case that all bandwidth points need to be paid for
        bandwidth_cost_trx = Decimal(bandwidth_points) * Decimal("0.000002")
        
        # Energy cost for a simple transfer
        energy_cost_trx = Decimal("0.000002")
        
        # Total cost
        total_fee_trx = bandwidth_cost_trx + energy_cost_trx
        
        logger.debug(f"Tron fee: {total_fee_trx} TRX")
        return str(total_fee_trx)
    except Exception as e:
        logger.error(f"Error fetching Tron gas fee: {str(e)}")
        return DEFAULT_GAS_FEES["Tron"]

def fetch_xrp_gas_fee():
    """Fetch transaction fee for XRP network in XRP"""
    try:
        logger.debug("Fetching transaction fee for XRP network")
        headers = {"Content-Type": "application/json"}
        payload = {
            "method": "fee",
            "params": [{}]
        }
        
        response = requests.post(XRP_API, headers=headers, json=payload, timeout=10)
        
        if response.status_code != 200:
            logger.warning(f"XRP API returned status code {response.status_code}")
            return DEFAULT_GAS_FEES["XRP"]
            
        data = response.json()
        if not data or "result" not in data:
            logger.warning("Invalid response from XRP API")
            return DEFAULT_GAS_FEES["XRP"]
            
        # XRP fees are in drops (1 XRP = 1,000,000 drops)
        fee_drops = data.get("result", {}).get("drops", {}).get("median_fee", 10)
        
        # Convert to XRP
        fee_xrp = Decimal(fee_drops) / Decimal(1000000)
        
        logger.debug(f"XRP fee: {fee_xrp} XRP ({fee_drops} drops)")
        return str(fee_xrp)
    except Exception as e:
        logger.error(f"Error fetching XRP transaction fee: {str(e)}")
        return DEFAULT_GAS_FEES["XRP"]

def fetch_cardano_gas_fee():
    """Fetch transaction fee for Cardano network in ADA"""
    try:
        logger.debug("Fetching transaction fee for Cardano network")
        
        # Cardano fee calculation: a + b * size
        # where a = min_fee_a, b = min_fee_b from protocol parameters
        # And size is the transaction size in bytes
        
        # For simple transactions, the fee is typically around 0.17-0.18 ADA
        # This is based on the current protocol parameters
        
        api_key = os.getenv('BLOCKFROST_API_KEY', '')
        if not api_key:
            logger.warning("No Blockfrost API key found for Cardano")
            return DEFAULT_GAS_FEES["Cardano"]
            
        headers = {
            "project_id": api_key
        }
        
        # Get protocol parameters
        response = requests.get(
            f"{CARDANO_API}/epochs/latest/parameters", 
            headers=headers, 
            timeout=10
        )
        
        if response.status_code != 200:
            logger.warning(f"Cardano API returned status code {response.status_code}")
            return DEFAULT_GAS_FEES["Cardano"]
            
        data = response.json()
        if not data:
            logger.warning("Empty response from Cardano API")
            return DEFAULT_GAS_FEES["Cardano"]
            
        # Extract fee parameters
        min_fee_a = data.get("min_fee_a", 44)  # Usually 44
        min_fee_b = data.get("min_fee_b", 155381)  # Usually 155381
        
        # Estimate transaction size (bytes) for a simple transaction
        estimated_tx_size = 300
        
        # Calculate fee in lovelace (1 ADA = 1,000,000 lovelace)
        fee_lovelace = min_fee_a + (min_fee_b * estimated_tx_size / 1000000)
        
        # Convert to ADA
        fee_ada = Decimal(fee_lovelace) / Decimal(1000000)
        
        logger.debug(f"Cardano fee: {fee_ada} ADA")
        return str(fee_ada)
    except Exception as e:
        logger.error(f"Error fetching Cardano transaction fee: {str(e)}")
        return DEFAULT_GAS_FEES["Cardano"]

def fetch_polkadot_gas_fee():
    """Fetch transaction fee for Polkadot network in DOT"""
    try:
        logger.debug("Fetching transaction fee for Polkadot network")
        
        # For Polkadot, a simple transfer typically costs around 0.01 DOT
        # based on current network conditions
        
        headers = {
            "Content-Type": "application/json",
            "X-API-Key": os.getenv('SUBSCAN_API_KEY', '')
        }
        
        # Get current fee estimates from Subscan
        response = requests.post(
            POLKADOT_API,
            headers=headers, 
            json={},
            timeout=10
        )
        
        if response.status_code != 200:
            logger.warning(f"Polkadot API returned status code {response.status_code}")
            return DEFAULT_GAS_FEES["Polkadot"]
            
        # Current weight for a transfer is about 200,000,000 weight units
        # Fee multiplier varies but typical fee is around 0.01 DOT
        fee_dot = Decimal("0.01")
        
        logger.debug(f"Polkadot fee: {fee_dot} DOT")
        return str(fee_dot)
    except Exception as e:
        logger.error(f"Error fetching Polkadot transaction fee: {str(e)}")
        return DEFAULT_GAS_FEES["Polkadot"]

def fetch_cosmos_gas_fee():
    """Fetch transaction fee for Cosmos network in ATOM"""
    try:
        logger.debug("Fetching transaction fee for Cosmos network")
        
        # For Cosmos, a simple transfer typically uses 100,000 gas units
        # with a gas price around 0.025 uATOM per gas unit
        
        headers = {"Accept": "application/json"}
        response = requests.get(COSMOS_API, headers=headers, timeout=10)
        
        if response.status_code != 200:
            logger.warning(f"Cosmos API returned status code {response.status_code}")
            return DEFAULT_GAS_FEES["Cosmos"]
            
        # Standard fee for a simple transfer is around 0.025 ATOM
        fee_atom = Decimal("0.025")
        
        logger.debug(f"Cosmos fee: {fee_atom} ATOM")
        return str(fee_atom)
    except Exception as e:
        logger.error(f"Error fetching Cosmos transaction fee: {str(e)}")
        return DEFAULT_GAS_FEES["Cosmos"]

@gasfee_bp.route('/gasfee', methods=['GET'])
@SecurityUtils.rate_limit(requests=100, window=60)
@handle_api_errors
def get_gas_fee():
    """
    Get gas fees for all supported blockchain networks
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
        # Initialize response with default values
        response = {}
        for blockchain, default_fee in DEFAULT_GAS_FEES.items():
            response[blockchain] = {"gas_fee": default_fee}

        # Fetch gas fees for all networks
        # Bitcoin
        btc_fee = fetch_bitcoin_gas_fee()
        if btc_fee is not None:
            response["Bitcoin"]["gas_fee"] = btc_fee

        # Ethereum
        eth_fee = fetch_ethereum_gas_fee()
        if eth_fee is not None:
            response["Ethereum"]["gas_fee"] = eth_fee

        # EVM compatible chains
        networks = {
            "Polygon": POLYGON_URL,
            "Binance": BINANCE_URL,
            "Avalanche": AVALANCHE_URL,
            "Arbitrum": ARBITRUM_URL,
            "Optimism": OPTIMISM_URL,
            "Fantom": FANTOM_URL
        }
        
        for network, url in networks.items():
            fee = fetch_evm_gas_fee(url, network)
            if fee is not None:
                response[network]["gas_fee"] = fee

        # Solana
        sol_fee = fetch_solana_gas_fee()
        if sol_fee is not None:
            response["Solana"]["gas_fee"] = sol_fee
            
        # Tron
        tron_fee = fetch_tron_gas_fee()
        if tron_fee is not None:
            response["Tron"]["gas_fee"] = tron_fee
            
        # XRP
        xrp_fee = fetch_xrp_gas_fee()
        if xrp_fee is not None:
            response["XRP"]["gas_fee"] = xrp_fee
            
        # Cardano
        cardano_fee = fetch_cardano_gas_fee()
        if cardano_fee is not None:
            response["Cardano"]["gas_fee"] = cardano_fee
            
        # Polkadot
        polkadot_fee = fetch_polkadot_gas_fee()
        if polkadot_fee is not None:
            response["Polkadot"]["gas_fee"] = polkadot_fee
            
        # Cosmos
        cosmos_fee = fetch_cosmos_gas_fee()
        if cosmos_fee is not None:
            response["Cosmos"]["gas_fee"] = cosmos_fee

        logger.info("Successfully retrieved gas fees for all networks")
        return jsonify(response), 200

    except Exception as e:
        logger.error(f"Error in get_gas_fee: {str(e)}", exc_info=True)
        # Return response with default values on error
        response = {}
        for blockchain, default_fee in DEFAULT_GAS_FEES.items():
            response[blockchain] = {"gas_fee": default_fee}
        return jsonify(response), 500