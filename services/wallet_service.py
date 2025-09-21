from typing import Tuple, Dict, List, Any
from datetime import datetime
import uuid
import logging
import os
import json
from sqlalchemy.orm import Session
from bip_utils import Bip39MnemonicGenerator, Bip39WordsNum, Bip39MnemonicValidator
from uuid import uuid4
from sqlalchemy import func
from CC.errors.common_errors import ResourceAlreadyExists
from CC.services.blockchain_service import get_blockchain_service
from CC.services.hd_wallet_service import HDWalletService
from dotenv import load_dotenv
# import تنبل داخل تابع مصرف‌کننده انجام می‌شود
import threading
import concurrent.futures

# Setup logging
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

from CC.database.users import Users
from CC.database.wallets import Wallets
from CC.database.Address import Address
from CC.database.Blockchains import Blockchains
from CC.utils.blockchain_address_generator import BlockchainAddressGenerator
from CC.security.encryption import encrypt_private_key_aes, encrypt_mnemonic_aes, decrypt_private_key_aes, decrypt_mnemonic_aes
from .hd_wallet_service import HDWalletService
from .transaction_signer_service import TransactionSignerService
from .smart_contract_service import SmartContractService

class WalletService:
    def __init__(self, session: Session):
        self.session = session
        self.signer = TransactionSignerService()
        self.contract = SmartContractService()
        
    def create_wallet(self, wallet_name: str, address_count: int = 5, user_ip: str = None, user_device: str = None) -> Tuple[str, str, str, Dict]:
        """
        Create a new HD wallet with multiple addresses per chain
        wallet_name: نام کیف پول
        address_count: تعداد آدرس‌ها برای هر بلاکچین
        user_ip: آدرس IP کاربر
        user_device: اطلاعات دستگاه کاربر
        returns: (user_id, wallet_id, mnemonic, addresses)
        """
        try:
            # Create user record
            user_id = str(uuid.uuid4())
            user = Users(
                UserID=user_id,
                IP=user_ip,
                Device=user_device
            )
            self.session.add(user)
            logger.info(f"Created new user {user_id} with IP={user_ip}, Device={user_device}")
            
            # Test different word counts
            try:
                # Try with 12 words
                mnemonic12 = Bip39MnemonicGenerator().FromWordsNumber(Bip39WordsNum.WORDS_NUM_12)
                mnemonic12_str = mnemonic12.ToStr()
                word_count12 = len(mnemonic12_str.split())
                logger.info(f"Generated 12-word mnemonic with {word_count12} words: {mnemonic12_str}")
                
                # Try with 24 words
                mnemonic24 = Bip39MnemonicGenerator().FromWordsNumber(Bip39WordsNum.WORDS_NUM_24)
                mnemonic24_str = mnemonic24.ToStr()
                word_count24 = len(mnemonic24_str.split())
                logger.info(f"Generated 24-word mnemonic with {word_count24} words: {mnemonic24_str}")
                
                # Use the 12-word mnemonic
                mnemonic = mnemonic12
                mnemonic_str = mnemonic12_str
            except Exception as e:
                logger.error(f"Error testing mnemonic generation: {str(e)}")
                # Fallback to 24 words if 12 words fails
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
            addresses = self._generate_addresses(wallet_id, user_id, mnemonic_str)
            
            # Address registration with webhook system is now handled asynchronously
            # _register_addresses_with_webhook is called in a new thread inside _generate_addresses
            
            return user_id, wallet_id, mnemonic_str, addresses
            
        except Exception as e:
            self.session.rollback()
            logger.error(f"Error creating wallet: {str(e)}")
            raise

    def import_wallet(self, mnemonic: str, user_ip: str = None, user_device: str = None) -> Tuple[str, str, Dict, str]:
        """
        ایمپورت کیف پول موجود با استفاده از عبارت بازیابی
        mnemonic: عبارت بازیابی
        user_ip: آدرس IP کاربر
        user_device: اطلاعات دستگاه کاربر
        returns: (wallet_id, user_id, addresses, mnemonic)
        """
        try:
            # اعتبارسنجی عبارت بازیابی
            if not self.validate_mnemonic(mnemonic):
                raise ValueError("Invalid mnemonic phrase. Please check your recovery phrase and try again.")
            
            # تولید آدرس‌ها از Mnemonic
            address_generator = BlockchainAddressGenerator.from_mnemonic(mnemonic)
            blockchain_addresses = address_generator.generate_all_addresses()
            
            if not blockchain_addresses:
                raise ValueError("Failed to generate any addresses from this mnemonic")
            
            # بررسی آیا این آدرس‌ها قبلاً در سیستم وجود دارند
            # برای این کار، آدرس اتریوم را به عنوان شناسه اصلی استفاده می‌کنیم
            eth_address = None
            if "Ethereum" in blockchain_addresses:
                eth_address = blockchain_addresses["Ethereum"].public_address
            
            if not eth_address:
                raise ValueError("Could not generate Ethereum address from this mnemonic")
            
            # بررسی آیا این آدرس قبلاً در سیستم وجود دارد
            existing_address = self.session.query(Address).filter_by(PublicAddress=eth_address).first()
            
            if existing_address:
                # اگر آدرس قبلاً وجود داشته باشد، کیف پول و کاربر مربوطه را بازیابی می‌کنیم
                wallet_id = existing_address.WalletID
                wallet = self.session.query(Wallets).filter_by(WalletID=wallet_id).first()
                
                if not wallet:
                    raise ValueError("Wallet not found for the existing address")
                
                user_id = wallet.UserID
                
                # به‌روزرسانی اطلاعات IP و Device کاربر اگر ارائه شده باشند
                if user_ip or user_device:
                    user = self.session.query(Users).filter_by(UserID=user_id).first()
                    if user:
                        if user_ip:
                            user.IP = user_ip
                        if user_device:
                            user.Device = user_device
                        logger.info(f"Updated user info for existing user {user_id}: IP={user_ip}, Device={user_device}")
                
                logger.info(f"Found existing wallet with ID {wallet_id} for user {user_id}")
                
                # بازیابی تمام آدرس‌های مرتبط با این کیف پول
                addresses = {}
                wallet_addresses = self.session.query(Address, Blockchains).join(
                    Blockchains, Address.BlockchainID == Blockchains.BlockchainID
                ).filter(Address.WalletID == wallet_id).all()
                
                for addr, blockchain in wallet_addresses:
                    addresses[blockchain.BlockchainName] = addr.PublicAddress
                
                return wallet_id, user_id, addresses, mnemonic
            else:
                # اگر آدرس قبلاً وجود نداشته باشد، یک کاربر و کیف پول جدید ایجاد می‌کنیم
                user_id = str(uuid.uuid4())
                user = Users(
                    UserID=user_id,
                    IP=user_ip,
                    Device=user_device
                )
                self.session.add(user)
                logger.info(f"Created new user {user_id} with IP={user_ip}, Device={user_device}")
                
                wallet_id = str(uuid.uuid4())
                wallet = Wallets(
                    WalletID=wallet_id, 
                    UserID=user_id, 
                    IsMultiSig=False,
                    RequiredSignatures="1"
                )
                self.session.add(wallet)
                
                # ذخیره آدرس‌ها در دیتابیس
                addresses = {}
                blockchains = self.session.query(Blockchains).all()
                blockchain_map = {bc.BlockchainName: bc for bc in blockchains}
                
                # Store formatted addresses for webhook registration
                webhook_formatted_addresses = []
                
                for bc_name, address_obj in blockchain_addresses.items():
                    if bc_name in blockchain_map:
                        bc = blockchain_map[bc_name]
                        
                        # رمزنگاری کلیدها
                        encrypted_priv = encrypt_private_key_aes(address_obj.private_key)
                        encrypted_mnemonic = encrypt_mnemonic_aes(mnemonic)
                        
                        # ذخیره آدرس
                        new_addr = Address(
                            WalletID=wallet_id,
                            BlockchainID=bc.BlockchainID,
                            PublicAddress=address_obj.public_address,
                            PrivateKey=encrypted_priv,
                            PhraseKey=encrypted_mnemonic,
                            CreatedAt=datetime.utcnow()
                        )
                        self.session.add(new_addr)
                        addresses[bc_name] = address_obj.public_address
                        
                        # Format address info for webhook
                        blockchain_symbol = bc.Symbol if hasattr(bc, 'Symbol') else bc.BlockchainName
                        webhook_formatted_addresses.append({
                            'blockchain_symbol': blockchain_symbol,
                            'public_address': address_obj.public_address
                        })
                        
                        logger.info(f"Address created for {bc_name}: {address_obj.public_address}")
                
                if not addresses:
                    raise ValueError("Failed to create any addresses in the database")
                
                # Commit changes to database to make sure all addresses are stored
                self.session.flush()
                
                # Register addresses with webhook
                if webhook_formatted_addresses:
                    self._register_addresses_with_webhook(webhook_formatted_addresses)
                
                logger.info(f"Successfully imported wallet with ID {wallet_id} for new user {user_id}")
                return wallet_id, user_id, addresses, mnemonic

        except Exception as e:
            logger.error(f"Error in import_wallet: {str(e)}")
            # Rollback session to prevent partial imports
            self.session.rollback()
            
            # Re-raise the exception to be handled by the caller
            if isinstance(e, ValueError):
                raise
            else:
                raise ValueError(f"Failed to import wallet: {str(e)}")

    def validate_mnemonic(self, mnemonic: str) -> bool:
        """
        اعتبارسنجی عبارت بازیابی
        returns: True اگر عبارت معتبر باشد، False در غیر این صورت
        """
        try:
            # بررسی تعداد کلمات
            words = mnemonic.split()
            if len(words) not in [12, 18, 24]:
                logger.warning(f"Invalid mnemonic word count: {len(words)}")
                return False
                
            # استفاده از کتابخانه bip_utils برای اعتبارسنجی
            validator = Bip39MnemonicValidator()
            is_valid = validator.IsValid(mnemonic)
            
            if not is_valid:
                logger.warning("Mnemonic failed BIP39 validation")
                return False
                
            # تست تولید آدرس‌ها برای اطمینان از صحت
            try:
                address_generator = BlockchainAddressGenerator.from_mnemonic(mnemonic)
                addresses = address_generator.generate_all_addresses()
                
                # حداقل باید یک آدرس معتبر تولید شود
                if not addresses:
                    logger.warning("Mnemonic did not generate any valid addresses")
                    return False
                    
                # بررسی آدرس اتریوم به عنوان تست اصلی
                if "Ethereum" not in addresses:
                    logger.warning("Mnemonic did not generate a valid Ethereum address")
                    return False
                    
                eth_address = addresses["Ethereum"].public_address
                if not eth_address or not eth_address.startswith("0x"):
                    logger.warning(f"Invalid Ethereum address format: {eth_address}")
                    return False
                    
                logger.info(f"Mnemonic validated successfully, generated {len(addresses)} addresses")
                return True
                
            except Exception as e:
                logger.error(f"Error testing address generation: {str(e)}")
                return False
                
        except Exception as e:
            logger.error(f"Error validating mnemonic: {str(e)}")
            return False

    def _generate_addresses(self, wallet_id: str, user_id: str, mnemonic: str) -> Dict[str, str]:
        """
        Generate addresses for supported blockchains and save them to the database.
        """
        try:
            logger.info(f"Generating addresses for wallet {wallet_id}")
            
            # استفاده از BlockchainAddressGenerator برای تولید آدرس‌ها
            address_generator = BlockchainAddressGenerator.from_mnemonic(mnemonic)
            blockchain_addresses = address_generator.generate_all_addresses()
            
            if not blockchain_addresses:
                raise ValueError("Failed to generate any addresses from this mnemonic")
            
            # دریافت لیست بلاک‌چین‌های فعال در سیستم
            blockchains = self.session.query(Blockchains).all()
            blockchain_map = {bc.BlockchainName: bc for bc in blockchains}
            
            # Store addresses by blockchain name for return value
            addresses_by_chain = {}
            
            # Process each blockchain synchronously
            for bc_name, address_obj in blockchain_addresses.items():
                if bc_name in blockchain_map:
                    bc = blockchain_map[bc_name]
                    
                    # رمزنگاری کلیدها
                    encrypted_priv = encrypt_private_key_aes(address_obj.private_key)
                    encrypted_mnemonic = encrypt_mnemonic_aes(mnemonic)
                    
                    # ذخیره آدرس
                    new_addr = Address(
                        WalletID=wallet_id,
                        BlockchainID=bc.BlockchainID,
                        PublicAddress=address_obj.public_address,
                        PrivateKey=encrypted_priv,
                        PhraseKey=encrypted_mnemonic,
                        CreatedAt=datetime.utcnow()
                    )
                    self.session.add(new_addr)
                    addresses_by_chain[bc_name] = address_obj.public_address
                    
                    logger.info(f"Address created for {bc_name}: {address_obj.public_address}")
            
            if not addresses_by_chain:
                raise ValueError("Failed to create any addresses in the database")
            
            # Commit changes to database
            self.session.flush()
            
            # Register addresses with webhook system synchronously
            webhook_formatted_addresses = [
                {
                    'blockchain_symbol': bc.Symbol if hasattr(bc, 'Symbol') else bc.BlockchainName,
                    'public_address': addresses_by_chain[bc_name]
                }
                for bc_name, bc in blockchain_map.items()
                if bc_name in addresses_by_chain
            ]
            
            if webhook_formatted_addresses:
                self._register_addresses_with_webhook(webhook_formatted_addresses)
            
            logger.info(f"Successfully generated {len(addresses_by_chain)} addresses for wallet {wallet_id}")
            return addresses_by_chain
            
        except Exception as e:
            logger.error(f"Error generating addresses: {str(e)}")
            raise

    def _register_addresses_with_webhook(self, formatted_addresses):
        """
        Register the newly created addresses with the webhook system
        
        Args:
            formatted_addresses (list): List of dictionaries with address information
        """
        try:
            if not formatted_addresses:
                logger.warning("No addresses to register with webhook system")
                return
                
            # Import تنبل برای جلوگیری از circular import
            from webhook.tatum_subscription import register_new_addresses_for_webhook
            webhook_results = register_new_addresses_for_webhook(formatted_addresses)
            logger.info(f"Successfully registered {len(formatted_addresses)} addresses with webhook: {webhook_results}")
        except Exception as e:
            # نمی‌گذاریم این خطا باعث شکست عملیات اصلی شود
            logger.error(f"Failed to register addresses with webhook system: {str(e)}")
            # نباید خطایی پرتاب کنیم تا کل فرآیند متوقف نشود

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
            logger.error(f"Error retrieving phrase key: {str(e)}")
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
            logger.error(f"Error signing transaction: {str(e)}")
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
            logger.error(f"Error interacting with contract: {str(e)}")
            raise 