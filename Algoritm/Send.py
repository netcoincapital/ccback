import re
import getpass
from decimal import Decimal
from tronpy import Tron
from tronpy.keys import PrivateKey
from tronpy.providers import HTTPProvider  
from tronpy.exceptions import TransactionError

# --- Set Trongrid API Key and Network URI ---
TRONGRID_API_KEY = "61d401f5-27e5-4de7-81ae-a9a48a7fc5d8"
TRONGRID_URI = "https://api.trongrid.io"

# --- Configure Tron client ---
client = Tron(provider=HTTPProvider(endpoint_uri=TRONGRID_URI, api_key=TRONGRID_API_KEY))

def get_transaction_url(tx_hash):
    """ Returns the TronScan URL for a given transaction hash. """
    return f"https://tronscan.org/#/transaction/{tx_hash}"

def is_valid_private_key(key):
    return bool(re.fullmatch(r"[0-9a-fA-F]{64}", key))

def estimate_fee(txn):
    """ Estimate transaction fee before sending. """
    try:
        tx_info = txn.estimate_energy()
        estimated_fee_sun = tx_info * 280  # Approximate cost per energy unit
        estimated_fee_trx = estimated_fee_sun / 1_000_000  # Convert from Sun to TRX
        return round(estimated_fee_trx, 6)
    except Exception:
        return "Unknown"

def get_bandwidth_energy(address):
    """ Fetch Bandwidth and Energy information for the given address. """
    try:
        account_info = client.get_account_resource(address)
        bandwidth = account_info.get("freeNetUsed", 0) + account_info.get("netUsed", 0)
        energy = account_info.get("energyUsed", 0)
        return bandwidth, energy
    except Exception:
        return "Unknown", "Unknown"

def send_trc20(private_key, contract_address, to_address, amount, decimals=6):
    """
    Send TRC20 token from one wallet to another.
    """
    try:
        if not is_valid_private_key(private_key):
            print("Invalid private key format!")
            return None

        sender_private_key = PrivateKey(bytes.fromhex(private_key))
        sender_address = sender_private_key.public_key.to_base58check_address()

        amount_in_smallest_unit = int(amount * (10 ** decimals))
        sender_balance = client.get_account_balance(sender_address)
        contract = client.get_contract(contract_address)
        
        txn = (
            contract.functions.transfer(to_address, amount_in_smallest_unit)
            .with_owner(sender_address)
            .build()
        )

        estimated_fee = estimate_fee(txn)
        bandwidth, energy = get_bandwidth_energy(sender_address)
        balance_after_tx = sender_balance - estimated_fee if estimated_fee != "Unknown" else "Unknown"
        
        print(f"\n📌 **Transaction Details (Before Sending):**")
        print(f"   🔹 Sender Address: {sender_address}")
        print(f"   🔹 Recipient Address: {to_address}")
        print(f"   🔹 Token Contract: {contract_address}")
        print(f"   🔹 Amount: {amount} Tokens")
        print(f"   🔹 Sender Balance (Before): {sender_balance} TRX")
        print(f"   🔹 Estimated Fee: {estimated_fee} TRX")
        print(f"   🔹 Bandwidth Used: {bandwidth}")
        print(f"   🔹 Energy Used: {energy}")
        print(f"   🔹 Sender Balance (After): {balance_after_tx} TRX\n")
        
        if balance_after_tx != "Unknown" and balance_after_tx < 0:
            print("❌ Warning: Insufficient balance for this transaction!")
            return None

        confirm = input("✅ Confirm transaction? (yes/no): ").strip().lower()
        if confirm != "yes":
            print("🚫 Transaction canceled.")
            return None

        txn = txn.sign(sender_private_key)
        print("🚀 Sending transaction...")

        txn_hash = txn.broadcast().wait()
        txn_id = txn_hash["id"]

        tx_info = client.get_transaction_info(txn_id)
        fee_in_sun = tx_info.get("fee", 0)
        fee_in_trx = fee_in_sun / 1_000_000  # Convert from Sun to TRX
        result = tx_info.get("contractResult", ["N/A"])[0]
        status = "✅ Success" if tx_info.get("receipt", {}).get("result") == "SUCCESS" else "❌ Failed"

        sender_balance_after = client.get_account_balance(sender_address)

        print(f"\n✅ **Transaction Successfully Sent!**")
        print(f"   🔹 Transaction Hash: {txn_id}")
        print(f"   🔹 Transaction URL: {get_transaction_url(txn_id)}")
        print(f"   🔹 Actual Fee: {fee_in_trx} TRX")
        print(f"   🔹 Sender Balance (After): {sender_balance_after} TRX")
        print(f"   🔹 Result: {result}")
        print(f"   🔹 Status: {status}\n")

        return txn_id

    except TransactionError as e:
        print(f"❌ Transaction Error: {e}")
    except Exception as e:
        print(f"❌ An error occurred: {e}")

if __name__ == "__main__":
    print("Select Transaction Type:\n1. Send TRC20 Token")
    choice = input("Enter 1 to send TRC20 Token: ")

    private_key = getpass.getpass("Enter your private key: ")
    to_address = input("Enter recipient's address: ")

    if choice == "1":
        contract_address = input("Enter TRC20 contract address: ")
        try:
            amount = Decimal(input("Enter amount of token to send: "))
            decimals = int(input("Enter token decimals (default is 6): ") or 6)
        except ValueError:
            print("Invalid amount or decimals! Please enter a number.")
            exit()
        send_trc20(private_key, contract_address, to_address, amount, decimals)

    else:
        print("Invalid choice! Exiting...")