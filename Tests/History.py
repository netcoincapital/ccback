from bip_utils import Bip44Coins

print([coin for coin in dir(Bip44Coins) if not coin.startswith("_")])
