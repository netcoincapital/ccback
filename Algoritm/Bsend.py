import re
import getpass
from decimal import Decimal
from bit import wif_to_key
from bit.exceptions import InsufficientFunds

def get_btc_transaction_url(tx_hash):
    """Returns a Blockchain explorer URL for a given BTC transaction hash."""
    return f"https://www.blockchain.com/btc/tx/{tx_hash}"

def is_valid_wif_key(key):
    """
    بررسی می‌کند که آیا کلید خصوصی در فرمت WIF ممکن است معتبر باشد یا خیر.
    این تابع تنها بر اساس طول (و نه بررسی همهٔ جزییات) عمل می‌کند.
    شما می‌توانید منطق دقیق‌تری اضافه کنید.
    """
    # فرمت WIF معمولاً بین 51 تا 52 کاراکتر است (برخی حتی ممکن است 53 هم باشند).
    return 50 <= len(key) <= 60

def estimate_btc_fee(amount_btc, num_outputs=1, priority="medium"):
    """
    محاسبهٔ کارمزد تخمینی شبکهٔ بیت‌کوین.
    مقدار بازگشتی صرفاً یک مثال است و در عمل باید بر اساس شرایط شبکه محاسبه شود.
    """
    # برای نمونه، یک مقدار کارمزد ثابت (0.0001 BTC) برمی‌گردانیم.
    return Decimal("0.0001")

def send_btc(private_key, to_address, amount_btc):
    """
    ارسال بیت‌کوین از طریق کلید خصوصی به فرمت WIF.
    پارامتر `amount_btc` مقداری است که در شبکهٔ BTC ارسال می‌شود.
    """
    try:
        if not is_valid_wif_key(private_key):
            print("Invalid private key format (expected WIF)!")
            return None

        # کلید خصوصی را از فرمت WIF تبدیل می‌کنیم.
        key = wif_to_key(private_key)

        # موجودی فرستنده (در BTC)
        sender_balance_btc = Decimal(key.get_balance("btc"))
        amount_btc = Decimal(amount_btc)

        # برآورد کارمزد (مثالی)
        estimated_fee_btc = estimate_btc_fee(amount_btc)

        # موجودی فرستنده پس از تراکنش
        balance_after_tx = sender_balance_btc - amount_btc - estimated_fee_btc

        print(f"\n📌 **Transaction Details (Before Sending):**")
        print(f"   🔹 Sender Address: {key.address}")
        print(f"   🔹 Recipient Address: {to_address}")
        print(f"   🔹 Amount: {amount_btc} BTC")
        print(f"   🔹 Sender Balance (Before): {sender_balance_btc} BTC")
        print(f"   🔹 Estimated Fee: {estimated_fee_btc} BTC")
        print(f"   🔹 Sender Balance (After): {balance_after_tx} BTC\n")

        # بررسی کافی بودن موجودی
        if balance_after_tx < 0:
            print("❌ Warning: Insufficient balance for this transaction!")
            return None

        confirm = input("✅ Confirm transaction? (yes/no): ").strip().lower()
        if confirm != "yes":
            print("🚫 Transaction canceled.")
            return None

        print("🚀 Sending transaction...")

        # متد send در کتابخانه bit، پس از مشخص کردن مقدار و مقصد، تراکنش را می‌سازد و آن را امضا و منتشر می‌کند.
        tx_hash = key.send([(to_address, float(amount_btc), "btc")])

        if not tx_hash:
            print("❌ Transaction failed; tx_hash is empty.")
            return None

        # چاپ جزئیات پس از ارسال
        sender_balance_after = Decimal(key.get_balance("btc"))

        print(f"\n✅ **Transaction Successfully Sent!**")
        print(f"   🔹 Transaction Hash: {tx_hash}")
        print(f"   🔹 Transaction URL: {get_btc_transaction_url(tx_hash)}")
        print(f"   🔹 Actual Fee: کارمزد بر اساس سایز نهایی تراکنش کسر شده است.")
        print(f"   🔹 Sender Balance (After): {sender_balance_after} BTC")
        print(f"   🔹 Status: ✅ Success\n")

        return tx_hash

    except InsufficientFunds:
        print("❌ Transaction Error: Insufficient funds!")
    except Exception as e:
        print(f"❌ An error occurred: {e}")

if __name__ == "__main__":
    print("Select Transaction Type:\n1. Send BTC")
    choice = input("Enter 1 to send BTC: ")

    private_key = getpass.getpass("Enter your private key (WIF format): ")
    to_address = input("Enter recipient's address: ")

    if choice == "1":
        try:
            amount_btc = Decimal(input("Enter amount of BTC to send: "))
        except ValueError:
            print("Invalid amount! Please enter a valid number.")
            exit()

        send_btc(private_key, to_address, amount_btc)
    else:
        print("Invalid choice! Exiting...")
