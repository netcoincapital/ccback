import os
import base64
import logging
from datetime import datetime

from flask import Blueprint, request, jsonify

# کتابخانه bip_utils برای Mnemonic، Seed و استخراج آدرس‌ها
try:
    from bip_utils import (
        Bip39SeedGenerator,
        Bip44, Bip84,
        Bip44Coins, Bip84Coins, Bip44Changes
    )
except ImportError:
    logging.warning("bip_utils is not installed. Please install it via 'pip install bip_utils>=2.6.0'.")

# برای AES
from Crypto.Cipher import AES

# ایمپورت مدل‌ها و Session از پکیج دیتابیس
from database import SessionLocal
from database.users import Users
from database.wallets import Wallets
from database.Address import Address
from database.Blockchains import Blockchains
from database.Currencies import Currencies  # اگر نیازی به توکن‌ها ندارید می‌توانید حذف کنید

LOG_DIR = "Log"
os.makedirs(LOG_DIR, exist_ok=True)
log_file = os.path.join(LOG_DIR, f"import_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.log")

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler()
    ]
)

AES_SECRET_KEY = "MySecretKey@1234"  # باید طول 16/24/32 بایت داشته باشد

def encrypt_mnemonic_aes(mnemonic: str) -> str:
    """
    رمزنگاری Mnemonic با استفاده از AES (حالت GCM) و یک Salt تصادفی.
    در خروجی base64(salt + nonce + tag + ciphertext) را برمی‌گرداند.
    """
    salt = os.urandom(16)
    secret_key_bytes = AES_SECRET_KEY.encode('utf-8')
    cipher = AES.new(secret_key_bytes, AES.MODE_GCM)
    plaintext = salt + mnemonic.encode('utf-8')
    ciphertext, tag = cipher.encrypt_and_digest(plaintext)
    encrypted_data = salt + cipher.nonce + tag + ciphertext
    return base64.b64encode(encrypted_data).decode('utf-8')


def encrypt_private_key_aes(private_key: str) -> str:
    """
    رمزنگاری کلید خصوصی با استفاده از AES (حالت GCM) و یک Salt تصادفی.
    ساختار خروجی مشابه تابع encrypt_mnemonic_aes است:
    base64(salt + nonce + tag + ciphertext).
    """
    salt = os.urandom(16)
    secret_key_bytes = AES_SECRET_KEY.encode('utf-8')
    cipher = AES.new(secret_key_bytes, AES.MODE_GCM)
    plaintext = salt + private_key.encode('utf-8')
    ciphertext, tag = cipher.encrypt_and_digest(plaintext)
    encrypted_data = salt + cipher.nonce + tag + ciphertext
    return base64.b64encode(encrypted_data).decode('utf-8')


import_bp = Blueprint('import_bp', __name__)

