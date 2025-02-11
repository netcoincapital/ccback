# services.py
import hashlib
import hmac
import logging
import uuid
from datetime import datetime
from web3 import Web3
import os
from sqlalchemy.orm import Session
from config import HMAC_SECRET_KEY
from APIs import EtherscanService , TronscanService , BNBScanService , CoinMarketCapService
from database.users import Users
from database.wallets import Wallets
from database.UserHolding import UserHolding
from database.Currencies import Currencies
from database.Address import Address
from database.Blockchains import Blockchains
from eth_account import Account
import base64
import requests
from mnemonic import Mnemonic
from Crypto.Cipher import AES
from Crypto.Protocol.KDF import scrypt
from typing import Tuple

# تابع تولید UUID
def generate_uuid():
    return str(uuid.uuid4())

# تابع هش کردن رمز عبور با استفاده از HMAC
def hash_password(password):
    hashed = hmac.new(HMAC_SECRET_KEY.encode(), password.encode(), hashlib.sha256).hexdigest()
    return hashed

# تابع ایجاد کیف پول با استفاده از Infura API
def Generate(blockchain_name: str) -> dict:
    """
    Generate wallet address and private key based on the blockchain name.
    """
    if blockchain_name == "Ethereum":
        wallet = EtherscanService().generate_wallet()
    elif blockchain_name == "BNB":
        wallet = BNBScanService().generate_wallet()
    elif blockchain_name == "Tron":
        wallet = TronscanService().generate_wallet()
    else:
        raise ValueError(f"Unsupported blockchain: {blockchain_name}")

    return wallet

    
# تابع ذخیره اطلاعات UserHolding در پایگاه داده
def save_user_holding(session: Session, user_id, currency_id, amount):
    try:
        new_holding = UserHolding(
            UserID=user_id,
            CurrencyID=currency_id,
            Amount=amount,
            LastUpdated=datetime.utcnow()
        )
        session.add(new_holding)
        session.commit()
        logging.info("User holding data saved successfully to database!")
    except Exception as error:
        session.rollback()
        logging.error(f"Error while saving user holding data to database: {error}")
        raise error


# ذخیره اطلاعات کاربران در جدول Users
def save_user_to_database(session: Session, user_data: dict):
    try:
        new_user = Users(
            Username=user_data['Username'],
            Password_Hash=user_data['Password_Hash'],
            Email=user_data.get('Email'),
            PhraseKey=user_data.get('PhraseKey'),
            Created_At=datetime.utcnow(),
            Updated_At=datetime.utcnow()
        )
        session.add(new_user)
        session.commit()
        logging.info("User data saved successfully to database!")
    except Exception as error:
        session.rollback()
        logging.error(f"Error while saving user data to database: {error}")
        raise error


# ذخیره اطلاعات ارزی در جدول Currencies
def save_currency_to_database(session: Session, currency_data: dict):
    try:
        new_currency = Currencies(
            CurrencyName=currency_data['CurrencyName'],
            Icon=currency_data['Icon'],
            Symbol=currency_data['Symbol'],
            BlockchainID=currency_data['BlockchainID'],
            DecimalPlaces=currency_data['DecimalPlaces'],
            IsToken=currency_data.get('IsToken', False),
            SmartContractAddress=currency_data.get('SmartContractAddress'),
            CreatedAt=datetime.utcnow(),
            UpdatedAt=datetime.utcnow()
        )
        session.add(new_currency)
        session.commit()
        logging.info("Currency data saved successfully to database!")
    except Exception as error:
        session.rollback()
        logging.error(f"Error while saving currency data to database: {error}")
        raise error


# ذخیره آدرس‌ها در جدول Address
def save_address_to_database(session: Session, address_data: dict):
    try:
        new_address = Address(
            WalletID=address_data['WalletID'],
            BlockchainID=address_data['BlockchainID'],
            PublicAddress=address_data['PublicAddress'],
            PrivateKey=address_data['PrivateKey'],
            CreatedAt=datetime.utcnow()
        )
        session.add(new_address)
        session.commit()
        logging.info("Address data saved successfully to database!")
    except Exception as error:
        session.rollback()
        logging.error(f"Error while saving address data to database: {error}")
        raise error


# ذخیره بلاکچین‌ها در جدول Blockchains
def save_blockchain_to_database(session: Session, blockchain_data: dict):
    try:
        new_blockchain = Blockchains(
            BlockchainName=blockchain_data['BlockchainName'],
            Symbol=blockchain_data['Symbol'],
            ChainCode=blockchain_data['ChainCode'],
            CreatedAt=datetime.utcnow(),
            UpdatedAt=datetime.utcnow()
        )
        session.add(new_blockchain)
        session.commit()
        logging.info("Blockchain data saved successfully to database!")
    except Exception as error:
        session.rollback()
        logging.error(f"Error while saving blockchain data to database: {error}")
        raise error


