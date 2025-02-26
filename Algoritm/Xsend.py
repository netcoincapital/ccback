import re
import getpass
from decimal import Decimal

# کتابخانه اصلی برای کار با XRP Ledger
import xrpl
from xrpl.clients import JsonRpcClient
from xrpl.account import get_balance, get_account_root
from xrpl.ledger import get_latest_validated_ledger_sequence
from xrpl.models.requests import ServerInfo
from xrpl.models.transactions import Payment
from xrpl.transaction import autofill, sign, submit_and_wait
from xrpl.wallet import Wallet


# آدرس پیش‌فرض برای اتصال به شبکهٔ اصلی (Mainnet)
XRP_MAINNET_URL = "https://s2.ripple.com:51234"

# ساخت کلاینت JsonRpc برای اتصال به XRP Ledger
client = JsonRpcClient(XRP_MAINNET_URL)


def get_transaction_url_xrp(tx_hash):
    """
    برمی‌گرداندن آدرس تراکنش در مرورگر لجر XRP.
    نمونه: https://livenet.xrpl.org/transactions/{tx_hash}
    """
    return f"https://livenet.xrpl.org/transactions/{tx_hash}"


def is_valid_private_key_xrp(key):
    """
    بررسی ساده برای اینکه کلید خصوصی در قالب یک Seed/Secret استاندارد XRPL باشد.
    این تابع بسیار ساده است و صرفاً یک الگوی اولیه را چک می‌کند.
    معمولاً سیکرت‌های XRPL با 's' شروع شده و بین 16 تا 30 کاراکتر (یا بیشتر) دارند.
    """
    return bool(re.fullmatch(r"s[1-9A-HJ-NP-Za-km-z]{15,}", key))


def get_exact_fee_in_drops():
    """
    دریافت مقدار دقیق فی در شبکهٔ XRP به صورت واحد قطره (Drops).
    این فی بر اساس base_fee_xrp و load_factor از سرور محاسبه می‌شود.
    مقدار بازگشتی یک عدد صحیح است که بیانگر Drops می‌باشد.
    هر 1 XRP = 1,000,000 Drops
    """
    try:
        info = client.request(ServerInfo()).result["info"]
        # base_fee_xrp: فی پایه بر حسب XRP
        base_fee_xrp = float(info["validated_ledger"]["base_fee_xrp"])
        # load_factor: ضریب شلوغی شبکه
        load_factor = float(info["load_factor"])
        exact_fee_xrp = base_fee_xrp * load_factor
        exact_fee_drops = int(exact_fee_xrp * 1_000_000)
        return exact_fee_drops
    except Exception:
        # در صورت بروز خطا می‌توان مقدار پیش‌فرضی برگرداند یا تراکنش را متوقف کرد
        return None


