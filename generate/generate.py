import os
import base64
import json
from flask import Blueprint, jsonify, request
from datetime import datetime
import logging

from database import SessionLocal
from database.users import Users
from database.wallets import Wallets
from database.Address import Address
from database.Blockchains import Blockchains

from services import generate_uuid, CheckBlockchain

# کتابخانه bip_utils برای Mnemonic، Seed و استخراج کلید خصوصی
try:
    from bip_utils import (
        Bip39MnemonicGenerator, Bip39SeedGenerator,
        Bip44, Bip84, Bip44Coins, Bip84Coins,
        Bip39WordsNum, Bip44Changes
    )
except ImportError:
    logging.warning("bip_utils is not installed. Please install it via 'pip install bip_utils>=2.6.0'.")

# برای AES
from Crypto.Cipher import AES

LOG_DIR = "Log"
os.makedirs(LOG_DIR, exist_ok=True)
log_file = os.path.join(LOG_DIR, f"{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.log")

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler()
    ]
)

generate_bp = Blueprint('generate_wallet', __name__)

# کلید AES باید 16 یا 24 یا 32 بایت باشد:
AES_SECRET_KEY = "MySecretKey@1234"  # مثال: 16 کاراکتر (بایت)

def encrypt_private_key_aes(private_key: str) -> str:
    """
    رمزنگاری کلید خصوصی با استفاده از AES (حالت GCM) و کلید ثابت.
    خروجی: متن رمزنگاری‌شده (base64)
    """
    secret_key_bytes = AES_SECRET_KEY.encode()
    # ساخت cipher در حالت GCM
    cipher = AES.new(secret_key_bytes, AES.MODE_GCM)
    ciphertext, tag = cipher.encrypt_and_digest(private_key.encode())

    # ترکیب nonce + tag + ciphertext
    total_data = cipher.nonce + tag + ciphertext
    return base64.b64encode(total_data).decode()


