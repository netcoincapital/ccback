from typing import Tuple, Dict
from datetime import datetime
import uuid
import logging
from sqlalchemy.orm import Session
from bip_utils import Bip39MnemonicGenerator, Bip39WordsNum

from database.users import Users
from database.wallets import Wallets
from database.Address import Address
from database.Blockchains import Blockchains
from utils.blockchain_address_generator import BlockchainAddressGenerator
from security.encryption import encrypt_private_key_aes, encrypt_mnemonic_aes

class WalletService:
    def __init__(self, session: Session):
        self.session = session

    def create_wallet(self, wallet_name: str) -> Tuple[str, str, Dict]:
        """
        ایجاد کیف پول جدید
        returns: (user_id, mnemonic, addresses)
        """
        try:
            # ایجاد کاربر جدید
            user_id = str(uuid.uuid4())
            new_user = Users(
                UserID=user_id,
                CreatedAt=datetime.utcnow(),
                UpdatedAt=datetime.utcnow(),
                Device="Unknown",
                IP="Unknown"
            )
            self.session.add(new_user)
            logging.info(f"New user created: {new_user}")

            # ایجاد کیف پول
            wallet_id = str(uuid.uuid4())
            new_wallet = Wallets(
                WalletID=wallet_id,
                UserID=user_id,
                IsMultiSig=False,
                RequiredSignatures="1",
                CreatedAt=datetime.utcnow()
            )
            self.session.add(new_wallet)
            logging.info(f"New wallet created: {new_wallet}")

            # تولید عبارت بازیابی
            mnemonic = Bip39MnemonicGenerator().FromWordsNumber(Bip39WordsNum.WORDS_NUM_12)
            
            # تولید آدرس‌ها
            addresses = self._generate_addresses(wallet_id, str(mnemonic))

            return user_id, str(mnemonic), addresses

        except Exception as e:
            logging.error(f"Error in create_wallet: {str(e)}")
            raise

    def import_wallet(self, mnemonic: str) -> Tuple[str, Dict]:
        """
        وارد کردن کیف پول با استفاده از عبارت بازیابی
        returns: (wallet_id, addresses)
        """
        try:
            # ایجاد کیف پول
            wallet_id = str(uuid.uuid4())
            addresses = self._generate_addresses(wallet_id, mnemonic)
            
            return wallet_id, addresses

        except Exception as e:
            logging.error(f"Error in import_wallet: {str(e)}")
            raise

    def _generate_addresses(self, wallet_id: str, mnemonic: str) -> Dict:
        """تولید آدرس‌ها برای تمام بلاکچین‌های پشتیبانی شده"""
        try:
            address_generator = BlockchainAddressGenerator.from_mnemonic(mnemonic)
            blockchain_addresses = address_generator.generate_all_addresses()
            
            addresses = {}
            blockchains = self.session.query(Blockchains).all()

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

            return addresses

        except Exception as e:
            logging.error(f"Error in _generate_addresses: {str(e)}")
            raise 