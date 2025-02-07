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
log_directory = "Logs"
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
    # ایجاد FileHandler برای ثبت لاگ در فایل
    file_handler = logging.FileHandler(log_filename, encoding='utf-8')
    file_handler.setLevel(logging.INFO)

    # ایجاد StreamHandler برای نمایش لاگ در کنسول
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)

    # تنظیم فرمت لاگ‌ها
    log_format = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
    file_handler.setFormatter(log_format)
    console_handler.setFormatter(log_format)

    # اضافه کردن هندلرها به logger
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

# ایجاد Blueprint
balance_bp = Blueprint('balance', __name__)

def get_balance_for_user(user_id):
    """
    این تابع تمام آدرس‌های متعلق به کاربر را پیدا می‌کند و آن‌ها را در قالب
    یک Batch Request به سرور Node.js ارسال می‌نماید تا تنها توکن‌ها را برگرداند.
    """

    logger.info(f"Fetching balance for user {user_id}")

    # استفاده از Context Manager برای مدیریت Session
    with SessionLocal() as session:
        wallets = session.query(Wallets).filter(Wallets.UserID == user_id).all()
        if not wallets:
            logger.warning(f"No wallets found for user {user_id}")
            return {"UserID": user_id, "Tokens": {}}

        address_list = []
        for w in wallets:
            addresses = session.query(Address).filter(Address.WalletID == w.WalletID).all()
            for addr in addresses:
                address_list.append({
                    "public_address": addr.PublicAddress,
                    "blockchain_id": addr.BlockchainID
                })

        if not address_list:
            logger.warning(f"User {user_id} has wallets but no addresses")
            return {"UserID": user_id, "Tokens": {}}

    payload = {"requests": address_list}

    try:
        response = requests.post(
            "http://localhost:3000/blockchain/batch",
            json=payload,
            timeout=10
        )
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed batch request for user {user_id}: {e}")
        return {"UserID": user_id, "Tokens": {}}

    try:
        data = response.json()
    except Exception as e:
        logger.error(f"Error parsing JSON for user {user_id}: {e}")
        return {"UserID": user_id, "Tokens": {}}

    results_array = data.get("results", [])
    tokens_info = {}

    for item in results_array:
        tokens_dict = item.get("tokens", {})
        for symbol_or_contract, val_int in tokens_dict.items():
            val_dec = Decimal(val_int)
            if symbol_or_contract not in tokens_info:
                tokens_info[symbol_or_contract] = Decimal('0')
            tokens_info[symbol_or_contract] += val_dec

    if not tokens_info:
        logger.warning(f"User {user_id} has addresses but all token balances are zero")

    logger.info(f"Successfully fetched balance for user {user_id}: {tokens_info}")
    
    return {
        "UserID": user_id,
        "Tokens": {k: str(v) for k, v in tokens_info.items()}
    }

@balance_bp.route('/balance', methods=['POST'])
def post_balance():
    """
    متد اصلی که با فراخوانی POST /balance و ارسال:
    {
       "UserID": "<uuid یا id کاربر>"
    }
    بالانس توکن‌های کاربر را برمی‌گرداند.
    """
    try:
        data = request.get_json()
        if not data or "UserID" not in data:
            return jsonify({"error": "UserID is required"}), 400

        user_id = data["UserID"]
        logger.info(f"Received balance request for user {user_id}")

        result = get_balance_for_user(user_id)

        if not result["Tokens"]:
            logger.warning(f"No wallets/addresses or no tokens found for user {user_id}")
            return jsonify({"error": "No wallets/addresses or no tokens found for this user"}), 404

        logger.info(f"Returning balance data for user {user_id}")
        return jsonify({"Tokens": result["Tokens"]}), 200

    except Exception as e:
        logger.error(f"Error processing balance request: {e}")
        return jsonify({"error": str(e)}), 500
