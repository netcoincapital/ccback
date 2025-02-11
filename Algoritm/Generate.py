import requests
from bip_utils import (
    Bip39MnemonicGenerator, Bip39SeedGenerator, Bip44, Bip84, Bip49,
    Bip44Coins, Bip49Coins, Bip84Coins, Bip39WordsNum, Bip44Changes
)

# ✅ 1. تولید عبارت بازیابی
mnemonic = Bip39MnemonicGenerator().FromWordsNumber(Bip39WordsNum.WORDS_NUM_12)
print("Mnemonic:", mnemonic, "\n")

# ✅ 2. تولید Seed
seed_bytes = Bip39SeedGenerator(mnemonic).Generate()

# ✅ 3. ساخت کیف پول‌ها و نمایش Private key
wallets = {}

# بیت‌کوین
bip84 = Bip84.FromSeed(seed_bytes, Bip84Coins.BITCOIN)
btc_acc = bip84.Purpose().Coin().Account(0).Change(Bip44Changes.CHAIN_EXT).AddressIndex(0)
wallets["Bitcoin"] = {
    "Address": btc_acc.PublicKey().ToAddress(),
    "Private Key": btc_acc.PrivateKey().ToWif()
}

# اتریوم
bip44_eth = Bip44.FromSeed(seed_bytes, Bip44Coins.ETHEREUM)
eth_acc = bip44_eth.Purpose().Coin().Account(0).Change(Bip44Changes.CHAIN_EXT).AddressIndex(0)
wallets["Ethereum"] = {
    "Address": eth_acc.PublicKey().ToAddress(),
    "Private Key": eth_acc.PrivateKey().Raw().ToHex()
}

# ترون
bip44_tron = Bip44.FromSeed(seed_bytes, Bip44Coins.TRON)
tron_acc = bip44_tron.Purpose().Coin().Account(0).Change(Bip44Changes.CHAIN_EXT).AddressIndex(0)
wallets["Tron"] = {
    "Address": tron_acc.PublicKey().ToAddress(),
    "Private Key": tron_acc.PrivateKey().Raw().ToHex()
}

# بایننس اسمارت چین (BSC)
bip44_bnb = Bip44.FromSeed(seed_bytes, Bip44Coins.BINANCE_SMART_CHAIN)
bnb_acc = bip44_bnb.Purpose().Coin().Account(0).Change(Bip44Changes.CHAIN_EXT).AddressIndex(0)
wallets["BSC"] = {
    "Address": bnb_acc.PublicKey().ToAddress(),
    "Private Key": bnb_acc.PrivateKey().Raw().ToHex()
}

# پالیگان
bip44_polygon = Bip44.FromSeed(seed_bytes, Bip44Coins.POLYGON)
polygon_acc = bip44_polygon.Purpose().Coin().Account(0).Change(Bip44Changes.CHAIN_EXT).AddressIndex(0)
wallets["Polygon"] = {
    "Address": polygon_acc.PublicKey().ToAddress(),
    "Private Key": polygon_acc.PrivateKey().Raw().ToHex()
}

# آربیتروم
bip44_arbitrum = Bip44.FromSeed(seed_bytes, Bip44Coins.ARBITRUM)
arbitrum_acc = bip44_arbitrum.Purpose().Coin().Account(0).Change(Bip44Changes.CHAIN_EXT).AddressIndex(0)
wallets["Arbitrum"] = {
    "Address": arbitrum_acc.PublicKey().ToAddress(),
    "Private Key": arbitrum_acc.PrivateKey().Raw().ToHex()
}

# XRP
bip44_xrp = Bip44.FromSeed(seed_bytes, Bip44Coins.RIPPLE)
xrp_acc = bip44_xrp.Purpose().Coin().Account(0).Change(Bip44Changes.CHAIN_EXT).AddressIndex(0)
wallets["XRP"] = {
    "Address": xrp_acc.PublicKey().ToAddress(),
    "Private Key": xrp_acc.PrivateKey().Raw().ToHex()
}

# 🚀 **افزودن بلاکچین‌های جدید** 🚀

# سولانا
bip44_solana = Bip44.FromSeed(seed_bytes, Bip44Coins.SOLANA)
solana_acc = bip44_solana.Purpose().Coin().Account(0).Change(Bip44Changes.CHAIN_EXT).AddressIndex(0)
wallets["Solana"] = {
    "Address": solana_acc.PublicKey().ToAddress(),
    "Private Key": solana_acc.PrivateKey().Raw().ToHex()
}

# آوالانچ (با استاندارد BIP44)
bip44_avax = Bip44.FromSeed(seed_bytes, Bip44Coins.AVAX_C_CHAIN)
avax_acc = bip44_avax.Purpose().Coin().Account(0).Change(Bip44Changes.CHAIN_EXT).AddressIndex(0)
wallets["Avalanche"] = {
    "Address": avax_acc.PublicKey().ToAddress(),
    "Private Key": avax_acc.PrivateKey().Raw().ToHex()
}

bip44_dot = Bip44.FromSeed(seed_bytes, Bip44Coins.POLKADOT_ED25519_SLIP)
dot_acc = bip44_dot.Purpose().Coin().Account(0).Change(Bip44Changes.CHAIN_EXT).AddressIndex(0)

wallets["Polkadot"] = {
    "Address": dot_acc.PublicKey().ToAddress(),
    "Private Key": dot_acc.PrivateKey().Raw().ToHex()
}

# ✅ نمایش خروجی
print("\n🔹 Wallet Information:")
for chain, info in wallets.items():
    print(f"\n{chain}:")
    print(f"  Address: {info['Address']}")
    print(f"  Private Key: {info['Private Key']}")
