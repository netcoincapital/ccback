import logging
import json
from flask import Blueprint, jsonify, request
from database import SessionLocal, Currencies
from services import CurrencyPriceService

logger = logging.getLogger(__name__)

fiat_symbols = {
    "USD": "$", "CAD": "CA$", "AUD": "AU$", "GBP": "£", "EUR": "€",
    "KWD": "KD", "TRY": "₺", "IRR": "﷼", "SAR": "﷼", "CNY": "¥",
    "KRW": "₩", "JPY": "¥", "INR": "₹", "RUB": "₽", "IQD": "ع.د",
    "TND": "د.ت", "BHD": "ب.د"
}

def dynamic_decimal_format(price_value: float) -> str:
    if price_value >= 1:
        return f"{price_value:,.2f}"
    elif price_value >= 0.01:
        return f"{price_value:,.4f}"
    elif price_value >= 0.0001:
        return f"{price_value:,.6f}"
    else:
        return f"{price_value:,.8f}"

CUpdate_bp = Blueprint('CUpdate_bp', __name__)

@CUpdate_bp.route('/prices', methods=['POST'])
def get_currency_price():
    logger.info("Received a request to fetch currency prices.")

    db_session = SessionLocal()
    try:
        data = request.json
        if not data or "UserID" not in data or "CurrencyID" not in data:
            logger.error("UserID or CurrencyID not provided.")
            return jsonify({"success": False, "message": "UserID and CurrencyID are required."}), 400

        user_id = data["UserID"]
        currency_ids = data["CurrencyID"]
        if isinstance(currency_ids, str):
            currency_ids = [currency_ids]
        if not isinstance(currency_ids, list):
            return jsonify({"success": False, "message": "CurrencyID must be list or string."}), 400

        # گرفتن فیات‌ها (ارزهای رایج)
        fiat_currencies_input = data.get("FiatCurrencies", None)
        if fiat_currencies_input is None:
            fiat_currencies = list(fiat_symbols.keys())
        else:
            if isinstance(fiat_currencies_input, str):
                fiat_currencies_input = [fiat_currencies_input]
            if not isinstance(fiat_currencies_input, list):
                return jsonify({"success": False, "message": "FiatCurrencies must be list or string."}), 400
            filtered_fiats = [f for f in fiat_currencies_input if f in fiat_symbols]
            fiat_currencies = filtered_fiats if filtered_fiats else list(fiat_symbols.keys())

        logger.info(f"Final fiat currencies to fetch: {fiat_currencies}")

        # کوئری گرفتن ارزهای درخواستی
        currencies = db_session.query(Currencies).filter(Currencies.Symbol.in_(currency_ids)).all()
        if not currencies:
            return jsonify({"success": False, "message": "No currencies found."}), 404

        symbols = [currency.Symbol for currency in currencies]

        currency_service = CurrencyPriceService()
        final_prices = {symbol: {} for symbol in symbols}

        for fiat in fiat_currencies:
            prices_response = currency_service.get_latest_prices(symbols, fiat)
            changes_response = currency_service.get_24h_changes(symbols, fiat)

            # --- prices_response ---
            if isinstance(prices_response, str):
                try:
                    # اگر JSON باشد دیکدش می‌کنیم
                    prices_response = json.loads(prices_response)
                except json.JSONDecodeError:
                    # اگر JSON نبود، دیکشنری خطایی درست می‌کنیم تا با .get(...) سازگار باشد
                    prices_response = {
                        "status": "error",
                        "message": prices_response
                    }

            # --- changes_response ---
            if isinstance(changes_response, str):
                try:
                    changes_response = json.loads(changes_response)
                except json.JSONDecodeError:
                    changes_response = {
                        "status": "error",
                        "message": changes_response
                    }

            # در این مرحله باید حتماً دیکشنری باشند
            if not isinstance(prices_response, dict):
                logger.error(f"prices_response is not a dict: {type(prices_response)}")
                return jsonify({"success": False, "message": "Invalid response format from get_latest_prices."}), 500

            if not isinstance(changes_response, dict):
                logger.error(f"changes_response is not a dict: {type(changes_response)}")
                return jsonify({"success": False, "message": "Invalid response format from get_24h_changes."}), 500

            # اگر دارای فیلد status با مقدار error است، یعنی خطای سمت سرویس
            if prices_response.get("status") == "error":
                return jsonify({"success": False, "message": prices_response.get("message", "Unknown error.")}), 500

            if changes_response.get("status") == "error":
                return jsonify({"success": False, "message": changes_response.get("message", "Unknown error.")}), 500

            # ایجاد ساختار خروجی نهایی
            for symbol in symbols:
                price_value = prices_response.get(symbol)
                change_value = changes_response.get(symbol)

                if isinstance(price_value, (int, float)) and price_value >= 0:
                    numeric_str = dynamic_decimal_format(price_value)

                    if isinstance(change_value, (int, float)):
                        change_sign = "+" if change_value > 0 else ""
                        change_str = f"{change_sign}{change_value:.2f}%"
                    else:
                        change_str = "N/A"

                    final_prices[symbol][fiat] = {
                        "price": numeric_str,
                        "change_24h": change_str
                    }
                else:
                    final_prices[symbol][fiat] = None

        return jsonify({"success": True, "prices": final_prices}), 200

    except Exception as e:
        logger.exception("An exception occurred while fetching currency prices.")
        return jsonify({"success": False, "message": str(e)}), 500

    finally:
        db_session.close()