@import_bp.route('/import_wallet', methods=['POST'])
def import_wallet():
    session = SessionLocal()
    try:
        data = request.json
        mnemonic = data.get('mnemonic', '').strip()

        # بررسی تعداد کلمات Mnemonic
        mnemonic_words = mnemonic.split()
        if len(mnemonic_words) not in [12, 18, 24]:
            return jsonify({
                "status": "error",
                "message": "تعداد کلمات عبارت بازیابی باید 12، 18 یا 24 باشد."
            }), 400

        # تلاش برای تبدیل Mnemonic به Seed
        try:
            seed_bytes = Bip39SeedGenerator(mnemonic).Generate()
        except Exception as e:
            return jsonify({
                "status": "error",
                "message": f"عبارت بازیابی نامعتبر است: {str(e)}"
            }), 400

        # ایجاد یک کاربر جدید در دیتابیس
        new_user = Users(
            CreatedAt=datetime.utcnow(),
            UpdatedAt=datetime.utcnow(),
            Device="Unknown",
            IP="0.0.0.0"
        )
        session.add(new_user)
        session.flush()

        # ایجاد یک رکورد جدید در Wallets
        new_wallet = Wallets(
            UserID=new_user.UserID,
            IsMultiSig=False,
            RequiredSignatures="1",
            CreatedAt=datetime.utcnow(),
            UpdatedAt=datetime.utcnow()
        )
        session.add(new_wallet)
        session.flush()

        # --------- تولید کلید و آدرس برای بلاک‌چین‌های مختلف ----------

        # 1) بیت‌کوین (BIP84)
        bip84_btc = Bip84.FromSeed(seed_bytes, Bip84Coins.BITCOIN)
        btc_acc = bip84_btc.Purpose().Coin().Account(0).Change(Bip44Changes.CHAIN_EXT).AddressIndex(0)
        btc_address = btc_acc.PublicKey().ToAddress()
        # کلید خصوصی در فرمت WIF
        btc_priv_key = btc_acc.PrivateKey().ToWif()

        # 2) اتریوم (BIP44)
        bip44_eth = Bip44.FromSeed(seed_bytes, Bip44Coins.ETHEREUM)
        eth_acc = bip44_eth.Purpose().Coin().Account(0).Change(Bip44Changes.CHAIN_EXT).AddressIndex(0)
        eth_address = eth_acc.PublicKey().ToAddress()
        eth_priv_key = eth_acc.PrivateKey().Raw().ToHex()

        # 3) ترون (BIP44)
        bip44_tron = Bip44.FromSeed(seed_bytes, Bip44Coins.TRON)
        tron_acc = bip44_tron.Purpose().Coin().Account(0).Change(Bip44Changes.CHAIN_EXT).AddressIndex(0)
        tron_address = tron_acc.PublicKey().ToAddress()
        tron_priv_key = tron_acc.PrivateKey().Raw().ToHex()

        # 4) بایننس اسمارت‌چین
        bip44_bnb = Bip44.FromSeed(seed_bytes, Bip44Coins.BINANCE_SMART_CHAIN)
        bnb_acc = bip44_bnb.Purpose().Coin().Account(0).Change(Bip44Changes.CHAIN_EXT).AddressIndex(0)
        bnb_address = bnb_acc.PublicKey().ToAddress()
        bnb_priv_key = bnb_acc.PrivateKey().Raw().ToHex()

        # 5) پالیگان
        bip44_polygon = Bip44.FromSeed(seed_bytes, Bip44Coins.POLYGON)
        polygon_acc = bip44_polygon.Purpose().Coin().Account(0).Change(Bip44Changes.CHAIN_EXT).AddressIndex(0)
        polygon_address = polygon_acc.PublicKey().ToAddress()
        polygon_priv_key = polygon_acc.PrivateKey().Raw().ToHex()

        # 6) آربیتروم
        bip44_arb = Bip44.FromSeed(seed_bytes, Bip44Coins.ARBITRUM)
        arb_acc = bip44_arb.Purpose().Coin().Account(0).Change(Bip44Changes.CHAIN_EXT).AddressIndex(0)
        arb_address = arb_acc.PublicKey().ToAddress()
        arb_priv_key = arb_acc.PrivateKey().Raw().ToHex()

        # 7) ریپل (XRP)
        bip44_xrp = Bip44.FromSeed(seed_bytes, Bip44Coins.RIPPLE)
        xrp_acc = bip44_xrp.Purpose().Coin().Account(0).Change(Bip44Changes.CHAIN_EXT).AddressIndex(0)
        xrp_address = xrp_acc.PublicKey().ToAddress()
        xrp_priv_key = xrp_acc.PrivateKey().Raw().ToHex()

        # 8) سولانا
        bip44_solana = Bip44.FromSeed(seed_bytes, Bip44Coins.SOLANA)
        sol_acc = bip44_solana.Purpose().Coin().Account(0).Change(Bip44Changes.CHAIN_EXT).AddressIndex(0)
        solana_address = sol_acc.PublicKey().ToAddress()
        solana_priv_key = sol_acc.PrivateKey().Raw().ToHex()

        # 9) آوالانچ (C-Chain)
        bip44_avax = Bip44.FromSeed(seed_bytes, Bip44Coins.AVAX_C_CHAIN)
        avax_acc = bip44_avax.Purpose().Coin().Account(0).Change(Bip44Changes.CHAIN_EXT).AddressIndex(0)
        avax_address = avax_acc.PublicKey().ToAddress()
        avax_priv_key = avax_acc.PrivateKey().Raw().ToHex()

        # 10) پولکادات (Ed25519 SLIP)
        bip44_dot = Bip44.FromSeed(seed_bytes, Bip44Coins.POLKADOT_ED25519_SLIP)
        dot_acc = bip44_dot.Purpose().Coin().Account(0).Change(Bip44Changes.CHAIN_EXT).AddressIndex(0)
        dot_address = dot_acc.PublicKey().ToAddress()
        dot_priv_key = dot_acc.PrivateKey().Raw().ToHex()

        # رمزنگاری Mnemonic
        encrypted_mnemonic = encrypt_mnemonic_aes(mnemonic)

        # یک دیکشنری شامل (PublicAddress, PrivateKey) برای هر بلاکچین
        chain_addresses = {
            "Bitcoin":   (btc_address,  btc_priv_key),
            "Ethereum":  (eth_address,  eth_priv_key),
            "BNB":       (bnb_address,  bnb_priv_key),
            "Tron":      (tron_address, tron_priv_key),
            "Polygon":   (polygon_address, polygon_priv_key),
            "Arbitrum":  (arb_address,  arb_priv_key),
            "XRP":       (xrp_address,  xrp_priv_key),
            "Solana":    (solana_address, solana_priv_key),
            "Avalanche": (avax_address, avax_priv_key),
            "Polkadot":  (dot_address,  dot_priv_key),
        }

        addresses_result = []

        # ثبت رکورد در دیتابیس برای هر بلاکچین
        for chain_name, (pub_address, raw_priv) in chain_addresses.items():
            # پیدا کردن بلاکچین در دیتابیس
            blockchain_row = session.query(Blockchains).filter_by(BlockchainName=chain_name).first()
            if not blockchain_row:
                # بلاکچین در دیتابیس تعریف نشده، رد می‌کنیم
                continue

            # رمزنگاری کلید خصوصی
            encrypted_priv = encrypt_private_key_aes(raw_priv)

            # ایجاد رکورد Address
            new_addr = Address(
                WalletID=new_wallet.WalletID,
                BlockchainID=blockchain_row.BlockchainID,
                PublicAddress=pub_address,
                PrivateKey=encrypted_priv,  # ذخیره کلید خصوصی رمزنگاری‌شده
                PhraseKey=encrypted_mnemonic,
                CreatedAt=datetime.utcnow()
            )
            session.add(new_addr)
            session.flush()

            addresses_result.append({
                "BlockchainName": chain_name,
                "PublicAddress": pub_address
            })

        session.commit()

        return jsonify({
            "status": "success",
            "data": {
                "UserID": new_user.UserID,
                "WalletID": new_wallet.WalletID,
                "Mnemonic": mnemonic,
                "Addresses": addresses_result
            },
            "message": "کیف پول با موفقیت ایمپورت شد."
        }), 200

    except Exception as e:
        session.rollback()
        logging.error(f"Error in import_wallet: {str(e)}", exc_info=True)
        return jsonify({
            "status": "error",
            "message": f"خطا در ایمپورت کیف‌پول: {str(e)}"
        }), 500

    finally:
        session.close()
        logging.debug("Database session closed.")