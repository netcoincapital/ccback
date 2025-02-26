import re
import getpass
from decimal import Decimal
from substrateinterface import SubstrateInterface, Keypair
from substrateinterface.exceptions import SubstrateRequestException

# --- ست کردن آدرس وب‌سوکت پولکادات ---
POLKADOT_WEBSOCKET = "wss://rpc.polkadot.io"

# --- اتصال به شبکه پولکادات ---
substrate = SubstrateInterface(
    url=POLKADOT_WEBSOCKET,
    type_registry_preset='polkadot'
)

def get_extrinsic_url(ex_hash):
    """ برگرداندن لینک تراکنش در Subscan برای هش مربوطه. """
    return f"https://polkadot.subscan.io/extrinsic/{ex_hash}"

def is_valid_private_key(key):
    """
    بررسی فرمت کلیدخصوصی (Seed هگز ۶۴ حرفی).
    توجه داشته باشید که در پولکادات معمولاً از عبارت‌های 12/24 کلمه‌ای یا 
    فرمت‌های دیگر هم می‌توان استفاده کرد. اینجا صرفاً شکل هگز بررسی می‌شود.
    """
    return bool(re.fullmatch(r"[0-9a-fA-F]{64}", key))

def estimate_fee_polkadot(call, keypair):
    """
    تخمین کارمزد تراکنش قبل از ارسال.
    از متد get_payment_info برای برآورد هزینه استفاده می‌کنیم.
    """
    try:
        payment_info = substrate.get_payment_info(call=call, keypair=keypair)
        # مقدار برمی‌گردانده‌شده در واحد پلنک (Planck) است. 1 DOT = 10^10 Planck
        estimated_fee = int(payment_info['partialFee']) / 10**10
        return round(estimated_fee, 6)
    except Exception:
        return "Unknown"

def get_account_info(address):
    """
    گرفتن اطلاعات حساب، در اینجا فقط موجودی آزاد (Free Balance) را برمی‌گرداند.
    """
    try:
        account_info = substrate.query("System", "Account", [address]).value
        free_balance = account_info['data']['free']
        return int(free_balance) / 10**10
    except Exception:
        return "Unknown"

def send_dot_asset(private_key, to_address, amount):
    """
    ارسال توکن DOT از یک آدرس به آدرس دیگر.
    """
    try:
        if not is_valid_private_key(private_key):
            print("Invalid private key format!")
            return None

        # ساخت Keypair از روی seed هگز
        sender_keypair = Keypair.create_from_seed(bytes.fromhex(private_key))
        sender_address = sender_keypair.ss58_address

        # تبدیل مقدار DOT به Planck
        amount_in_planck = int(amount * 10**10)

        # بررسی موجودی فرستنده
        sender_balance = get_account_info(sender_address)

        # ساخت Call برای Balances.transfer
        call = substrate.compose_call(
            call_module='Balances',
            call_function='transfer',
            call_params={
                'dest': to_address,
                'value': amount_in_planck
            }
        )

        # تخمین کارمزد
        estimated_fee = estimate_fee_polkadot(call, sender_keypair)
        balance_after_tx = sender_balance - estimated_fee if estimated_fee != "Unknown" else "Unknown"

        print(f"\n📌 **Transaction Details (Before Sending):**")
        print(f"   🔹 Sender Address: {sender_address}")
        print(f"   🔹 Recipient Address: {to_address}")
        print(f"   🔹 Amount: {amount} DOT")
        print(f"   🔹 Sender Balance (Before): {sender_balance} DOT")
        print(f"   🔹 Estimated Fee: {estimated_fee} DOT")
        print(f"   🔹 Sender Balance (After): {balance_after_tx} DOT\n")

        # بررسی کافی‌بودن موجودی
        if balance_after_tx != "Unknown" and balance_after_tx < 0:
            print("❌ Warning: Insufficient balance for this transaction!")
            return None

        # گرفتن تایید کاربر
        confirm = input("✅ Confirm transaction? (yes/no): ").strip().lower()
        if confirm != "yes":
            print("🚫 Transaction canceled.")
            return None

        # ایجاد Extrinsic امضا شده
        extrinsic = substrate.create_signed_extrinsic(
            call=call,
            keypair=sender_keypair
        )

        print("🚀 Sending transaction...")

        # ارسال تراکنش و انتظار برای ورود به بلاک
        receipt = substrate.submit_extrinsic(extrinsic, wait_for_inclusion=True)
        ex_hash = receipt.extrinsic_hash

        # محاسبه هزینهٔ واقعی از اطلاعات دریافت‌شده
        fee_in_planck = receipt.total_fee_amount
        fee_in_dot = fee_in_planck / 10**10
        status = "SUCCESS" if receipt.is_success else "FAILED"

        sender_balance_after = get_account_info(sender_address)

        print(f"\n✅ **Transaction Successfully Sent!**")
        print(f"   🔹 Extrinsic Hash: {ex_hash}")
        print(f"   🔹 Transaction URL: {get_extrinsic_url(ex_hash)}")
        print(f"   🔹 Actual Fee: {fee_in_dot} DOT")
        print(f"   🔹 Sender Balance (After): {sender_balance_after} DOT")
        print(f"   🔹 Status: {status}\n")

        return ex_hash

    except SubstrateRequestException as e:
        print(f"❌ Transaction Error: {e}")
    except Exception as e:
        print(f"❌ An error occurred: {e}")

if __name__ == "__main__":
    print("Select Transaction Type:\n1. Send DOT")
    choice = input("Enter 1 to send DOT: ")

    private_key = getpass.getpass("Enter your private key (hex seed): ")
    to_address = input("Enter recipient's address (SS58): ")

    if choice == "1":
        try:
            amount = Decimal(input("Enter amount of DOT to send: "))
        except ValueError:
            print("Invalid amount! Please enter a number.")
            exit()
        send_dot_asset(private_key, to_address, amount)
    else:
        print("Invalid choice! Exiting...")
