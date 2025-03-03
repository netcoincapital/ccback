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
        """Generate addresses for all supported blockchains"""
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

        # Binance Smart Chain (Same derivation path as Ethereum)
        try:
            bip44_bnb = Bip44.FromSeed(self.seed_bytes, Bip44Coins.BINANCE_SMART_CHAIN)
            bnb_acc = bip44_bnb.Purpose().Coin().Account(0).Change(Bip44Changes.CHAIN_EXT).AddressIndex(0)
            addresses["Binance Smart Chain"] = BlockchainAddress(
                public_address=bnb_acc.PublicKey().ToAddress(),
                private_key=bnb_acc.PrivateKey().Raw().ToHex()
            )
            logging.info(f"Successfully generated Binance Smart Chain address: {bnb_acc.PublicKey().ToAddress()}")
        except Exception as e:
            logging.error(f"Error generating Binance Smart Chain address: {str(e)}", exc_info=True)
            # Try alternative approach for Binance
            try:
                # Binance uses the same address format as Ethereum
                if "Ethereum" in addresses:
                    eth_address = addresses["Ethereum"].public_address
                    eth_private_key = addresses["Ethereum"].private_key
                    addresses["Binance Smart Chain"] = BlockchainAddress(
                        public_address=eth_address,
                        private_key=eth_private_key
                    )
                    logging.info(f"Used Ethereum address as fallback for Binance Smart Chain: {eth_address}")
            except Exception as fallback_error:
                logging.error(f"Fallback for Binance Smart Chain address also failed: {str(fallback_error)}")

        # Polygon (Same derivation path as Ethereum)
        try:
            bip44_polygon = Bip44.FromSeed(self.seed_bytes, Bip44Coins.POLYGON)
            polygon_acc = bip44_polygon.Purpose().Coin().Account(0).Change(Bip44Changes.CHAIN_EXT).AddressIndex(0)
            addresses["Polygon"] = BlockchainAddress(
                public_address=polygon_acc.PublicKey().ToAddress(),
                private_key=polygon_acc.PrivateKey().Raw().ToHex()
            )
        except Exception as e:
            logging.error(f"Error generating Polygon address: {e}")

        # Avalanche (Same derivation path as Ethereum)
        try:
            bip44_avax = Bip44.FromSeed(self.seed_bytes, Bip44Coins.AVAX_C_CHAIN)
            avax_acc = bip44_avax.Purpose().Coin().Account(0).Change(Bip44Changes.CHAIN_EXT).AddressIndex(0)
            addresses["Avalanche"] = BlockchainAddress(
                public_address=avax_acc.PublicKey().ToAddress(),
                private_key=avax_acc.PrivateKey().Raw().ToHex()
            )
        except Exception as e:
            logging.error(f"Error generating Avalanche address: {e}")

        # Arbitrum (Same derivation path as Ethereum)
        try:
            bip44_arb = Bip44.FromSeed(self.seed_bytes, Bip44Coins.ARBITRUM)
            arb_acc = bip44_arb.Purpose().Coin().Account(0).Change(Bip44Changes.CHAIN_EXT).AddressIndex(0)
            addresses["Arbitrum"] = BlockchainAddress(
                public_address=arb_acc.PublicKey().ToAddress(),
                private_key=arb_acc.PrivateKey().Raw().ToHex()
            )
        except Exception as e:
            logging.error(f"Error generating Arbitrum address: {e}")

        # Polkadot
        try:
            # Using substrate address format for Polkadot
            bip44_dot = Bip44.FromSeed(self.seed_bytes, Bip44Coins.POLKADOT_ED25519_SLIP)
            dot_acc = bip44_dot.Purpose().Coin().Account(0).Change(Bip44Changes.CHAIN_EXT).AddressIndex(0)
            addresses["Polkadot"] = BlockchainAddress(
                public_address=dot_acc.PublicKey().ToAddress(),
                private_key=dot_acc.PrivateKey().Raw().ToHex()
            )
        except Exception as e:
            logging.error(f"Error generating Polkadot address: {e}")

        # XRP (Ripple)
        try:
            bip44_xrp = Bip44.FromSeed(self.seed_bytes, Bip44Coins.RIPPLE)
            xrp_acc = bip44_xrp.Purpose().Coin().Account(0).Change(Bip44Changes.CHAIN_EXT).AddressIndex(0)
            addresses["XRP"] = BlockchainAddress(
                public_address=xrp_acc.PublicKey().ToAddress(),
                private_key=xrp_acc.PrivateKey().Raw().ToHex()
            )
        except Exception as e:
            logging.error(f"Error generating XRP address: {e}")

        # Solana
        try:
            # Using ed25519 curve for Solana
            bip44_sol = Bip44.FromSeed(self.seed_bytes, Bip44Coins.SOLANA)
            sol_acc = bip44_sol.Purpose().Coin().Account(0).Change(Bip44Changes.CHAIN_EXT).AddressIndex(0)
            addresses["Solana"] = BlockchainAddress(
                public_address=sol_acc.PublicKey().ToAddress(),
                private_key=sol_acc.PrivateKey().Raw().ToHex()
            )
        except Exception as e:
            logging.error(f"Error generating Solana address: {e}")

        return addresses

    @staticmethod
    def from_mnemonic(mnemonic: str) -> 'BlockchainAddressGenerator':
        """Create a new instance from a mnemonic phrase"""
        seed_bytes = Bip39SeedGenerator(mnemonic).Generate()
        return BlockchainAddressGenerator(seed_bytes) 