from sqlalchemy.orm import Session
import logging
from web3 import Web3
import requests

class BlockchainService:
    def __init__(self, session: Session):
        self.session = session
        self.infura_api_key = "a8ab43a04ce044de988a838d92f478a7"
        self.tron_api_key = "61d401f5-27e5-4de7-81ae-a9a48a7fc5d8"

    def get_gas_fee(self, network: str) -> dict:
        """Get gas fee for specified network"""
        if network in self._get_evm_networks():
            return self._get_evm_gas_fee(network)
        else:
            return self._get_non_evm_gas_fee(network)

    def _get_evm_networks(self):
        return {
            "Ethereum": f"https://mainnet.infura.io/v3/{self.infura_api_key}",
            "Polygon": f"https://polygon-mainnet.infura.io/v3/{self.infura_api_key}",
            "Arbitrum": f"https://arbitrum-mainnet.infura.io/v3/{self.infura_api_key}",
            "Avalanche": f"https://avalanche-mainnet.infura.io/v3/{self.infura_api_key}",
            "Binance": f"https://bsc-mainnet.infura.io/v3/{self.infura_api_key}"
        }

    def _get_evm_gas_fee(self, network: str) -> dict:
        try:
            w3 = Web3(Web3.HTTPProvider(self._get_evm_networks()[network]))
            gas_price = w3.eth.gas_price
            return {"gas_fee": Web3.from_wei(gas_price, "gwei")}
        except Exception as e:
            logging.error(f"Error getting EVM gas fee: {str(e)}")
            return {"error": str(e)}

    def _get_non_evm_gas_fee(self, network: str) -> dict:
        api_endpoints = {
            "Bitcoin": "https://mempool.space/api/v1/fees/recommended",
            "Tron": f"https://api.trongrid.io/v1/wallet/getnowblock?apiKey={self.tron_api_key}",
            "Solana": "https://api.mainnet-beta.solana.com"
        }

        try:
            response = requests.get(api_endpoints[network], timeout=10)
            return {"gas_fee": response.json()}
        except Exception as e:
            logging.error(f"Error getting non-EVM gas fee: {str(e)}")
            return {"error": str(e)}
