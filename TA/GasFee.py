from flask import Flask, Blueprint, jsonify
import requests
from web3 import Web3

gasfee_bp = Blueprint('gasfee', __name__)

# Infura API Key (Replace with your own)
INFURA_API_KEY = "a8ab43a04ce044de988a838d92f478a7"

# Infura URLs for EVM-based blockchains
INFURA_URLS = {
    "Ethereum": f"https://mainnet.infura.io/v3/{INFURA_API_KEY}",
    "Polygon": f"https://polygon-mainnet.infura.io/v3/{INFURA_API_KEY}",
    "Arbitrum": f"https://arbitrum-mainnet.infura.io/v3/{INFURA_API_KEY}",
    "Avalanche": f"https://avalanche-mainnet.infura.io/v3/{INFURA_API_KEY}",
    "Binance": f"https://bsc-mainnet.infura.io/v3/{INFURA_API_KEY}",
    "Solana": f"https://solana-mainnet.g.alchemy.com/v2/{INFURA_API_KEY}"
}

# API Endpoints for Non-EVM Networks

# API Keys for Non-EVM Blockchains
TRON_API_KEY = "61d401f5-27e5-4de7-81ae-a9a48a7fc5d8"
POLKADOT_API_KEY = "RRYN92DT9T4DFIYN6ATT7UIPS3Z9PW6B8S"
XRP_API_KEY = "your_xrp_api_key_here"


NON_EVM_APIS = {
    "Bitcoin": "https://mempool.space/api/v1/fees/recommended",
    "Tron": f"https://api.trongrid.io/v1/wallet/getnowblock?apiKey={TRON_API_KEY}",
    "Polkadot": "https://api.subscan.io/api/scan/metadata",
    "XRP": "https://s1.ripple.com:51234"
}

# Fetch gas fees from Infura for EVM-based networks
def fetch_infura_gas_fee(network):
    try:
        w3 = Web3(Web3.HTTPProvider(INFURA_URLS[network]))
        gas_price = w3.eth.gas_price
        return {"gas_fee": Web3.from_wei(gas_price, "gwei")}
    except Exception as e:
        return {"error": str(e)}

# Fetch gas fees from external APIs for non-EVM networks
def fetch_non_evm_gas_fee(network):
    try:
        headers = {"Accept": "application/json"}
        response = requests.get(NON_EVM_APIS[network], headers=headers, timeout=10)

        if response.status_code != 200:
            return {"error": f"API returned status code {response.status_code}"}

        data = response.json()
        if not data:
            return {"error": "Empty response from API"}

        if network == "Bitcoin":
            return {"gas_fee": data.get("fastestFee", "Unknown")}
        elif network == "Tron":
            return {"gas_fee": data.get("energyFee", data.get("bandwidth", "Unknown"))}
        elif network == "Polkadot":
            return {"gas_fee": data.get("data", {}).get("tokenDecimals", "Unknown")}
        elif network == "Solana":
            return {"gas_fee": data.get("average", "Unknown")}
        elif network == "XRP":
            return {"gas_fee": data.get("drops", {}).get("base_fee", "Unknown")}
        else:
            return {"error": "Unsupported network"}

    except Exception as e:
        return {"error": str(e)}

# Fetch gas fees for all networks
def fetch_all_gas_fees():
    gas_fees = {}

    # Fetch from Infura
    for network in INFURA_URLS.keys():
        gas_fees[network] = fetch_infura_gas_fee(network)

    # Fetch from other APIs
    for network in NON_EVM_APIS.keys():
        gas_fees[network] = fetch_non_evm_gas_fee(network)

    return gas_fees

# Define API route
@gasfee_bp.route('/gasfee', methods=['GET'])
def get_gas_fees():
    gas_fees = fetch_all_gas_fees()
    return jsonify(gas_fees)

# Initialize Flask app
app = Flask(__name__)
app.register_blueprint(gasfee_bp)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)