import logging
from flask import Blueprint, jsonify, request
from database import SessionLocal, Currencies
from services import CurrencyPriceService

logger = logging.getLogger(__name__)

# دیکشنری نگهداری نماد (Symbol) ارزهای فیات (فقط درون کد قابل دسترس است)
fiat_symbols = {
    "USD": "$",    # دلار آمریکا
    "CAD": "CA$",  # دلار کانادا
    "AUD": "AU$",  # دلار استرالیا
    "GBP": "£",    # پوند انگلیس
    "EUR": "€",    # یورو
    "KWD": "KD",   # دینار کویت
    "TRY": "₺",    # لیر ترکیه
    "IRR": "﷼",    # ریال ایران
    "SAR": "﷼",    # ریال عربستان
    "CNY": "¥",    # یوآن چین
    "KRW": "₩",    # وون کره جنوبی
    "JPY": "¥",    # ین ژاپن
    "INR": "₹",    # روپیه هند
    "RUB": "₽",    # روبل روسیه
    "IQD": "ع.د",  # دینار عراق
    "TND": "د.ت",  # دینار تونس
    "BHD": "ب.د"   # دینار بحرین
}

def dynamic_decimal_format(price_value: float) -> str:
    """
    فرمت‌دهی پویا برای نمایش تعداد اعشار قیمت:
    - اگر قیمت >= 1 باشد: دو رقم اعشار (مثال: 3,233.88)
    - اگر 1 > قیمت >= 0.01 باشد: چهار رقم اعشار (مثال: 0.1234)
    - اگر 0.01 > قیمت >= 0.0001 باشد: شش رقم اعشار (مثال: 0.000123)
    - اگر قیمت < 0.0001 باشد: هشت رقم اعشار (مثال: 0.00000012)
    """
    if price_value >= 1:
        return f"{price_value:,.2f}"
    elif price_value >= 0.01:
        return f"{price_value:,.4f}"
    elif price_value >= 0.0001:
        return f"{price_value:,.6f}"
    else:
        return f"{price_value:,.8f}"

# تعریف Blueprint
CUpdate_bp = Blueprint('CUpdate_bp', __name__)