def send_xrp(private_key, to_address, amount):
    """
    ارسال XRP (ارز اصلی شبکه) از یک آدرس به آدرس دیگر.
    - private_key: کلید خصوصی (Seed) فرستنده
    - to_address: آدرس مقصد (Classic Address)
    - amount: مقدار XRP برای ارسال (بر حسب XRP، نه قطره)
    """
    try:
        if not is_valid_private_key_xrp(private_key):
            print("Invalid XRP private key (seed) format!")
            return None

        # ساخت Wallet موقت با sequence=0
        temp_wallet = Wallet(seed=private_key, sequence=0)

        # دریافت اطلاعات حساب (account_data) فرستنده
        try:
            account_data = get_account_root(temp_wallet.classic_address, client)
            sequence_num = account_data["Sequence"]
        except Exception:
            print("Cannot fetch sequence from the account. Make sure the account is valid and funded.")
            return None

        # ساخت کیف پول با sequence درست
        wallet = Wallet(seed=private_key, sequence=sequence_num)

        # تبدیل واحد از XRP به Drops
        amount_in_drops = int(Decimal(amount) * 1_000_000)

        # بالانس فعلی فرستنده (بر حسب XRP)
        sender_balance_drops = get_balance(wallet.classic_address, client)
        sender_balance_xrp = Decimal(sender_balance_drops) / Decimal(1_000_000)

        # محاسبهٔ فی دقیق از سرور
        fee_in_drops = get_exact_fee_in_drops()
        if fee_in_drops is None:
            print("Could not fetch exact fee from network. Aborting transaction.")
            return None

        fee_in_xrp = Decimal(fee_in_drops) / Decimal(1_000_000)
        balance_after_tx = sender_balance_xrp - Decimal(amount) - fee_in_xrp

        print(f"\n📌 **Transaction Details (Before Sending):**")
        print(f"   🔹 Sender Address: {wallet.classic_address}")
        print(f"   🔹 Recipient Address: {to_address}")
        print(f"   🔹 Amount: {amount} XRP")
        print(f"   🔹 Sender Balance (Before): {sender_balance_xrp} XRP")
        print(f"   🔹 Estimated Fee: {fee_in_xrp} XRP")
        print(f"   🔹 Sender Balance (After): {balance_after_tx} XRP\n")

        if balance_after_tx < 0:
            print("❌ Warning: Insufficient balance for this transaction!")
            return None

        confirm = input("✅ Confirm transaction? (yes/no): ").strip().lower()
        if confirm != "yes":
            print("🚫 Transaction canceled.")
            return None

        # ساخت Payment با فی (Drops)، sequence و ...
        # (در رویکرد جدید نیازی نیست حتماً fee و sequence را به صورت دستی ست کنیم؛
        #  اما در این مثال، برای کنترل دقیق Fee این کار را انجام می‌دهیم.)
        payment_tx = Payment(
            account=wallet.classic_address,
            amount=str(amount_in_drops),
            destination=to_address,
            sequence=sequence_num,
            fee=str(fee_in_drops)
        )

        # با این حال، بهتر است از autofill استفاده کنیم تا فیلدهایی مانند last_ledger_sequence پر شود
        autofilled_tx = autofill(payment_tx, client)

        # امضای تراکنش
        signed_tx = sign(autofilled_tx, wallet)

        print("🚀 Sending transaction...")
        # ارسال و انتظار نتیجه (submit_and_wait)
        try:
            tx_response = submit_and_wait(signed_tx, client)
        except Exception as e:
            print(f"❌ Error while submitting transaction: {e}")
            return None

        tx_id = signed_tx.get_hash()
        print(f"\n✅ **Transaction Sent!**")
        print(f"   🔹 Transaction Hash: {tx_id}")
        print(f"   🔹 Transaction URL: {get_transaction_url_xrp(tx_id)}")

        # نتیجهٔ نهایی از متای تراکنش
        result_code = tx_response.result.get("meta", {}).get("TransactionResult", "N/A")
        status = "✅ Success" if result_code == "tesSUCCESS" else f"❌ Failed: {result_code}"

        # هزینه‌ی واقعی تراکنش
        actual_fee_drops = tx_response.result.get("Fee", 0)
        actual_fee_xrp = Decimal(actual_fee_drops) / Decimal(1_000_000)

        # بالانس جدید فرستنده
        new_balance_drops = get_balance(wallet.classic_address, client)
        new_balance_xrp = Decimal(new_balance_drops) / Decimal(1_000_000)

        print(f"   🔹 Actual Fee: {actual_fee_xrp} XRP")
        print(f"   🔹 Sender Balance (After): {new_balance_xrp} XRP")
        print(f"   🔹 Result Code: {result_code}")
        print(f"   🔹 Status: {status}\n")

        return tx_id

    except Exception as e:
        print(f"❌ An error occurred: {e}")


