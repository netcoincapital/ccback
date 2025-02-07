from web3 import Web3
from eth_account import Account

# -------------------------- ERC20 ABI گسترش‌یافته --------------------------
# متدهای transfer, decimals, balanceOf, symbol
ERC20_ABI = [
    {
        "constant": False,
        "inputs": [
            {"name": "_to", "type": "address"},
            {"name": "_value", "type": "uint256"}
        ],
        "name": "transfer",
        "outputs": [{"name": "", "type": "bool"}],
        "type": "function"
    },
    {
        "constant": True,
        "inputs": [],
        "name": "decimals",
        "outputs": [{"name": "", "type": "uint8"}],
        "type": "function"
    },
    {
        "constant": True,
        "inputs": [
            {"name": "_owner", "type": "address"}
        ],
        "name": "balanceOf",
        "outputs": [{"name": "", "type": "uint256"}],
        "type": "function"
    },
    {
        "constant": True,
        "inputs": [],
        "name": "symbol",
        "outputs": [{"name": "", "type": "string"}],
        "type": "function"
    }
]

# --------------------------- RPC های معتبر برای شبکه‌ها ---------------------------
ETHEREUM_PROVIDER  = "https://mainnet.infura.io/v3/a8ab43a04ce044de988a838d92f478a7"    # با مقدار Project ID خودتان جایگزین کنید
BSC_PROVIDER       = "https://bsc-dataseed1.binance.org"
POLYGON_PROVIDER   = "https://polygon-mainnet.infura.io/v3/a8ab43a04ce044de988a838d92f478a7"  # با مقدار Project ID خودتان جایگزین کنید
ARBITRUM_PROVIDER  = "https://arb1.arbitrum.io/rpc"
AVALANCHE_PROVIDER = "https://api.avax.network/ext/bc/C/rpc"

# --------------------------- ساخت Web3 برای هر شبکه ---------------------------
ethereum_network  = Web3(Web3.HTTPProvider(ETHEREUM_PROVIDER))
bsc_network       = Web3(Web3.HTTPProvider(BSC_PROVIDER))
polygon_network   = Web3(Web3.HTTPProvider(POLYGON_PROVIDER))
arbitrum_network  = Web3(Web3.HTTPProvider(ARBITRUM_PROVIDER))
avalanche_network = Web3(Web3.HTTPProvider(AVALANCHE_PROVIDER))

# نمایش وضعیت اتصال
print("Ethereum:",  "Connected" if ethereum_network.is_connected()  else "Not connected")
print("BSC:     ",  "Connected" if bsc_network.is_connected()       else "Not connected")
print("Polygon: ",  "Connected" if polygon_network.is_connected()   else "Not connected")
print("Arbitrum:",  "Connected" if arbitrum_network.is_connected()  else "Not connected")
print("Avalanche:", "Connected" if avalanche_network.is_connected() else "Not connected")


def get_eip1559_fees(network):
    """
    تلاش برای محاسبه پویا بر اساس آخرین بلاک و max_priority_fee.
    اگر شبکه از EIP-1559 پشتیبانی نکند یا اطلاعات بلاک ناقص باشد،
    None برمی‌گرداند.
    """
    try:
        latest_block = network.eth.get_block("latest")
        # اگر بلاک دارای baseFeePerGas باشد، یعنی از EIP-1559 پشتیبانی می‌کند
        base_fee = latest_block.get("baseFeePerGas", None)
        if base_fee is not None:
            # تلاش برای بدست آوردن priority_fee به شکل پیش‌فرض وب3
            priority_fee = None
            try:
                priority_fee = network.eth.max_priority_fee
            except:
                # اگر متد max_priority_fee وجود نداشت، یک مقدار پیش‌فرض در نظر می‌گیریم
                priority_fee = network.to_wei("2", "gwei")

            # محاسبه‌ی یک maxFeePerGas با ضریب 1.2 روی baseFee + priorityFee
            max_fee_per_gas = int(base_fee * 1.2 + priority_fee)
            max_priority_fee_per_gas = int(priority_fee)

            return (max_fee_per_gas, max_priority_fee_per_gas)
        else:
            return None
    except:
        return None


def send_native_transaction(network, private_key, to_address, value_in_ether, network_name):
    """
    ارسال کوین اصلی شبکه با در نظر گرفتن EIP-1559 برای شبکه‌هایی که پشتیبانی می‌کنند.
    اگر شبکه Legacy باشد (مانند BSC) یا اطلاعات EIP-1559 در دسترس نباشد، از gasPrice استفاده می‌کنیم.
    """
    try:
        sender_address = Account.from_key(private_key).address
        balance = network.eth.get_balance(sender_address)
        balance_in_ether = network.from_wei(balance, "ether")
        print(f"Sender Address: {sender_address}")
        print(f"Sender {network_name} Balance: {balance_in_ether}")

        if balance_in_ether < value_in_ether:
            print("Insufficient balance!")
            return None

        nonce = network.eth.get_transaction_count(sender_address)
        chain_id = network.eth.chain_id

        eip1559_fees = get_eip1559_fees(network)
        if eip1559_fees is not None and network_name != "Binance Smart Chain":
            # شبکه از EIP-1559 پشتیبانی می‌کند
            max_fee_per_gas, max_priority_fee_per_gas = eip1559_fees
            tx = {
                "chainId": chain_id,
                "to": to_address,
                "value": network.to_wei(value_in_ether, "ether"),
                "gas": 21000,
                "maxFeePerGas": max_fee_per_gas,
                "maxPriorityFeePerGas": max_priority_fee_per_gas,
                "nonce": nonce
            }
        else:
            # Legacy (برای BSC یا شبکه‌هایی که EIP-1559 را پشتیبانی نمی‌کنند)
            gas_price = network.eth.gas_price  # مقدار پویا از شبکه
            tx = {
                "chainId": chain_id,
                "to": to_address,
                "value": network.to_wei(value_in_ether, "ether"),
                "gas": 21000,
                "gasPrice": gas_price,
                "nonce": nonce
            }

        signed_txn = network.eth.account.sign_transaction(tx, private_key)
        tx_hash = network.eth.send_raw_transaction(signed_txn.rawTransaction)
        tx_hash_hex = network.to_hex(tx_hash)
        print(f"Transaction sent! Hash: {tx_hash_hex}")
        return tx_hash_hex

    except Exception as e:
        print(f"An error occurred: {e}")
        return None


