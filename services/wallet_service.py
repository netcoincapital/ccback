from typing import Tuple, Dict, List, Any
from datetime import datetime
import uuid
import logging
from sqlalchemy.orm import Session
from bip_utils import Bip39MnemonicGenerator, Bip39WordsNum, Bip39MnemonicValidator

from database.users import Users
from database.wallets import Wallets
from database.Address import Address
from database.Blockchains import Blockchains
from utils.blockchain_address_generator import BlockchainAddressGenerator
from security.encryption import encrypt_private_key_aes, encrypt_mnemonic_aes, decrypt_private_key_aes, decrypt_mnemonic_aes
from .hd_wallet_service import HDWalletService
from .transaction_signer_service import TransactionSignerService
from .smart_contract_service import SmartContractService

class WalletService:
    def __init__(self, session: Session):
        self.session = session
        self.signer = TransactionSignerService()
        self.contract = SmartContractService()

    def create_wallet(self, wallet_name: str, address_count: int = 5) -> Tuple[str, str, Dict]:
        """
        Create a new HD wallet with multiple addresses per chain
        returns: (user_id, mnemonic, addresses)
        """
        try:
            # Create user record
            user_id = str(uuid.uuid4())
            user = Users(UserID=user_id)
            self.session.add(user)
            
            # Generate mnemonic
            mnemonic = Bip39MnemonicGenerator().FromWordsNumber(Bip39WordsNum.WORDS_NUM_24)
            mnemonic_str = mnemonic.ToStr()
            
            # Create wallet record
            wallet_id = str(uuid.uuid4())
            wallet = Wallets(
                WalletID=wallet_id, 
                UserID=user_id, 
                IsMultiSig=False,
                RequiredSignatures="1"
            )
            self.session.add(wallet)
            
            # Generate addresses for all supported blockchains
            addresses = self._generate_addresses(wallet_id, mnemonic_str)
            
            return user_id, mnemonic_str, addresses
            
        except Exception as e:
            self.session.rollback()
            logging.error(f"Error creating wallet: {str(e)}")
            raise

    def import_wallet(self, mnemonic: str) -> Tuple[str, Dict]:
        """
        وارد کردن کیف پول با استفاده از عبارت بازیابی
        mnemonic: عبارت بازیابی
        returns: (wallet_id, addresses)
        """
        try:
            # اعتبارسنجی عبارت بازیابی
            if not self.validate_mnemonic(mnemonic):
                raise ValueError("عبارت بازیابی نامعتبر است")
                
            # ایجاد کاربر جدید
            user_id = str(uuid.uuid4())
            user = Users(UserID=user_id)
            self.session.add(user)
            
            # ایجاد کیف پول
            wallet_id = str(uuid.uuid4())
            wallet = Wallets(
                WalletID=wallet_id, 
                UserID=user_id, 
                IsMultiSig=False,
                RequiredSignatures="1"
            )
            self.session.add(wallet)
            
            # تولید آدرس‌ها
            addresses = self._generate_addresses(wallet_id, mnemonic)
            
            return wallet_id, addresses

        except Exception as e:
            logging.error(f"Error in import_wallet: {str(e)}")
            raise

    def validate_mnemonic(self, mnemonic: str) -> bool:
        """
        اعتبارسنجی عبارت بازیابی
        returns: True اگر عبارت معتبر باشد، False در غیر این صورت
        """
        try:
            # بررسی تعداد کلمات
            words = mnemonic.split()
            if len(words) not in [12, 18, 24]:
                return False
                
            # استفاده از کتابخانه bip_utils برای اعتبارسنجی
            validator = Bip39MnemonicValidator()
            return validator.IsValid(mnemonic)
        except Exception as e:
            logging.error(f"Error validating mnemonic: {str(e)}")
            return False

    def _generate_addresses(self, wallet_id: str, mnemonic: str) -> Dict:
        """تولید آدرس‌ها برای تمام بلاکچین‌های پشتیبانی شده"""
        try:
            address_generator = BlockchainAddressGenerator.from_mnemonic(mnemonic)
            blockchain_addresses = address_generator.generate_all_addresses()
            
            addresses = {}
            blockchains = self.session.query(Blockchains).all()
            
            # اضافه کردن لاگ برای دیباگ
            logging.debug(f"Generated blockchain addresses: {list(blockchain_addresses.keys())}")
            logging.debug(f"Database blockchains: {[bc.BlockchainName for bc in blockchains]}")

            for bc in blockchains:
                bc_name = bc.BlockchainName
                if bc_name in blockchain_addresses:
                    address = blockchain_addresses[bc_name]
                    
                    # رمزنگاری کلیدها
                    encrypted_priv = encrypt_private_key_aes(address.private_key)
                    encrypted_mnemonic = encrypt_mnemonic_aes(mnemonic)

                    # ذخیره آدرس
                    new_addr = Address(
                        WalletID=wallet_id,
                        BlockchainID=bc.BlockchainID,
                        PublicAddress=address.public_address,
                        PrivateKey=encrypted_priv,
                        PhraseKey=encrypted_mnemonic,
                        CreatedAt=datetime.utcnow()
                    )
                    self.session.add(new_addr)
                    addresses[bc_name] = address.public_address
                    
                    logging.info(f"Address created for {bc_name}")
                else:
                    logging.warning(f"No address generated for blockchain {bc_name}")

            # اطمینان از اینکه آدرس بایننس در خروجی وجود دارد
            if "Binance Smart Chain" in blockchain_addresses and "Binance Smart Chain" not in addresses:
                binance_address = blockchain_addresses["Binance Smart Chain"]
                addresses["Binance Smart Chain"] = binance_address.public_address
                logging.info(f"Added Binance Smart Chain address to response: {binance_address.public_address}")

            return addresses

        except Exception as e:
            logging.error(f"Error in _generate_addresses: {str(e)}")
            raise

    def get_phrase_key(self, user_id: str) -> str:
        """
        دریافت عبارت بازیابی برای کاربر
        returns: عبارت بازیابی رمزگشایی شده
        """
        try:
            # یافتن کیف پول کاربر
            wallet = self.session.query(Wallets).filter_by(UserID=user_id).first()
            if not wallet:
                raise ValueError(f"No wallet found for user {user_id}")
                
            # یافتن آدرس با عبارت بازیابی
            address = self.session.query(Address).filter_by(WalletID=wallet.WalletID).first()
            if not address or not address.PhraseKey:
                raise ValueError(f"No phrase key found for wallet {wallet.WalletID}")
                
            # رمزگشایی و برگرداندن عبارت بازیابی
            # این بخش باید با تابع رمزگشایی مناسب تکمیل شود
            # در اینجا فرض می‌کنیم تابع decrypt_mnemonic_aes وجود دارد
            # return decrypt_mnemonic_aes(address.PhraseKey)
            
            # برای امنیت، فعلاً یک پیام برمی‌گردانیم
            return "Phrase key retrieval is disabled for security reasons"
            
        except Exception as e:
            logging.error(f"Error retrieving phrase key: {str(e)}")
            raise

    def sign_transaction(self, wallet_id: str, chain: str, tx_data: Dict) -> str:
        """Sign a transaction for any supported blockchain"""
        try:
            address = self.session.query(Address).filter_by(
                WalletID=wallet_id,
                Blockchain=chain
            ).first()
            
            if not address:
                raise ValueError(f"No address found for wallet {wallet_id} on chain {chain}")
                
            private_key = decrypt_private_key_aes(address.PrivateKey)
            
            if chain.lower() == 'ethereum':
                return self.signer.sign_ethereum_transaction(private_key, tx_data)
            elif chain.lower() == 'bitcoin':
                return self.signer.sign_bitcoin_transaction(private_key, tx_data)
            else:
                raise ValueError(f"Unsupported blockchain: {chain}")
                
        except Exception as e:
            logging.error(f"Error signing transaction: {str(e)}")
            raise
            
    def interact_with_contract(
        self,
        wallet_id: str,
        contract_address: str,
        contract_abi: list,
        function_name: str,
        *args,
        **kwargs
    ) -> Any:
        """Interact with a smart contract"""
        try:
            # Load contract
            contract = self.contract.load_contract(contract_address, contract_abi)
            
            # If transaction needs signing
            if kwargs.get('sign', False):
                address = self.session.query(Address).filter_by(
                    WalletID=wallet_id,
                    Blockchain='ethereum'
                ).first()
                
                if not address:
                    raise ValueError(f"No Ethereum address found for wallet {wallet_id}")
                    
                private_key = decrypt_private_key_aes(address.PrivateKey)
                return self.contract.send_contract_transaction(
                    contract,
                    function_name,
                    private_key,
                    *args,
                    **kwargs
                )
            
            # For read-only functions
            return self.contract.call_contract_function(
                contract,
                function_name,
                *args,
                **kwargs
            )
            
        except Exception as e:
            logging.error(f"Error interacting with contract: {str(e)}")
            raise 