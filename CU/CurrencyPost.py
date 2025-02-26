import logging
from flask import Blueprint, jsonify, request
from database import SessionLocal, Currencies

logger = logging.getLogger(__name__)

# تعریف Blueprint برای نمایش تمامی کارنسی‌ها
CPost_bp = Blueprint('CPost_bp', __name__)

@CPost_bp.route('/all-currencies', methods=['GET'])
def get_all_currencies():
    """
    این اندپوینت تمام کارنسی‌های موجود در دیتابیس را برگردانده و نمایش می‌دهد.
    """
    logger.info("Attempting to fetch all currencies from the database.")

    # تعریف یک مپ برای تبدیل BlockchainID به BlockchainName
    blockchain_map = {
        4: "Bitcoin",
        1: "Ethereum",
        2: "Tron",
        3: "Binance",
        5: "Polygon",
        11: "XRP",
        12: "Solana",
        6: "Arbitrum",
        13: "Polkadot",
        14: "Avalanche"
    }

    # ایجاد Session برای ارتباط با دیتابیس
    db_session = SessionLocal()

    try:
        # دریافت تمام رکوردهای Currencies از دیتابیس
        currencies = db_session.query(Currencies).all()
        
        if not currencies:
            logger.warning("No currencies found in the database.")
            return jsonify({"success": False, "message": "No currencies found."}), 404

        # تبدیل اطلاعات کارنسی‌ها به قالب JSON
        data = []
        for currency in currencies:
            # جایگزینی BlockchainID با BlockchainName
            blockchain_name = blockchain_map.get(currency.BlockchainID, "Unknown")
            
            data.append({
                "CurrencyID": currency.CurrencyID,
                "CurrencyName": currency.CurrencyName,
                "Icon": currency.Icon,
                "Symbol": currency.Symbol,
                "BlockchainName": blockchain_name,  # استفاده از نام به‌جای آی‌دی
                "DecimalPlaces": currency.DecimalPlaces,
                "IsToken": currency.IsToken,
                "SmartContractAddress": currency.SmartContractAddress,
            })

        logger.info("All currencies fetched successfully.")
        return jsonify({"success": True, "currencies": data}), 200
    except Exception as e:
        logger.exception("An exception occurred while fetching all currencies.")
        return jsonify({"success": False, "message": str(e)}), 500
    finally:
        # بستن سشن دیتابیس
        db_session.close()
