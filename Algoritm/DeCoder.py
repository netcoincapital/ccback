import os
import base64
import json
import logging
from datetime import datetime
from Crypto.Cipher import AES
from bip_utils import (
    Bip39SeedGenerator, Bip44, Bip84, Bip44Coins, Bip84Coins, Bip44Changes
)

# کلید AES (باید ثابت و 16/24/32 بایت باشد)
AES_SECRET_KEY = "MySecretKey@1234"

# تنظیمات لاگ
LOG_DIR = "Log"
os.makedirs(LOG_DIR, exist_ok=True)
log_file = os.path.join(LOG_DIR, f"decrypt_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.log")

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler()
    ]
)

def decrypt_private_key_aes(encrypted_key: str) -> str:
    """ دی‌کریپت کلید خصوصی رمزگذاری‌شده با AES-GCM """
    try:
        secret_key_bytes = AES_SECRET_KEY.encode()
        encrypted_data = base64.b64decode(encrypted_key)

        nonce = encrypted_data[:16]
        tag = encrypted_data[16:32]
        ciphertext = encrypted_data[32:]

        cipher = AES.new(secret_key_bytes, AES.MODE_GCM, nonce=nonce)
        decrypted_key = cipher.decrypt_and_verify(ciphertext, tag)

        return decrypted_key.decode()
    except Exception as e:
        logging.error(f"Decryption failed: {e}")
        return None

def generate_wallets_from_mnemonic(mnemonic):
    """ دریافت Mnemonic و تولید کلیدهای خصوصی و آدرس‌های 10 بلاکچین مختلف """
    seed_bytes = Bip39SeedGenerator(mnemonic).Generate()
    wallet_info = {"Mnemonic": mnemonic, "Wallets": {}}

    # لیست شبکه‌های مورد نظر
    networks = {
        "BTC": (Bip84.FromSeed(seed_bytes, Bip84Coins.BITCOIN), "wif"),
        "ETH": (Bip44.FromSeed(seed_bytes, Bip44Coins.ETHEREUM), "hex"),
        "TRX": (Bip44.FromSeed(seed_bytes, Bip44Coins.TRON), "hex"),
        "BSC": (Bip44.FromSeed(seed_bytes, Bip44Coins.BINANCE_SMART_CHAIN), "hex"),
        "MATIC": (Bip44.FromSeed(seed_bytes, Bip44Coins.POLYGON), "hex"),
        "SOL": (Bip44.FromSeed(seed_bytes, Bip44Coins.SOLANA), "hex"),
        "XRP": (Bip44.FromSeed(seed_bytes, Bip44Coins.RIPPLE), "hex"),
        "ARB": (Bip44.FromSeed(seed_bytes, Bip44Coins.ARBITRUM), "hex"),
        "AVAX": (Bip44.FromSeed(seed_bytes, Bip44Coins.AVAX_C_CHAIN), "hex"),
        "DOT": (Bip44.FromSeed(seed_bytes, Bip44Coins.POLKADOT_ED25519_SLIP), "hex"),
    }

    for blockchain, (bip_obj, key_format) in networks.items():
        acc = bip_obj.Purpose().Coin().Account(0).Change(Bip44Changes.CHAIN_EXT).AddressIndex(0)
        if key_format == "wif":
            private_key = acc.PrivateKey().ToWif()
        else:
            private_key = acc.PrivateKey().Raw().ToHex()
        public_address = acc.PublicKey().ToAddress()

        wallet_info["Wallets"][blockchain] = {
            "PrivateKey": private_key,
            "Address": public_address
        }

    return wallet_info

def find_private_key_by_address(mnemonic, public_address):
    """ بررسی اینکه Public Address داده شده مربوط به کدام بلاکچین است و پرایوت کی را استخراج می‌کند """
    wallet_data = generate_wallets_from_mnemonic(mnemonic)

    for blockchain, data in wallet_data["Wallets"].items():
        if data["Address"] == public_address:
            return {
                "Blockchain": blockchain,
                "PublicAddress": public_address,
                "PrivateKey": data["PrivateKey"]
            }

    return None  # اگر آدرس پیدا نشد

if __name__ == "__main__":
    user_input = input("Enter your Mnemonic or Public Address: ").strip()

    # اگر کاربر Mnemonic وارد کند، تمام کیف‌ها را بازیابی می‌کند
    if " " in user_input:
        wallet_data = generate_wallets_from_mnemonic(user_input)
        logging.info("Wallet recovery successful")
        print(json.dumps(wallet_data, indent=4))
    
    # اگر کاربر فقط Public Address وارد کند، Private Key مربوط به آن را نمایش می‌دهد
    else:
        mnemonic = input("Enter your Mnemonic (for verification): ").strip()
        private_key_info = find_private_key_by_address(mnemonic, user_input)

        if private_key_info:
            logging.info("Private key found")
            print(json.dumps(private_key_info, indent=4))
        else:
            logging.error("Public Address not found in this mnemonic's wallets")
            print("Error: Public Address not found.")