# تابع ذخیره کیف پول در پایگاه داده
def save_wallet_to_database(session: Session, user_id, wallet_name, wallet_address, is_multisig, required_signatures):
    try:
        new_wallet = Wallets(
            WalletID=generate_uuid(),
            UserID=user_id,
            Wallet_Name=wallet_name,
            # اطمینان از اینکه آدرس در مدل Wallets درست استفاده شده است
            Wallet_Address=wallet_address,  
            IsMultiSig=is_multisig,
            Required_Signatures=required_signatures
        )
        session.add(new_wallet)
        session.commit()
        logging.info("Wallet data saved successfully to database!")
    except Exception as error:
        session.rollback()
        logging.error(f"Error while saving wallet data to database: {error}")
        raise error


# تابع بررسی کلید خصوصی در بلاکچین
def check_private_key_in_blockchain(private_key):
    try:
        # تبدیل private_key به آدرس عمومی
        account = Account.from_key(private_key)
        public_address = account.address

        # اینجا اتصال به بلاکچین با Web3 یا Infura قبلاً انجام شده و نیازی به تعریف مجدد نیست.

        # بررسی اینکه آیا آدرس عمومی معتبر است یا خیر
        if public_address:
            logging.info(f"Wallet found on blockchain for address: {public_address}")
            return True
        else:
            logging.warning(f"Wallet not found on blockchain for address: {public_address}")
            return False
    except Exception as e:
        logging.error(f"Error checking private key on blockchain: {e}")
        return False  

# بروزرسانی کلاس CheckBlockchain 
class CheckBlockchain:
    def __init__(self):
        self.etherscan_service = EtherscanService()
        self.tronscan_service = TronscanService()
        self.bnbscan_service = BNBScanService()

    def identify_blockchain(self, public_address: str) -> str:
        """
        بررسی نوع بلاکچین بر اساس آدرس عمومی.
        """
        if not isinstance(public_address, str):
            logging.error("Invalid public address format")
            return 'Unknown Blockchain'

        logging.info(f"Attempting to identify blockchain for address: {public_address}")

        if public_address.startswith('0x'):  # بررسی آدرس‌های Ethereum و BNB
            try:
                eth_balance = self.etherscan_service.get_wallet_balance(public_address)
                logging.info(f"Response from Etherscan: {eth_balance}")
                if eth_balance.get("status") == "1" and int(eth_balance.get("balance", 0)) >= 0:
                    logging.info("Blockchain identified as Ethereum")
                    return 'Ethereum'

                bnb_balance = self.bnbscan_service.get_wallet_balance(public_address)
                logging.info(f"Response from BscScan: {bnb_balance}")
                if bnb_balance.get("status") == "1" and int(bnb_balance.get("balance", 0)) >= 0:
                    logging.info("Blockchain identified as Binance Smart Chain")
                    return 'Binance Smart Chain'
            except Exception as e:
                logging.error(f"Error identifying Ethereum/BSC: {e}")
                return 'Unknown Blockchain'

        elif public_address.startswith('T'):  # بررسی آدرس‌های Tron
            try:
                tron_balance = self.tronscan_service.get_wallet_balance(public_address)
                if tron_balance.get("status") == "1":
                    logging.info("Blockchain identified as Tron")
                    return 'Tron'
            except Exception as e:
                logging.error(f"Error identifying Tron: {e}")
                return 'Unknown Blockchain'

        logging.info("Unknown Blockchain format")
        return 'Unknown Blockchain'

    def import_wallet(self, blockchain_name: str, private_key: str, phrase_key: str = None) -> dict:
        """
        ایمپورت کیف پول برای بلاکچین مشخص.
        """
        try:
            if blockchain_name == "Ethereum":
                return self.etherscan_service.import_wallet(private_key, phrase_key)
            elif blockchain_name == "Tron":
                return self.tronscan_service.import_wallet(private_key, phrase_key)
            elif blockchain_name == "BNB":
                return self.bnbscan_service.import_wallet(private_key, phrase_key)
            else:
                logging.warning(f"Unsupported blockchain: {blockchain_name}")
                return None
        except Exception as e:
            logging.error(f"Error importing wallet for blockchain {blockchain_name}: {e}")
            return None

    def generate_wallet(self, blockchain_name: str) -> dict:
        """
        تولید کیف پول جدید برای بلاکچین مشخص.
        """
        try:
            if blockchain_name == "Ethereum":
                wallet = self.etherscan_service.generate_wallet()
                logging.info(f"Generated Ethereum wallet: {wallet}")
                return wallet
            elif blockchain_name == "Tron":
                wallet = self.tronscan_service.generate_wallet()
                logging.info(f"Generated Tron wallet: {wallet}")
                return wallet
            elif blockchain_name == "BNB":
                wallet = self.bnbscan_service.generate_wallet()
                logging.info(f"Generated BNB wallet: {wallet}")
                return wallet
            else:
                logging.warning(f"Unsupported blockchain: {blockchain_name}")
                return None
        except Exception as e:
            logging.error(f"Error generating wallet for blockchain {blockchain_name}: {e}")
            return None

    def get_wallet_balance(self, blockchain_name: str, public_address: str) -> dict:
        try:
            if blockchain_name == "Ethereum":
                response = self.etherscan_service.get_wallet_balance(public_address)
            elif blockchain_name == "Tron":
                response = self.tronscan_service.get_wallet_balance(public_address)
            elif blockchain_name == "BNB":
                response = self.bnbscan_service.get_wallet_balance(public_address)
            else:
                logging.warning(f"Unsupported blockchain: {blockchain_name}")
                return {"status": "0", "message": "Unsupported blockchain type"}

        # بررسی وضعیت پاسخ
            if response.get("status") == "1":
                balance = response.get("balance", "0")
                logging.info(f"Balance fetched successfully for {blockchain_name}: {balance}")
                return {"status": "1", "balance": balance}
            else:
                logging.warning(f"Error fetching balance for {blockchain_name}: {response.get('message')}")
                return {"status": "0", "message": response.get('message')}

        except Exception as e:
            logging.error(f"Error fetching balance for {blockchain_name}: {e}", exc_info=True)
            return {"status": "0", "message": str(e)}

    
