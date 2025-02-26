import logging
import os
from datetime import datetime
from decimal import Decimal, getcontext
import requests

from flask import Blueprint, jsonify, request
from database import SessionLocal
from database.wallets import Wallets
from database.Address import Address
import config  # ایمپورت فایل تنظیمات دیتابیس

# تعیین دقت محاسبات اعشاری
getcontext().prec = 28

# ایجاد دایرکتوری Logs اگر وجود نداشته باشد
log_directory = "Logssssss"
if not os.path.exists(log_directory):
    os.makedirs(log_directory)

# ایجاد فایل لاگ با تایم‌استمپ
log_filename = os.path.join(log_directory, f"balance_log_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.log")

# تنظیم Logger
logger = logging.getLogger("balance_logger")
logger.setLevel(logging.INFO)  # تنظیم سطح لاگ

# جلوگیری از انتشار لاگ‌ها به سایر logger ها
logger.propagate = False

# بررسی و حذف `FileHandler` های قبلی (برای جلوگیری از ایجاد چندین هندلر)
if not logger.handlers:
    file_handler = logging.FileHandler(log_filename, encoding='utf-8')
    file_handler.setLevel(logging.INFO)

    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)

    log_format = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
    file_handler.setFormatter(log_format)
    console_handler.setFormatter(log_format)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

# ایجاد Blueprint
balance_bp = Blueprint('balance', __name__)

BLOCKCHAIN_SERVICE_URL = "http://localhost:4000/blockchain/batch"
REQUEST_TIMEOUT = 120  # seconds

@balance_bp.route('/balance', methods=['POST'])
def post_balance():
    try:
        # دریافت UserID از درخواست
        data = request.get_json()
        user_id = data.get('UserID')
        
        if not user_id:
            return jsonify({"error": "UserID is required"}), 400

        logger.info(f"Fetching balance for UserID: {user_id}")

        # دریافت آدرس‌های کاربر از دیتابیس
        with SessionLocal() as session:
            # پیدا کردن تمام کیف پول‌های کاربر
            wallets = session.query(Wallets).filter(Wallets.UserID == user_id).all()
            
            if not wallets:
                logger.warning(f"No wallets found for UserID: {user_id}")
                return jsonify({
                    "UserID": user_id,
                    "Tokens": {}
                })

            # جمع‌آوری تمام آدرس‌ها از تمام کیف پول‌ها
            address_requests = []
            for wallet in wallets:
                addresses = session.query(Address).filter(Address.WalletID == wallet.WalletID).all()
                for addr in addresses:
                    address_requests.append({
                        "public_address": addr.PublicAddress,
                        "blockchain_id": addr.BlockchainID
                    })

            if not address_requests:
                logger.warning(f"No addresses found for UserID: {user_id}")
                return jsonify({
                    "UserID": user_id,
                    "Tokens": {}
                })

            logger.info(f"Found {len(address_requests)} addresses for UserID: {user_id}")

        # ارسال درخواست به سرویس Node.js
        try:
            response = requests.post(
                BLOCKCHAIN_SERVICE_URL,
                json={"requests": address_requests},
                timeout=REQUEST_TIMEOUT
            )
            response.raise_for_status()
            blockchain_data = response.json()
            
            logger.debug(f"Blockchain service response: {blockchain_data}")

            # تجمیع تمام توکن‌ها از تمام آدرس‌ها
            all_tokens = {}
            for result in blockchain_data.get('results', []):
                tokens = result.get('tokens', {})
                for token_symbol, balance in tokens.items():
                    # اگر توکن قبلاً وجود دارد، مقدار جدید را اضافه کن
                    if token_symbol in all_tokens:
                        all_tokens[token_symbol] += balance
                    else:
                        all_tokens[token_symbol] = balance

            # حذف توکن‌هایی که موجودی صفر دارند
            non_zero_tokens = {k: v for k, v in all_tokens.items() if v > 0}

            if not non_zero_tokens:
                logger.info(f"No non-zero tokens found for UserID: {user_id}")
                return jsonify({
                    "UserID": user_id,
                    "Tokens": {}
                })

            return jsonify({
                "UserID": user_id,
                "Tokens": non_zero_tokens
            })

        except requests.exceptions.RequestException as e:
            logger.error(f"Error calling blockchain service: {e}")
            return jsonify({
                "error": "Failed to fetch blockchain data",
                "details": str(e)
            }), 500

    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        return jsonify({
            "error": "Internal server error",
            "details": str(e)
        }), 500