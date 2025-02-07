import requests
from eth_account import Account
import logging
from tronpy.keys import PrivateKey
from config import (
    ETHERSCAN_API_URL, ETHERSCAN_API_KEY,
    TRONSCAN_API_URL, TRONSCAN_API_KEY,
    BNBSCAN_API_URL, BNBSCAN_API_KEY,
    COINMARKETCAP_API_URL, COINMARKETCAP_API_KEY,
    BaseConfig
)


class EtherscanService(BaseConfig):
    def __init__(self):
        super().__init__(ETHERSCAN_API_URL, ETHERSCAN_API_KEY)

    def generate_wallet(self) -> dict:
        """
        تولید کیف پول معتبر برای Ethereum.
        """
        account = Account.create()
        private_key = account.key.hex()
        public_address = account.address
        logging.info(f"Generated Ethereum Wallet - Address: {public_address}, PrivateKey: {private_key}")
        return {"address": public_address, "private_key": private_key} 

    def import_wallet(self, private_key: str, phrase_key: str = None) -> dict:
        """
        ایمپورت کیف پول برای Ethereum با استفاده از کلید خصوصی یا عبارت بازیابی.
        """
        try:
            account = Account.from_key(private_key)
            public_address = account.address
            logging.info(f"Imported Ethereum Wallet - Address: {public_address}")
            return {"address": public_address, "private_key": private_key}
        except Exception as e:
            logging.error(f"Error importing Ethereum wallet: {e}")
            return None

    def get_wallet_balance(self, public_address: str) -> dict:
        try:
            url = f"{self.base_url}?module=account&action=balance&address={public_address}&tag=latest&apikey={self.api_key}"
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            response_data = response.json()

            if response_data.get("status") == "1":
                return {"status": "1", "balance": response_data.get("result")}
            else:
                logging.error(f"Etherscan error: {response_data.get('message')}")
                return {"status": "0", "message": response_data.get("message")}

        except requests.exceptions.Timeout:
            logging.error("Timeout error while fetching Ethereum balance.")
            return {"status": "0", "message": "Timeout error"}
        except Exception as e:
            logging.error(f"Error in Etherscan get_wallet_balance: {e}", exc_info=True)
            return {"status": "0", "message": str(e)}



    def get_wallet_transactions(self, public_key: str) -> dict:
        params = {
            'module': 'account',
            'action': 'txlist',
            'address': public_key,
            'startblock': 0,
            'endblock': 99999999,
            'sort': 'asc',
            'apikey': self.api_key
        }
        return self._make_request(params)

    def _make_request(self, params: dict) -> dict:
        try:
            response = requests.get(self.api_url, params=params)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            return {'status': '0', 'message': str(e)}


class TronscanService(BaseConfig):
    def __init__(self):
        super().__init__(TRONSCAN_API_URL, TRONSCAN_API_KEY)

    def generate_wallet(self) -> dict:
        """
        تولید کیف پول معتبر برای Tron.
        """
        private_key = PrivateKey.random()
        public_address = private_key.public_key.to_base58check_address()
        return {"address": public_address, "private_key": private_key.hex()}  

    def import_wallet(self, private_key: str, phrase_key: str = None) -> dict:
        """
        ایمپورت کیف پول برای Tron با استفاده از کلید خصوصی.
        """
        try:
            private_key_obj = PrivateKey(bytes.fromhex(private_key))
            public_address = private_key_obj.public_key.to_base58check_address()
            logging.info(f"Imported Tron Wallet - Address: {public_address}")
            return {"address": public_address, "private_key": private_key}
        except Exception as e:
            logging.error(f"Error importing Tron wallet: {e}")
            return None  

    def get_wallet_balance(self, public_address: str) -> dict:
        try:
            url = f"{self.base_url}/account?address={public_address}"
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            response_data = response.json()

            if "balance" in response_data:
                return {"status": "1", "balance": str(response_data["balance"])}
            else:
                logging.warning(f"Tronscan response does not contain balance: {response_data}")
                return {"status": "0", "message": "No balance found"}

        except requests.exceptions.Timeout:
            logging.error("Timeout error while fetching Tron balance.")
            return {"status": "0", "message": "Timeout error"}
        except Exception as e:
            logging.error(f"Error in Tronscan get_wallet_balance: {e}", exc_info=True)
            return {"status": "0", "message": str(e)}



    def get_wallet_transactions(self, public_key: str) -> dict:
        params = {
            'module': 'account',
            'action': 'txlist',
            'address': public_key,
            'apikey': self.api_key
        }
        return self._make_request(params)

    def _make_request(self, params: dict) -> dict:
        try:
            response = requests.get(self.api_url, params=params)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            return {'status': '0', 'message': str(e)}


class BNBScanService(BaseConfig):
    def __init__(self):
        super().__init__(BNBSCAN_API_URL, BNBSCAN_API_KEY)

    def generate_wallet(self) -> dict:
        """
        تولید کیف پول معتبر برای Binance Smart Chain.
        """
        account = Account.create()
        private_key = account.key.hex()
        public_address = account.address
        return {"address": public_address, "private_key": private_key}  

    def import_wallet(self, private_key: str, phrase_key: str = None) -> dict:
        """
        ایمپورت کیف پول برای Binance Smart Chain با استفاده از کلید خصوصی.
        """
        try:
            account = Account.from_key(private_key)
            public_address = account.address
            logging.info(f"Imported Binance Smart Chain Wallet - Address: {public_address}")
            return {"address": public_address, "private_key": private_key}
        except Exception as e:
            logging.error(f"Error importing Binance Smart Chain wallet: {e}")
            return None  

    def get_wallet_balance(self, public_address: str) -> dict:
        try:
            url = f"{self.base_url}?module=account&action=balance&address={public_address}&tag=latest&apikey={self.api_key}"
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            response_data = response.json()

            if response_data.get("status") == "1":
                return {"status": "1", "balance": response_data.get("result")}
            else:
                logging.error(f"BSCScan error: {response_data.get('message')}")
                return {"status": "0", "message": response_data.get("message")}

        except requests.exceptions.Timeout:
            logging.error("Timeout error while fetching BNB balance.")
            return {"status": "0", "message": "Timeout error"}
        except Exception as e:
            logging.error(f"Error in BNBScan get_wallet_balance: {e}", exc_info=True)
            return {"status": "0", "message": str(e)}



    def get_wallet_transactions(self, public_key: str) -> dict:
        params = {
            'module': 'account',
            'action': 'txlist',
            'address': public_key,
            'startblock': 0,
            'endblock': 99999999,
            'sort': 'asc',
            'apikey': self.api_key
        }
        return self._make_request(params)

    def _make_request(self, params: dict) -> dict:
        try:
            response = requests.get(self.api_url, params=params)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            return {'status': '0', 'message': str(e)}


class CoinMarketCapService(BaseConfig):
    def __init__(self):
        super().__init__(COINMARKETCAP_API_URL, COINMARKETCAP_API_KEY)

    def get_token_price(self, symbol: str, convert: str = "USD") -> dict:
        """
        دریافت قیمت لحظه‌ای توکن با استفاده از CoinMarketCap.
        """
        headers = {
            'Accepts': 'application/json',
            'X-CMC_PRO_API_KEY': self.api_key,
        }
        params = {
            'symbol': symbol,
            'convert': convert
        }
        try:
            response = requests.get(self.api_url, headers=headers, params=params)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            return {'status': '0', 'message': str(e)}