class EtherscanService:
    def __init__(self):
        self.api_key = "YOUR_ETHERSCAN_API_KEY"
        self.base_url = "https://api.etherscan.io/api"

    def generate_wallet(self):
        private_key = os.urandom(32).hex()
        public_address = f"0x{hashlib.sha256(private_key.encode()).hexdigest()[:40]}"
        return {"address": public_address, "private_key": private_key}

    def import_wallet(self, private_key: str, phrase_key: str = None) -> dict:
        try:
            # برای اتریوم، آدرس را از private_key با Account.from_key می‌گیریم
            account = Account.from_key(private_key)
            public_address = account.address
            return {"address": public_address, "private_key": private_key}
        except Exception as e:
            logging.error(f"Error importing Ethereum wallet: {e}")
            return None

    def get_wallet_balance(self, public_address: str) -> dict:
        try:
            url = f"{self.base_url}?module=account&action=balance&address={public_address}&tag=latest&apikey={self.api_key}"
            response = requests.get(url)
            response_data = response.json()

            if response_data.get("status") == "1":
                return {"status": "1", "balance": response_data.get("result")}
            else:
                return {"status": "0", "message": response_data.get("message")}
        except Exception as e:
            logging.error(f"Error in Etherscan get_wallet_balance: {e}")
            return {"status": "0", "message": str(e)}


class BNBScanService:
    def __init__(self):
        self.api_key = "YOUR_BSCSCAN_API_KEY"
        self.base_url = "https://api.bscscan.com/api"

    def generate_wallet(self):
        private_key = os.urandom(32).hex()
        public_address = f"0x{hashlib.sha256(private_key.encode()).hexdigest()[:40]}"
        return {"address": public_address, "private_key": private_key}

    def import_wallet(self, private_key: str, phrase_key: str = None) -> dict:
        try:
            # برای BNB (BSC) نیز مانند اتریوم از Account.from_key استفاده می‌کنیم
            account = Account.from_key(private_key)
            public_address = account.address
            return {"address": public_address, "private_key": private_key}
        except Exception as e:
            logging.error(f"Error importing Binance Smart Chain wallet: {e}")
            return None

    def get_wallet_balance(self, public_address: str) -> dict:
        try:
            url = f"{self.base_url}?module=account&action=balance&address={public_address}&tag=latest&apikey={self.api_key}"
            response = requests.get(url)
            response_data = response.json()

            if response_data.get("status") == "1":
                return {"status": "1", "balance": response_data.get("result")}
            else:
                return {"status": "0", "message": response_data.get("message")}
        except Exception as e:
            logging.error(f"Error in BNBScan get_wallet_balance: {e}")
            return {"status": "0", "message": str(e)}