def send_xrp_iou(private_key, to_address, amount, currency, issuer, destination_tag=None):
    """
    ارسال توکن (IOU) روی شبکه‌ی XRP (مشابه TRC20 در Tron).
    پارامترها:
      - private_key: Seed فرستنده
      - to_address: آدرس کلاسیک مقصد
      - amount: مقدار توکن برای ارسال
      - currency: نام یا کد توکن (مثلاً "USD" یا "TOKEN")
      - issuer: آدرس کلاسیک صادرکننده توکن
      - destination_tag: (اختیاری) تگ مقصد برای آدرس مقصد

    توجه: برای انتقال توکن در XRPL باید مقصد و فرستنده هر دو trustline مناسب داشته باشند.
    """
    try:
        if not is_valid_private_key_xrp(private_key):
            print("Invalid XRP private key (seed) format!")
            return None

        temp_wallet = Wallet(seed=private_key, sequence=0)
        try:
            account_data = get_account_root(temp_wallet.classic_address, client)
            sequence_num = account_data["Sequence"]
        except Exception:
            print("Cannot fetch sequence from the account. Make sure the account is valid and funded.")
            return None

        wallet = Wallet(seed=private_key, sequence=sequence_num)

        # محاسبهٔ فی دقیق
        fee_in_drops = get_exact_fee_in_drops()
        if fee_in_drops is None:
            print("Could not fetch exact fee from network. Aborting transaction.")
            return None

        # در XRPL برای پرداخت توکن در فیلد "amount" از یک آبجکت JSON استفاده می‌شود:
        iou_amount = {
            "currency": currency,
            "value": str(amount),
            "issuer": issuer
        }

        payment_fields = {
            "account": wallet.classic_address,
            "amount": iou_amount,
            "destination": to_address,
            "sequence": sequence_num,
            "fee": str(fee_in_drops),
        }

        if destination_tag is not None:
            payment_fields["destination_tag"] = int(destination_tag)

        payment_tx = Payment(**payment_fields)

        sender_balance_drops = get_balance(wallet.classic_address, client)
        sender_balance_xrp = Decimal(sender_balance_drops) / Decimal(1_000_000)
        fee_in_xrp = Decimal(fee_in_drops) / Decimal(1_000_000)

        print(f"\n📌 **IOU Transaction Details (Before Sending):**")
        print(f"   🔹 Sender Address: {wallet.classic_address}")
        print(f"   🔹 Recipient Address: {to_address}")
        print(f"   🔹 IOU Amount: {amount} {currency}")
        print(f"   🔹 Issuer: {issuer}")
        if destination_tag is not None:
            print(f"   🔹 Destination Tag: {destination_tag}")
        print(f"   🔹 Sender XRP Balance (Before): {sender_balance_xrp} XRP")
        print(f"   🔹 Estimated Fee: {fee_in_xrp} XRP\n")

        confirm = input("✅ Confirm IOU transaction? (yes/no): ").strip().lower()
        if confirm != "yes":
            print("🚫 Transaction canceled.")
            return None

        # autofill و sign
        autofilled_tx = autofill(payment_tx, client)
        signed_tx = sign(autofilled_tx, wallet)

        print("🚀 Sending IOU transaction...")
        try:
            tx_response = submit_and_wait(signed_tx, client)
        except Exception as e:
            print(f"❌ Error while submitting IOU transaction: {e}")
            return None

        tx_id = signed_tx.get_hash()
        print(f"\n✅ **IOU Transaction Sent!**")
        print(f"   🔹 Transaction Hash: {tx_id}")
        print(f"   🔹 Transaction URL: {get_transaction_url_xrp(tx_id)}")

        result_code = tx_response.result.get("meta", {}).get("TransactionResult", "N/A")
        status = "✅ Success" if result_code == "tesSUCCESS" else f"❌ Failed: {result_code}"

        # هزینه‌ی واقعی تراکنش
        actual_fee_drops = tx_response.result.get("Fee", 0)
        actual_fee_xrp = Decimal(actual_fee_drops) / Decimal(1_000_000)

        # بالانس جدید فرستنده
        new_balance_drops = get_balance(wallet.classic_address, client)
        new_balance_xrp = Decimal(new_balance_drops) / Decimal(1_000_000)

        print(f"   🔹 Actual Fee: {actual_fee_xrp} XRP")
        print(f"   🔹 Sender Balance (After): {new_balance_xrp} XRP")
        print(f"   🔹 Result Code: {result_code}")
        print(f"   🔹 Status: {status}\n")

        return tx_id

    except Exception as e:
        print(f"❌ An error occurred in IOU transfer: {e}")


if __name__ == "__main__":
    print("Select Transaction Type:\n1. Send XRP\n2. Send IOU (Custom Token)")
    choice = input("Enter 1 for XRP, 2 for IOU: ").strip()

    private_key = getpass.getpass("Enter your XRP seed (secret): ")
    to_address = input("Enter recipient's XRP address (classic): ")

    if choice == "1":
        try:
            amount = Decimal(input("Enter amount of XRP to send: "))
        except ValueError:
            print("Invalid amount! Please enter a number.")
            exit()
        send_xrp(private_key, to_address, amount)

    elif choice == "2":
        currency = input("Enter currency code (e.g., USD, TOKEN): ").strip().upper()
        issuer = input("Enter issuer address of the token: ").strip()
        amount = input("Enter amount of the token to send: ").strip()
        destination_tag_input = input("Enter destination tag (if any, otherwise leave blank): ").strip()
        destination_tag = destination_tag_input if destination_tag_input else None
        try:
            Decimal(amount)  # صرفاً برای اطمینان از قابل تبدیل بودن
        except:
            print("Invalid token amount!")
            exit()
        send_xrp_iou(private_key, to_address, Decimal(amount), currency, issuer, destination_tag)

    else:
        print("Invalid choice! Exiting...")
