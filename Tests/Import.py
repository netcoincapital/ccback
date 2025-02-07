import requests
import time
from bip_utils import (
    Bip39SeedGenerator, Bip44, Bip84, Bip44Coins, Bip49Coins, Bip84Coins,
    Bip86Coins, Bip44Changes
)

# دریافت عبارت بازیابی از کاربر
mnemonic = input("Enter your 12/24-word mnemonic phrase: ").strip()

# بررسی صحت عبارت بازیابی
mnemonic_words = mnemonic.split()
if len(mnemonic_words) not in [12, 24]:
    print("❌ Error: Mnemonic phrase must contain exactly 12 or 24 words.")
    exit()

# تولید Seed از عبارت بازیابی
try:
    seed_bytes = Bip39SeedGenerator(mnemonic).Generate()
except Exception as e:
    print(f"❌ Error: Invalid mnemonic phrase - {str(e)}")
    exit()

# تولید کیف پول‌های بلاک‌چین‌های مختلف
wallets = {}

# بیت‌کوین (Bech32 - bc1)
bip84 = Bip84.FromSeed(seed_bytes, Bip84Coins.BITCOIN)
btc_acc = bip84.Purpose().Coin().Account(0).Change(Bip44Changes.CHAIN_EXT).AddressIndex(0)
wallets["Bitcoin (Bech32)"] = btc_acc.PublicKey().ToAddress()

# اتریوم
bip44_eth = Bip44.FromSeed(seed_bytes, Bip44Coins.ETHEREUM)
eth_acc = bip44_eth.Purpose().Coin().Account(0).Change(Bip44Changes.CHAIN_EXT).AddressIndex(0)
wallets["Ethereum"] = eth_acc.PublicKey().ToAddress()

# ترون (Tron)
bip44_tron = Bip44.FromSeed(seed_bytes, Bip44Coins.TRON)
tron_acc = bip44_tron.Purpose().Coin().Account(0).Change(Bip44Changes.CHAIN_EXT).AddressIndex(0)
wallets["Tron"] = tron_acc.PublicKey().ToAddress()

# بایننس اسمارت چین (BNB)
bip44_bnb = Bip44.FromSeed(seed_bytes, Bip44Coins.BINANCE_SMART_CHAIN)
bnb_acc = bip44_bnb.Purpose().Coin().Account(0).Change(Bip44Changes.CHAIN_EXT).AddressIndex(0)
wallets["BNB (BSC)"] = bnb_acc.PublicKey().ToAddress()

# پالیگان (Polygon)
bip44_polygon = Bip44.FromSeed(seed_bytes, Bip44Coins.POLYGON)
polygon_acc = bip44_polygon.Purpose().Coin().Account(0).Change(Bip44Changes.CHAIN_EXT).AddressIndex(0)
wallets["Polygon"] = polygon_acc.PublicKey().ToAddress()

# کلیدهای API
ETHERSCAN_API_KEY = "77D1W3AMVN6ZGUXQ7116ECFQC2M9M3WFKY"
BSCSCAN_API_KEY = "AXZ8211BAB2GVKKMMUVU24ERT858ZGE3SJ"
POLYGONSCAN_API_KEY = "a8ab43a04ce044de988a838d92f478a7"
TRONSCAN_API_KEY = "87a006f2-b397-4961-9597-cb2a7e7e5577"

# دریافت موجودی کیف پول از API
def get_balance(address, coin, api_key=None, tron_api_key=None):
    try:
        if coin == "Bitcoin (Bech32)":
            url = f"https://blockchain.info/q/addressbalance/{address}"
            response = requests.get(url).text
            balance = int(response) / 1e8
            return f"{balance} BTC", {}

        elif coin in ["Ethereum", "BNB (BSC)", "Polygon"]:
            if coin == "Polygon":
                url = f"https://polygon-mainnet.infura.io/v3/{api_key}"
                payload = {"jsonrpc":"2.0","method":"eth_getBalance","params":[address, "latest"],"id":1}
                headers = {"Content-Type": "application/json"}
                response = requests.post(url, json=payload, headers=headers).json()
            else:
                base_url = "https://api.etherscan.io/api" if coin == "Ethereum" else "https://api.bscscan.com/api"
                url = f"{base_url}?module=account&action=balance&address={address}&tag=latest&apikey={api_key}"
                response = requests.get(url).json()
            
            if "result" not in response:
                return f"Error: {response}", {}
            
            balance = int(response["result"], 16 if coin == "Polygon" else 10) / 1e18
            token_balances = get_tokens(address, api_key, coin)
            return f"{balance} {coin.split()[0]}", token_balances

        elif coin == "Tron":
            url = f"https://apilist.tronscanapi.com/api/account?address={address}"
            headers = {"TRONSCAN-API-KEY": tron_api_key} if tron_api_key else {}
            response = requests.get(url, headers=headers).json()

            if "balance" not in response:
                return "Error: API response issue", {}

            balance_trx = response["balance"] / 1_000_000
            token_balances = get_tron_tokens(address, tron_api_key)
            return f"{balance_trx} TRX", token_balances

        else:
            return "N/A", {}

    except Exception as e:
        return f"Error: {str(e)}", {}

# دریافت توکن‌های ERC-20 و BEP-20
def get_tokens(address, api_key, network):
    try:
        base_url = "https://api.etherscan.io/api" if network == "Ethereum" else "https://api.bscscan.com/api"
        url = f"{base_url}?module=account&action=tokenbalance&contractaddress={address}&tag=latest&apikey={api_key}"
        response = requests.get(url).json()
        return {network: int(response["result"]) / 1e18} if "result" in response and response["result"].isdigit() else {}
    except:
        return {}

# دریافت توکن‌های TRC-20
def get_tron_tokens(address, tron_api_key):
    try:
        url = f"https://apilist.tronscanapi.com/api/account?address={address}"
        headers = {"TRONSCAN-API-KEY": tron_api_key} if tron_api_key else {}
        response = requests.get(url, headers=headers).json()
        return {token["tokenName"]: int(token["balance"]) / 10 ** token["tokenDecimal"] for token in response.get("tokenBalances", [])}
    except:
        return {}

# نمایش خروجی
for chain, address in wallets.items():
    print(f"\n🔹 {chain}")
    print(f"   Public Address: {address}")

    api_key = ETHERSCAN_API_KEY if chain == "Ethereum" else BSCSCAN_API_KEY if chain == "BNB (BSC)" else POLYGONSCAN_API_KEY
    balance, tokens = get_balance(address, chain, api_key, TRONSCAN_API_KEY if chain == "Tron" else None)
    
    print(f"   Balance: {balance}")
    
    if tokens:
        print("   Tokens:")
        for token, amount in tokens.items():
            print(f"     - {token}: {amount}")
    
    time.sleep(1)