class TronscanService:
    def __init__(self):
        self.base_url = "https://api.tronscan.org/api"

    def generate_wallet(self):
        private_key = os.urandom(32).hex()
        public_address = f"T{hashlib.sha256(private_key.encode()).hexdigest()[:33]}"
        return {"address": public_address, "private_key": private_key}

    def import_wallet(self, private_key: str, phrase_key: str = None) -> dict:
        try:
            # برای ترون از PrivateKey و to_base58check_address استفاده می‌کنیم
            private_key_obj = private_key(bytes.fromhex(private_key))
            public_address = private_key_obj.public_key.to_base58check_address()
            return {"address": public_address, "private_key": private_key}
        except Exception as e:
            logging.error(f"Error importing Tron wallet: {e}")
            return None

    def get_wallet_balance(self, public_address: str) -> dict:
        try:
            url = f"{self.base_url}/account?address={public_address}"
            response = requests.get(url)
            response_data = response.json()

            if "balance" in response_data:
                return {"status": "1", "balance": str(response_data["balance"])}
            else:
                return {"status": "0", "message": "No balance found"}
        except Exception as e:
            logging.error(f"Error in Tronscan get_wallet_balance: {e}")
            return {"status": "0", "message": str(e)}



# تابع جدید برای دریافت موجودی از بلاکچین‌های مختلف
def get_wallet_balance(blockchain_type: str, public_address: str):
    """
    دریافت موجودی کیف پول بر اساس نوع بلاکچین.
    """
    try:
        if blockchain_type == 'Ethereum':
            return EtherscanService().get_wallet_balance(public_address)
        elif blockchain_type == 'Tron':
            return TronscanService().get_wallet_balance(public_address)
        elif blockchain_type == 'Binance Smart Chain':
            return BNBScanService().get_wallet_balance(public_address)
        else:
            logging.error("Unsupported blockchain type")
            return {"status": "0", "message": "Unsupported blockchain type"}
    except Exception as e:
        logging.error(f"Error while fetching wallet balance: {e}")
        return {"status": "0", "message": str(e)}

class CurrencyPriceService:
    def __init__(self):
        self.coin_market_cap = CoinMarketCapService()
        self.logger = logging.getLogger(self.__class__.__name__)

    def get_latest_prices(self, symbols: list[str], convert: str = "USD") -> dict:
        """
        دریافت قیمت لحظه‌ای چندین ارز دیجیتال.

        :param symbols: لیستی از نماد ارزهای دیجیتال (مانند ['BTC', 'ETH']).
        :param convert: ارز تبدیل (پیش‌فرض: 'USD').
        :return: دیکشنری شامل قیمت لحظه‌ای هر ارز یا دیکشنری خطا.
        """
        try:
            self.logger.info(f"Fetching latest prices for symbols: {symbols}, convert: {convert}")
            symbol_str = ",".join(symbols)
            response = self.coin_market_cap.get_token_price(symbol_str, convert)

            if isinstance(response, str):
                self.logger.error(f"Error fetching prices: {response}")
                return {"status": "error", "message": response}

            if response.get("status") and response["status"].get("error_code") == 0:
                prices = {}
                for symbol in symbols:
                    price_data = response["data"].get(symbol)
                    if price_data:
                        prices[symbol] = price_data["quote"][convert]["price"]
                    else:
                        prices[symbol] = None
                self.logger.info(f"Prices fetched successfully: {prices}")
                return prices
            else:
                error_msg = response.get("status", {}).get("error_message", "Unknown error")
                self.logger.error(f"Error fetching prices: {error_msg}")
                return {"status": "error", "message": error_msg}
        except Exception as e:
            self.logger.error(f"Exception in get_latest_prices: {str(e)}")
            return {"status": "error", "message": str(e)}

    def get_24h_changes(self, symbols: list[str], convert: str = "USD") -> dict:
        """
        دریافت درصد تغییرات قیمت ۲۴ ساعته برای هر ارز دیجیتال.

        :param symbols: لیستی از نماد ارزهای دیجیتال (مانند ['BTC', 'ETH']).
        :param convert: ارز تبدیل (پیش‌فرض: 'USD').
        :return: دیکشنری شامل درصد تغییر ۲۴ ساعته هر ارز یا مقدار None در صورت نبود داده.
        """
        try:
            self.logger.info(f"Fetching 24h changes for symbols: {symbols}, convert: {convert}")
            symbol_str = ",".join(symbols)
            response = self.coin_market_cap.get_token_price(symbol_str, convert)

            if isinstance(response, str):
                self.logger.error(f"Error fetching 24h changes: {response}")
                return {symbol: None for symbol in symbols}

            if response.get("status") and response["status"].get("error_code") == 0:
                changes = {}
                for symbol in symbols:
                    price_data = response["data"].get(symbol)
                    if price_data:
                        changes[symbol] = price_data["quote"][convert]["percent_change_24h"]
                    else:
                        changes[symbol] = None
                self.logger.info(f"24h changes fetched successfully: {changes}")
                return changes
            else:
                error_msg = response.get("status", {}).get("error_message", "Unknown error")
                self.logger.error(f"Error fetching 24h changes: {error_msg}")
                return {symbol: None for symbol in symbols}
        except Exception as e:
            self.logger.error(f"Exception in get_24h_changes: {str(e)}")
            return {symbol: None for symbol in symbols}

