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

def send_trx(private_key, to_address, amount):
    """ Send TRX from one wallet to another. """
    try:
        if not is_valid_private_key(private_key):
            print("Invalid private key format!")
            return None

        sender_private_key = PrivateKey(bytes.fromhex(private_key))
        sender_address = sender_private_key.public_key.to_address()

        if not client.is_address(to_address):
            print("Invalid recipient address!")
            return None

        sender_balance = client.get_account_balance(sender_address)
        print(f"\n📌 **Transaction Details (Before Sending):**")
        print(f"   🔹 Sender Address: {sender_address}")
        print(f"   🔹 Recipient Address: {to_address}")
        print(f"   🔹 Amount: {amount} TRX")
        print(f"   🔹 Sender Balance: {sender_balance} TRX\n")

        if sender_balance < amount:
            print("❌ Insufficient balance!")
            return None

        confirm = input("✅ Confirm transaction? (yes/no): ").strip().lower()
        if confirm != "yes":
            print("🚫 Transaction canceled.")
            return None

        txn = (
            client.trx.transfer(sender_address, to_address, int(float(amount) * 1_000_000))
            .build()
            .sign(sender_private_key)
        )

        print("🚀 Sending transaction...")

        txn_hash = txn.broadcast().wait()
        txn_id = txn_hash["id"]  # ✅ استخراج هش تراکنش

        print(f"\n✅ **Transaction Successfully Sent!**")
        print(f"   🔹 Transaction Hash: {txn_id}")
        print(f"   🔹 Transaction URL: {get_transaction_url(txn_id)}")

        # ✅ دریافت هزینه واقعی تراکنش
        tx_info = client.get_transaction_info(txn_id)
        fee_in_sun = tx_info.get("fee", 0)
        fee_in_trx = fee_in_sun / 1_000_000  # Convert from Sun to TRX
        print(f"   🔹 Actual Transaction Fee: {fee_in_trx} TRX\n")

        return txn_id

    except TransactionError as e:
        print(f"❌ Transaction Error: {e}")
    except Exception as e:
        print(f"❌ An error occurred: {e}")

def send_trc20(private_key, contract_address, to_address, amount, decimals=6):
    """
    Send TRC20 token from one wallet to another.
    """
    try:
        if not is_valid_private_key(private_key):
            print("Invalid private key format!")
            return None

        sender_private_key = PrivateKey(bytes.fromhex(private_key))
        sender_address = sender_private_key.public_key.to_address()

        # Convert amount to smallest unit
        amount_in_smallest_unit = int(amount * (10 ** decimals))

        print(f"\n📌 **Transaction Details (Before Sending):**")
        print(f"   🔹 Sender Address: {sender_address}")
        print(f"   🔹 Recipient Address: {to_address}")
        print(f"   🔹 Token Contract: {contract_address}")
        print(f"   🔹 Amount: {amount} Tokens\n")

        confirm = input("✅ Confirm transaction? (yes/no): ").strip().lower()
        if confirm != "yes":
            print("🚫 Transaction canceled.")
            return None

        txn = (
            client.trx.contract(contract_address)
            .functions.transfer(to_address, amount_in_smallest_unit)
            .with_owner(sender_address)
            .build()
            .sign(sender_private_key)
        )

        print("🚀 Sending transaction...")

        txn_hash = txn.broadcast().wait()
        txn_id = txn_hash["id"]  # ✅ استخراج هش تراکنش

        print(f"\n✅ **Transaction Successfully Sent!**")
        print(f"   🔹 Transaction Hash: {txn_id}")
        print(f"   🔹 Transaction URL: {get_transaction_url(txn_id)}")

        # ✅ دریافت هزینه واقعی تراکنش
        tx_info = client.get_transaction_info(txn_id)
        fee_in_sun = tx_info.get("fee", 0)
        fee_in_trx = fee_in_sun / 1_000_000  # Convert from Sun to TRX
        print(f"   🔹 Actual Transaction Fee: {fee_in_trx} TRX\n")

        return txn_id

    except TransactionError as e:
        print(f"❌ Transaction Error: {e}")
    except Exception as e:
        print(f"❌ An error occurred: {e}")

if __name__ == "__main__":
    print("Select Transaction Type:\n1. Send TRX\n2. Send TRC20 Token")
    choice = input("Enter 1 or 2: ")

    private_key = getpass.getpass("Enter your private key: ")
    to_address = input("Enter recipient's address: ")

    if choice == "1":
        try:
            amount = Decimal(input("Enter amount of TRX to send: "))
        except ValueError:
            print("Invalid amount! Please enter a number.")
            exit()
        send_trx(private_key, to_address, amount)

    elif choice == "2":
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