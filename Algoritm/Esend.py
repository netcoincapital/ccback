import re
import getpass
from decimal import Decimal
from web3 import Web3
from web3.exceptions import TransactionNotFound
from eth_account import Account

NETWORKS = {
    "1": {
        "name": "Ethereum Mainnet",
        "chain_id": 1,
        "rpc_url": "https://mainnet.infura.io/v3/a8ab43a04ce044de988a838d92f478a7",  # Replace with your valid Infura or other RPC
        "explorer": "https://etherscan.io/tx/"
    },
    "2": {
        "name": "Binance Smart Chain (BSC)",
        "chain_id": 56,
        "rpc_url": "https://bsc-dataseed.binance.org/",
        "explorer": "https://bscscan.com/tx/"
    },
    "3": {
        "name": "Polygon",
        "chain_id": 137,
        "rpc_url": "https://polygon-rpc.com",
        "explorer": "https://polygonscan.com/tx/"
    },
    "4": {
        "name": "Arbitrum",
        "chain_id": 42161,
        "rpc_url": "https://arb1.arbitrum.io/rpc",
        "explorer": "https://arbiscan.io/tx/"
    },
    "5": {
        "name": "Avalanche",
        "chain_id": 43114,
        "rpc_url": "https://api.avax.network/ext/bc/C/rpc",
        "explorer": "https://snowtrace.io/tx/"
    }
}

MIN_ERC20_ABI = [
    {
        "constant": False,
        "inputs": [
            {"name": "_to", "type": "address"},
            {"name": "_value", "type": "uint256"}
        ],
        "name": "transfer",
        "outputs": [
            {"name": "", "type": "bool"}
        ],
        "type": "function"
    }
]


def is_valid_private_key(key: str) -> bool:
    """
    Checks if a given string is a valid 64-character hexadecimal private key.
    Note: This does NOT validate balances, usage, or security best practices.
    """
    return bool(re.fullmatch(r"[0-9a-fA-F]{64}", key))


def get_web3_provider(network_choice: str) -> Web3:
    """
    Returns a Web3 provider connected to the selected network's RPC.
    Raises ValueError if the network choice is invalid.
    """
    if network_choice not in NETWORKS:
        raise ValueError("Invalid network choice.")
    rpc_url = NETWORKS[network_choice]["rpc_url"]
    return Web3(Web3.HTTPProvider(rpc_url))


def get_transaction_url(tx_hash: str, network_choice: str) -> str:
    """
    Returns the explorer URL for a given transaction hash and network.
    """
    base_url = NETWORKS[network_choice]["explorer"]
    return f"{base_url}{tx_hash}"


def get_account_balance(web3: Web3, address: str) -> float:
    """
    Returns the native coin (ETH/BNB/MATIC/etc.) balance of 'address' as a float.
    1 native coin = 10^18 wei.
    """
    balance_wei = web3.eth.get_balance(address)
    balance = Web3.fromWei(balance_wei, 'ether')
    return float(balance)


def estimate_gas_fee(web3: Web3, contract_function, from_address: str, gas_price: int = None):
    """
    Estimates the gas limit and fee for a given contract function call.
    
    Parameters:
      - web3: Web3 provider instance
      - contract_function: e.g., contract.functions.transfer(...)
      - from_address: the sender's address
      - gas_price: optionally override the gas price in wei. If None, tries to use web3.eth.gas_price.
    
    Returns:
      (gas_estimate, fee_in_native) as a tuple.
      If estimation fails, returns (None, "Unknown").
    """
    try:
        if gas_price is None:
            # Attempt to use the network's recommended dynamic gas price
            gas_price = web3.eth.gas_price
        gas_estimate = contract_function.estimateGas({"from": from_address})
        fee_wei = gas_estimate * gas_price
        fee_in_native = Web3.fromWei(fee_wei, 'ether')
        return gas_estimate, float(fee_in_native)
    except Exception:
        return None, "Unknown"