@CUpdate_bp.route('/prices', methods=['POST'])
def get_currency_price():
    """
    این اندپوینت با دریافت UserID و مجموعه‌ای از Symbolها (در فیلد CurrencyID به‌صورت آرایه)،
    قیمت هر Symbol را در واحدهای پولی مورد نظر که در فیلد FiatCurrencies به‌صورت آرایه فرستاده می‌شود،
    برمی‌گرداند. در صورت عدم ارسال FiatCurrencies، از همه واحدهای موجود در fiat_symbols استفاده می‌کنیم.

    بدنه درخواست باید حداقل شامل فیلدهای زیر باشد:
    {
      "UserID": "xxxxxx",
      "CurrencyID": ["ETH", "SHIB"],
      "FiatCurrencies": ["USD", "EUR", "IRR"]   // اختیاری: در صورت حذف، تمام فیات‌ها برگردانده می‌شوند
    }
    """

    logger.info("Received a request to fetch currency prices based on UserID and CurrencyID list.")

    # ایجاد Session برای ارتباط با دیتابیس
    db_session = SessionLocal()

    try:
        # دریافت داده‌های ورودی از بدنه درخواست
        data = request.json

        # بررسی موجود بودن فیلدهای ضروری
        if not data or "UserID" not in data or "CurrencyID" not in data:
            logger.error("UserID or CurrencyID not provided in the request body.")
            return jsonify({"success": False, "message": "UserID and CurrencyID are required."}), 400

        user_id = data["UserID"]
        currency_ids = data["CurrencyID"]  # ممکن است لیست یا رشته باشد
        logger.info(f"Fetching price for these symbols {currency_ids}, requested by UserID: {user_id}")

        # اگر کاربر یک رشته تکی ارسال کرده باشد (مثلاً "ETH")، آن را به لیست تبدیل می‌کنیم
        if isinstance(currency_ids, str):
            currency_ids = [currency_ids]

        if not isinstance(currency_ids, list):
            logger.error("CurrencyID must be a list of symbols or a single string symbol.")
            return jsonify({"success": False, "message": "CurrencyID must be list or string."}), 400

        # اگر در ورودی "FiatCurrencies" نیامده باشد، از کل لیست پشتیبانی شده استفاده می‌کنیم
        fiat_currencies_input = data.get("FiatCurrencies", None)
        if fiat_currencies_input is None:
            # یعنی کاربر هیچ لیستی از فیات‌ها ارسال نکرده است
            fiat_currencies = list(fiat_symbols.keys())
        else:
            # اگر فقط یک رشته ارسال کرده بود ("USD")، به لیست تبدیل می‌کنیم
            if isinstance(fiat_currencies_input, str):
                fiat_currencies_input = [fiat_currencies_input]

            if not isinstance(fiat_currencies_input, list):
                logger.error("FiatCurrencies must be a list or string if provided.")
                return jsonify({"success": False, "message": "FiatCurrencies must be list or string."}), 400

            # از ورودی، فقط آن ارزهایی را می‌پذیریم که در دیکشنری fiat_symbols تعریف شده باشند
            filtered_fiats = [f for f in fiat_currencies_input if f in fiat_symbols]
            if not filtered_fiats:
                # اگر هیچ‌کدام از فیات‌های ورودی معتبر نبودند، می‌توانیم خطا بدهیم یا همه را برگردانیم
                logger.warning("No valid fiat currencies were provided. Using all by default.")
                fiat_currencies = list(fiat_symbols.keys())
            else:
                fiat_currencies = filtered_fiats

        logger.info(f"Final fiat currencies to fetch: {fiat_currencies}")

        # واکشی تمام رکوردهایی که Symbol در لیست currency_ids است
        currencies = db_session.query(Currencies).filter(Currencies.Symbol.in_(currency_ids)).all()

        if not currencies:
            logger.warning(f"No currency found with the given symbols: {currency_ids}")
            return jsonify({"success": False, "message": "No currencies found for given symbols."}), 404

        # استخراج سمبل‌ها از دیتابیس
        symbols = [currency.Symbol for currency in currencies]
        logger.info(f"Fetched these symbols from database: {symbols}")

        # ایجاد یک نمونه از سرویس قیمت ارز
        currency_service = CurrencyPriceService()

        # ساخت دیکشنری نهایی برای نگهداری قیمت هر ارز در هر واحد پولی
        final_prices = {}
        for symbol in symbols:
            final_prices[symbol] = {}

        # برای هر واحد پولی در fiat_currencies، قیمت همه سمبل‌ها را یکجا می‌گیریم
        for fiat in fiat_currencies:
            prices_response = currency_service.get_latest_prices(symbols, fiat)

            # بررسی ارور در پاسخ دریافتی از سرویس (مثلاً CoinMarketCap)
            if "status" in prices_response and prices_response["status"] == "error":
                error_msg = prices_response.get("message", "Unknown error occurred.")
                logger.error(f"Error occurred while fetching prices for fiat {fiat}: {error_msg}")
                return jsonify({"success": False, "message": error_msg}), 500

            # برای هر سمبل، قیمت را در دیکشنری final_prices قرار می‌دهیم
            for symbol in symbols:
                price_value = prices_response.get(symbol)
                if isinstance(price_value, (int, float)) and price_value >= 0:
                    numeric_str = dynamic_decimal_format(price_value)
                    # فقط قیمت + کد ارز
                    final_prices[symbol][fiat] = f"{numeric_str}"
                else:
                    final_prices[symbol][fiat] = None

        # برگرداندن پاسخ نهایی به صورت JSON
        return jsonify({
            "success": True,
            "prices": final_prices
        }), 200

    except Exception as e:
        logger.exception("An exception occurred while fetching currency prices.")
        return jsonify({"success": False, "message": str(e)}), 500

    finally:
        # بستن سشن دیتابیس
        db_session.close()