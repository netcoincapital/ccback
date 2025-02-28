from bip_utils import (
    Bip39SeedGenerator, Bip44, Bip84,
    Bip44Coins, Bip84Coins, Bip44Changes
)
import logging
from typing import Dict, Tuple
from dataclasses import dataclass

@dataclass
class BlockchainAddress:
    public_address: str
    private_key: str

class BlockchainAddressGenerator:
    def __init__(self, seed_bytes: bytes):
        self.seed_bytes = seed_bytes

    def generate_all_addresses(self) -> Dict[str, BlockchainAddress]:
        """تولید آدرس برای تمام بلاکچین‌های پشتیبانی شده"""
        addresses = {}
        
        # Bitcoin (BIP84)
        try:
            bip84_btc = Bip84.FromSeed(self.seed_bytes, Bip84Coins.BITCOIN)
            btc_acc = bip84_btc.Purpose().Coin().Account(0).Change(Bip44Changes.CHAIN_EXT).AddressIndex(0)
            addresses["Bitcoin"] = BlockchainAddress(
                public_address=btc_acc.PublicKey().ToAddress(),
                private_key=btc_acc.PrivateKey().ToWif()
            )
        except Exception as e:
            logging.error(f"Error generating Bitcoin address: {e}")

        # Ethereum (BIP44)
        try:
            bip44_eth = Bip44.FromSeed(self.seed_bytes, Bip44Coins.ETHEREUM)
            eth_acc = bip44_eth.Purpose().Coin().Account(0).Change(Bip44Changes.CHAIN_EXT).AddressIndex(0)
            addresses["Ethereum"] = BlockchainAddress(
                public_address=eth_acc.PublicKey().ToAddress(),
                private_key=eth_acc.PrivateKey().Raw().ToHex()
            )
        except Exception as e:
            logging.error(f"Error generating Ethereum address: {e}")

        # Tron
        try:
            bip44_tron = Bip44.FromSeed(self.seed_bytes, Bip44Coins.TRON)
            tron_acc = bip44_tron.Purpose().Coin().Account(0).Change(Bip44Changes.CHAIN_EXT).AddressIndex(0)
            addresses["Tron"] = BlockchainAddress(
                public_address=tron_acc.PublicKey().ToAddress(),
                private_key=tron_acc.PrivateKey().Raw().ToHex()
            )
        except Exception as e:
            logging.error(f"Error generating Tron address: {e}")

        # ... سایر بلاکچین‌ها به همین ترتیب

        return addresses

    @staticmethod
    def from_mnemonic(mnemonic: str) -> 'BlockchainAddressGenerator':
        """ایجاد نمونه جدید از روی Mnemonic"""
        seed_bytes = Bip39SeedGenerator(mnemonic).Generate()
        return BlockchainAddressGenerator(seed_bytes) 