# -----------------------------------------------------------------------------
# Main ERC20 Sending Function
# -----------------------------------------------------------------------------
def send_erc20_token(
    network_choice: str,
    private_key: str,
    contract_address: str,
    to_address: str,
    amount: Decimal,
    decimals: int = 18
):
    """
    Sends an ERC20 token from the sender to the recipient on the chosen EVM network.

    Parameters:
      - network_choice (str): Key in the NETWORKS dict (e.g., '1' for Ethereum).
      - private_key (str): The sender's private key in hex (without '0x' prefix).
      - contract_address (str): The ERC20 contract address.
      - to_address (str): Recipient address (0x...).
      - amount (Decimal): Amount of tokens to send (in human-readable form).
      - decimals (int): Number of decimals for the token (default = 18).
    """
    # 1. Validate private key format
    if not is_valid_private_key(private_key):
        print("❌ Invalid private key format!")
        return None

    # 2. Connect to the selected network
    web3 = get_web3_provider(network_choice)
    if not web3.isConnected():
        print("❌ Failed to connect to the selected network!")
        return None

    # 3. Create the sender account and extract sender's address
    sender_account = Account.from_key(private_key)
    sender_address = sender_account.address

    # 4. Convert token amount to the smallest unit
    #    e.g., if decimals=6 and amount=12.345, smallest_unit = 12345000
    amount_in_smallest_unit = int(amount * (10 ** decimals))

    # 5. Get the sender's native balance (for paying transaction fees)
    sender_balance = get_account_balance(web3, sender_address)

    # 6. Build the contract interface
    contract = web3.eth.contract(
        address=web3.toChecksumAddress(contract_address),
        abi=MIN_ERC20_ABI
    )

    # 7. Prepare the transfer function
    transfer_function = contract.functions.transfer(to_address, amount_in_smallest_unit)

    # 8. Estimate gas and fee
    gas_estimate, fee_estimate = estimate_gas_fee(web3, transfer_function, sender_address)

    if gas_estimate is None or fee_estimate == "Unknown":
        print("⚠️ Unable to estimate gas or fee (Unknown).")
        print("   You may need to set a manual gas price.")
        gas_estimate = "Unknown"
        fee_estimate = "Unknown"

    # 9. Calculate post-transaction balance if possible
    if fee_estimate == "Unknown":
        balance_after_tx = "Unknown"
    else:
        balance_after_tx = sender_balance - fee_estimate

    # 10. Print transaction summary (pre-broadcast)
    chain_name = NETWORKS[network_choice]["name"]
    print(f"\n📌 Transaction Details (Before Sending):")
    print(f"   Network: {chain_name}")
    print(f"   Sender Address: {sender_address}")
    print(f"   Recipient Address: {to_address}")
    print(f"   Token Contract: {contract_address}")
    print(f"   Amount to Send: {amount} tokens")
    print(f"   Sender Balance (Before): {sender_balance} (native)")
    print(f"   Estimated Gas Limit: {gas_estimate}")
    print(f"   Estimated Fee: {fee_estimate} (native)")
    print(f"   Sender Balance (After): {balance_after_tx} (native)\n")

    if balance_after_tx != "Unknown" and balance_after_tx < 0:
        print("❌ Insufficient native balance for the transaction fee!")
        return None

    confirm = input("✅ Do you want to proceed with the transaction? (yes/no): ").strip().lower()
    if confirm != "yes":
        print("🚫 Transaction canceled.")
        return None

    # 11. Build and sign the transaction
    try:
        nonce = web3.eth.get_transaction_count(sender_address)

        # If we want to rely on the dynamic gas price from the network:
        gas_price = web3.eth.gas_price

        # If gas_estimate is not known, we can set a safe upper limit
        if gas_estimate == "Unknown":
            gas_limit = 300000  # A higher fallback to avoid out-of-gas
        else:
            # Add some buffer for any potential fluctuation
            gas_limit = gas_estimate + 10000

        tx_data = transfer_function.buildTransaction({
            "chainId": NETWORKS[network_choice]["chain_id"],
            "from": sender_address,
            "nonce": nonce,
            "gas": gas_limit,
            "gasPrice": gas_price
        })

        signed_tx = sender_account.sign_transaction(tx_data)

        # 12. Broadcast the transaction
        print("🚀 Sending transaction...")
        tx_hash = web3.eth.send_raw_transaction(signed_tx.rawTransaction)
        tx_hash_hex = tx_hash.hex()

        print(f"   Transaction Hash: {tx_hash_hex}")
        print(f"   Waiting for confirmation...")

        # 13. Wait for transaction receipt (confirmation)
        receipt = web3.eth.wait_for_transaction_receipt(tx_hash, timeout=180)
        # status: 1 = success, 0 = failure
        if receipt.status == 1:
            status_msg = "✅ Success"
        else:
            status_msg = "❌ Failed"

        # Calculate the actual fee spent
        actual_gas_used = receipt.gasUsed
        actual_fee_wei = actual_gas_used * gas_price
        actual_fee_native = Web3.fromWei(actual_fee_wei, 'ether')

        # Retrieve updated sender balance
        sender_balance_after = get_account_balance(web3, sender_address)

        print(f"\n✅ Transaction Confirmed!")
        print(f"   Network: {chain_name}")
        print(f"   Transaction Hash: {tx_hash_hex}")
        print(f"   Explorer URL: {get_transaction_url(tx_hash_hex, network_choice)}")
        print(f"   Actual Gas Used: {actual_gas_used}")
        print(f"   Actual Fee: {actual_fee_native} (native)")
        print(f"   Sender Balance (After): {sender_balance_after} (native)")
        print(f"   Status: {status_msg}\n")

        return tx_hash_hex

    except Exception as e:
        print(f"❌ Error while sending transaction: {e}")
        return None

# -----------------------------------------------------------------------------
# Main Entry Point
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    print("Select the network to use:")
    print("1. Ethereum Mainnet")
    print("2. Binance Smart Chain (BSC)")
    print("3. Polygon")
    print("4. Arbitrum")
    print("5. Avalanche")

    network_choice = input("Enter the number of the desired network: ").strip()
    if network_choice not in NETWORKS:
        print("Invalid network choice! Exiting...")
        exit()

    # Securely prompt for the private key (without echoing input)
    private_key = getpass.getpass("Enter your private key (without 0x prefix): ")
    to_address = input("Enter the recipient address (0x...): ")
    contract_address = input("Enter the ERC20 contract address (0x...): ")

    try:
        amount = Decimal(input("Enter the amount of tokens to send: "))
        decimals_str = input("Enter the token decimals (default is 18): ").strip()
        decimals = int(decimals_str) if decimals_str else 18
    except ValueError:
        print("Invalid amount or decimals! Please enter valid numeric values.")
        exit()

    send_erc20_token(
        network_choice=network_choice,
        private_key=private_key,
        contract_address=contract_address,
        to_address=to_address,
        amount=amount,
        decimals=decimals
    )