def send_token_transaction(network, private_key, token_address, to_address, amount_in_tokens, network_name):
    """
    ارسال توکن ERC20 (یا سازگار) در شبکه‌های مختلف EVM، با درنظرگرفتن EIP-1559.
    اگر شبکه پشتیبانی نکند، از روش Legacy (gasPrice) استفاده می‌شود.
    """
    try:
        sender_address = Account.from_key(private_key).address
        chain_id = network.eth.chain_id

        contract = network.eth.contract(
            address=Web3.to_checksum_address(token_address),
            abi=ERC20_ABI
        )

        # تعداد اعشار توکن
        decimals = contract.functions.decimals().call()
        amount_wei = int(amount_in_tokens * (10 ** decimals))

        # (اختیاری) نمایش بالانس فعلی توکن فرستنده
        sender_balance_wei = contract.functions.balanceOf(sender_address).call()
        sender_balance_tokens = sender_balance_wei / (10 ** decimals)
        token_symbol = contract.functions.symbol().call()
        print(f"Sender has {sender_balance_tokens} {token_symbol}")

        # بررسی اینکه آیا بالانس توکن کافی است (اختیاری)
        if sender_balance_tokens < amount_in_tokens:
            print("Insufficient token balance!")
            return None

        nonce = network.eth.get_transaction_count(sender_address)
        # تخمین اولیه برای انتقال توکن
        gas_limit_estimated = contract.functions.transfer(
            Web3.to_checksum_address(to_address),
            amount_wei
        ).estimate_gas({
            "from": sender_address
        })
        # حاشیه امنیت
        gas_limit = int(gas_limit_estimated * 1.2)

        eip1559_fees = get_eip1559_fees(network)
        if eip1559_fees is not None and network_name != "Binance Smart Chain":
            max_fee_per_gas, max_priority_fee_per_gas = eip1559_fees
            tx = contract.functions.transfer(
                Web3.to_checksum_address(to_address),
                amount_wei
            ).build_transaction({
                "chainId": chain_id,
                "gas": gas_limit,
                "maxFeePerGas": max_fee_per_gas,
                "maxPriorityFeePerGas": max_priority_fee_per_gas,
                "nonce": nonce
            })
        else:
            # Legacy (BSC یا شبکه‌هایی که EIP-1559 ندارند)
            gas_price = network.eth.gas_price
            tx = contract.functions.transfer(
                Web3.to_checksum_address(to_address),
                amount_wei
            ).build_transaction({
                "chainId": chain_id,
                "gas": gas_limit,
                "gasPrice": gas_price,
                "nonce": nonce
            })

        signed_txn = network.eth.account.sign_transaction(tx, private_key)
        tx_hash = network.eth.send_raw_transaction(signed_txn.rawTransaction)
        tx_hash_hex = network.to_hex(tx_hash)
        print(f"Token transfer sent! Hash: {tx_hash_hex}")
        return tx_hash_hex

    except Exception as e:
        print(f"An error occurred: {e}")
        return None


if __name__ == "__main__":
    print("Select the blockchain network:")
    print("1. Ethereum")
    print("2. Binance Smart Chain")
    print("3. Polygon")
    print("4. Arbitrum")
    print("5. Avalanche")

    network_choice = input("Enter the number of the network (1-5): ").strip()

    if network_choice == "1":
        network = ethereum_network
        network_name = "Ethereum"
    elif network_choice == "2":
        network = bsc_network
        network_name = "Binance Smart Chain"
    elif network_choice == "3":
        network = polygon_network
        network_name = "Polygon"
    elif network_choice == "4":
        network = arbitrum_network
        network_name = "Arbitrum"
    elif network_choice == "5":
        network = avalanche_network
        network_name = "Avalanche"
    else:
        print("Invalid choice! Exiting...")
        exit()

    # انتخاب نوع تراکنش
    print(f"\nSelected network: {network_name}")
    print("Choose transaction type:")
    print("1. Send native coin")
    print("2. Send token (ERC20-compatible)")

    tx_type_choice = input("Enter choice (1 or 2): ").strip()

    private_key = input("Enter your private key (hex): ").strip()
    to_address = input("Enter recipient's address: ").strip()

    if tx_type_choice == "1":
        amount = float(input(f"Enter amount to send in {network_name}'s native coin: "))
        send_native_transaction(network, private_key, to_address, amount, network_name)
    elif tx_type_choice == "2":
        token_address = input("Enter the token contract address: ").strip()
        amount = float(input("Enter amount of tokens to send: "))
        send_token_transaction(network, private_key, token_address, to_address, amount, network_name)
    else:
        print("Invalid choice for transaction type!")