class PhraseKeyManager:
    
    def __init__(self):
        self.mnemonic = Mnemonic("english")
    
    # تولید Mnemonic phrase
    def generate_mnemonic_phrase(self) -> str:
        entropy = os.urandom(16)  # تولید 128 بیت برای عبارت 12 کلمه‌ای
        phrase = self.mnemonic.to_mnemonic(entropy)
        return phrase
    
    # تبدیل Mnemonic phrase به Seed
    def generate_seed_from_mnemonic(self, phrase: str, passphrase: str = '') -> bytes:
        seed = hashlib.pbkdf2_hmac('sha512', phrase.encode('utf-8'), passphrase.encode('utf-8'), 2048)
        return seed
    
    # تولید کلید امن از رمز عبور با Scrypt
    def generate_key_from_password(self, password: str, salt: bytes = None) -> Tuple[bytes, bytes]:
        if salt is None:
            salt = os.urandom(16)  # تولید salt تصادفی
        key = scrypt(password, salt, 32, N=2**14, r=8, p=1)
        return key, salt
    
    # رمزنگاری Seed با AES-GCM
    def encrypt_seed_with_aes(self, seed: bytes, key: bytes) -> Tuple[bytes, bytes, bytes]:
        cipher = AES.new(key, AES.MODE_GCM)
        ciphertext, tag = cipher.encrypt_and_digest(seed)
        return ciphertext, cipher.nonce, tag
    
    # رمزگشایی Seed با AES-GCM
    def decrypt_seed_with_aes(self, ciphertext: bytes, key: bytes, nonce: bytes, tag: bytes) -> bytes:
        cipher = AES.new(key, AES.MODE_GCM, nonce=nonce)
        decrypted_seed = cipher.decrypt_and_verify(ciphertext, tag)
        return decrypted_seed
    
    # ذخیره‌سازی امن Seed و ایجاد یک خروجی Base64
    def save_secure_seed(self, mnemonic_phrase: str, password: str) -> str:
        # تولید Seed از Mnemonic phrase
        seed = self.generate_seed_from_mnemonic(mnemonic_phrase)
        
        # تولید کلید امن از رمز عبور
        key, salt = self.generate_key_from_password(password)
        
        # رمزنگاری Seed با AES
        ciphertext, nonce, tag = self.encrypt_seed_with_aes(seed, key)
        
        # ترکیب همه اطلاعات در یک رشته باینری
        combined_data = salt + nonce + tag + ciphertext
        
        # تبدیل داده‌ها به Base64
        encrypted_base64 = base64.b64encode(combined_data).decode('utf-8')
        
        return encrypted_base64
    
    # احراز هویت با استفاده از Mnemonic phrase
    def authenticate_user(self, mnemonic_phrase: str, password: str, encrypted_base64: str) -> str:
        # تبدیل Base64 به باینری
        combined_data = base64.b64decode(encrypted_base64)
        
        # جدا کردن salt، nonce، tag و ciphertext
        salt = combined_data[:16]
        nonce = combined_data[16:32]
        tag = combined_data[32:48]
        ciphertext = combined_data[48:]
        
        # تولید Seed از Mnemonic phrase
        seed = self.generate_seed_from_mnemonic(mnemonic_phrase)
        
        # تولید کلید با استفاده از رمز عبور و salt
        key, _ = self.generate_key_from_password(password, salt)
        
        # رمزگشایی Seed
        decrypted_seed = self.decrypt_seed_with_aes(ciphertext, key, nonce, tag)
        
        if seed == decrypted_seed:
            return "valid seed"
        else:
            return "not valid seed"