@generate_bp.route('/generate-wallet', methods=['POST'])
def generate_wallet():
    """
    ایجاد کاربر + کیف پول + آدرس‌های مختلف بلاکچین،
    فقط Mnemonic در PhraseKey، استفاده از AES برای PrivateKey
    و تراکنش اتمیک (with session.begin()).
    """
    session = SessionLocal()
    try:
        data = request.get_json()
        wallet_name = data.get('WalletName')

        if not wallet_name:
            return jsonify({'error': 'WalletName is required'}), 400

        with session.begin():  # آغاز تراکنش اتمیک
            # ساخت یوزر (بدون Password)
            user_id = generate_uuid()
            new_user = Users(
                UserID=user_id,
                CreatedAt=datetime.utcnow(),
                UpdatedAt=datetime.utcnow(),
                Device="Unknown",
                IP="Unknown"
            )
            session.add(new_user)
            logging.info(f"New user created: {new_user}")

            # ساخت یک Wallet رکورد (بدون WalletName)
            wallet_id = generate_uuid()
            new_wallet = Wallets(
                WalletID=wallet_id,
                UserID=user_id,
                IsMultiSig=False,
                RequiredSignatures="1",
                CreatedAt=datetime.utcnow()
            )
            session.add(new_wallet)
            logging.info(f"Wallet created (wallet name not stored): {new_wallet}")

            # تولید یک عبارت Mnemonic
            mnemonic = Bip39MnemonicGenerator().FromWordsNumber(Bip39WordsNum.WORDS_NUM_12)
            logging.info(f"Generated Mnemonic: {mnemonic}")

            # تبدیل Mnemonic به Seed
            seed_bytes = Bip39SeedGenerator(mnemonic).Generate()

            # Bitcoin (BIP84)
            bip84_btc = Bip84.FromSeed(seed_bytes, Bip84Coins.BITCOIN)
            btc_acc = bip84_btc.Purpose().Coin().Account(0).Change(Bip44Changes.CHAIN_EXT).AddressIndex(0)
            btc_priv_key_wif = btc_acc.PrivateKey().ToWif()
            btc_pub_address = btc_acc.PublicKey().ToAddress()

            # Ethereum (BIP44)
            bip44_eth = Bip44.FromSeed(seed_bytes, Bip44Coins.ETHEREUM)
            eth_acc = bip44_eth.Purpose().Coin().Account(0).Change(Bip44Changes.CHAIN_EXT).AddressIndex(0)
            eth_priv_key = eth_acc.PrivateKey().Raw().ToHex()
            eth_pub_address = eth_acc.PublicKey().ToAddress()

            # Tron
            bip44_tron = Bip44.FromSeed(seed_bytes, Bip44Coins.TRON)
            tron_acc = bip44_tron.Purpose().Coin().Account(0).Change(Bip44Changes.CHAIN_EXT).AddressIndex(0)
            tron_priv_key = tron_acc.PrivateKey().Raw().ToHex()
            tron_pub_address = tron_acc.PublicKey().ToAddress()

            # Binance Smart Chain
            bip44_bnb = Bip44.FromSeed(seed_bytes, Bip44Coins.BINANCE_SMART_CHAIN)
            bnb_acc = bip44_bnb.Purpose().Coin().Account(0).Change(Bip44Changes.CHAIN_EXT).AddressIndex(0)
            bnb_priv_key = bnb_acc.PrivateKey().Raw().ToHex()
            bnb_pub_address = bnb_acc.PublicKey().ToAddress()

            # Polygon
            bip44_polygon = Bip44.FromSeed(seed_bytes, Bip44Coins.POLYGON)
            polygon_acc = bip44_polygon.Purpose().Coin().Account(0).Change(Bip44Changes.CHAIN_EXT).AddressIndex(0)
            polygon_priv_key = polygon_acc.PrivateKey().Raw().ToHex()
            polygon_pub_address = polygon_acc.PublicKey().ToAddress()

            # XRP
            bip44_xrp = Bip44.FromSeed(seed_bytes, Bip44Coins.RIPPLE)
            xrp_acc = bip44_xrp.Purpose().Coin().Account(0).Change(Bip44Changes.CHAIN_EXT).AddressIndex(0)
            xrp_priv_key = xrp_acc.PrivateKey().Raw().ToHex()
            xrp_pub_address = xrp_acc.PublicKey().ToAddress()

            # Arbitrum
            bip44_arbitrum = Bip44.FromSeed(seed_bytes, Bip44Coins.ARBITRUM)
            arbitrum_acc = bip44_arbitrum.Purpose().Coin().Account(0).Change(Bip44Changes.CHAIN_EXT).AddressIndex(0)
            arbitrum_priv_key = arbitrum_acc.PrivateKey().Raw().ToHex()
            arbitrum_pub_address = arbitrum_acc.PublicKey().ToAddress()

            bip44_solana = Bip44.FromSeed(seed_bytes, Bip44Coins.SOLANA)
            solana_acc = bip44_solana.Purpose().Coin().Account(0).Change(Bip44Changes.CHAIN_EXT).AddressIndex(0)
            solana_priv_key = solana_acc.PrivateKey().Raw().ToHex()
            solana_pub_address = solana_acc.PublicKey().ToAddress()

            bip44_avax = Bip44.FromSeed(seed_bytes, Bip44Coins.AVAX_C_CHAIN)
            avax_acc = bip44_avax.Purpose().Coin().Account(0).Change(Bip44Changes.CHAIN_EXT).AddressIndex(0)
            avax_priv_key = avax_acc.PrivateKey().Raw().ToHex()
            avax_pub_address = avax_acc.PublicKey().ToAddress()

            bip44_dot = Bip44.FromSeed(seed_bytes, Bip44Coins.POLKADOT_ED25519_SLIP)
            dot_acc = bip44_dot.Purpose().Coin().Account(0).Change(Bip44Changes.CHAIN_EXT).AddressIndex(0)
            dot_priv_key = dot_acc.PrivateKey().Raw().ToHex()
            dot_pub_address = dot_acc.PublicKey().ToAddress()

            # گرفتن بلاکچین ها از دیتابیس
            blockchains = session.query(Blockchains).all()

            for bc in blockchains:
                bc_lower = bc.BlockchainName.lower()

                if "bitcoin" in bc_lower:
                    raw_priv = btc_priv_key_wif
                    raw_pub = btc_pub_address
                elif "ethereum" in bc_lower:
                    raw_priv = eth_priv_key
                    raw_pub = eth_pub_address
                elif "tron" in bc_lower:
                    raw_priv = tron_priv_key
                    raw_pub = tron_pub_address
                elif "binance smart chain" in bc_lower:
                    raw_priv = bnb_priv_key
                    raw_pub = bnb_pub_address
                elif "polygon" in bc_lower:
                    raw_priv = polygon_priv_key
                    raw_pub = polygon_pub_address
                elif "arbitrum" in bc_lower:
                    raw_priv = arbitrum_priv_key
                    raw_pub = arbitrum_pub_address
                elif "xrp" in bc_lower:
                    raw_priv = xrp_priv_key
                    raw_pub = xrp_pub_address      
                elif "solana" in bc_lower:
                    raw_priv = solana_priv_key
                    raw_pub = solana_pub_address
                elif "avalanche" in bc_lower:
                    raw_priv = avax_priv_key
                    raw_pub = avax_pub_address
                elif "polkadot" in bc_lower:
                    raw_priv = dot_priv_key
                    raw_pub = dot_pub_address    

                else:
                    logging.warning(f"Skipping blockchain: {bc.BlockchainName} (not recognized).")
                    raise ValueError("Unsupported blockchain in DB")

                # رمزنگاری با AES
                encrypted_priv = encrypt_private_key_aes(raw_priv)

                # ایجاد رکورد Address
                new_addr = Address(
                    WalletID=wallet_id,
                    BlockchainID=bc.BlockchainID,
                    PublicAddress=raw_pub,
                    PrivateKey=encrypted_priv,
                    PhraseKey=str(mnemonic),  # فقط Mnemonic
                    CreatedAt=datetime.utcnow()
                )
                session.add(new_addr)
                logging.info(f"Address created for {bc.BlockchainName}: {new_addr}")

        # پایان بلاک with => commit اتمیک
        return jsonify({
            'UserID': user_id,
            'Mnemonic': str(mnemonic),
            'success': True
        }), 201

    except Exception as e:
        logging.error(f"Error in generate_wallet: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500

    finally:
        session.close()
        logging.debug("Database session closed.")
