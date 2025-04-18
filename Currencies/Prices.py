import logging
import json
import requests
import time
from flask import Blueprint, jsonify, request
from security.validators import InputValidator, SecurityUtils, ValidationError
from utils.error_handlers import handle_api_errors
from utils.logging_config import get_logger
from schemas import (
    CurrencyPriceRequest,
    CurrencyPriceResponse,
    CurrencyUpdateResponse,
    ErrorResponse
)
from sqlalchemy.orm import Session
from database import engine, Currencies
from database.prices import Price
from Currencies.price_service import PriceDbService
from Currencies.api_key_manager import ApiKeyManager
from Currencies.currency_price_service import dynamic_decimal_format, fiat_symbols

# Configure logging
logger = get_logger(__file__)
logger.info("Initializing currency update module")

# تعریف CurrencyPriceService کامل حذف می‌شود

CUpdate_bp = Blueprint('currency_update', __name__)

@CUpdate_bp.route('/prices', methods=['POST'])
@SecurityUtils.rate_limit(requests=100, window=60)
@handle_api_errors
def get_currency_price():
    """
    Get currency prices from local database
    ---
    tags:
      - Currencies
    requestBody:
      required: true
      content:
        application/json:
          schema:
            type: object
            properties:
              Symbol:
                type: array
                items:
                  type: string
              FiatCurrencies:
                type: array
                items:
                  type: string
    responses:
      200:
        description: Currency prices retrieved successfully
      400:
        description: Invalid input data
      429:
        description: Rate limit exceeded
      500:
        description: Server error
    """
    try:
        # Debug response is now removed
        
        data = request.get_json()
        if not data:
            raise ValidationError("Invalid request data")

        # پشتیبانی از هر دو فرمت Symbol و currencyname
        symbols = data.get('Symbol', data.get('currencyname', data.get('CurrencyID', [])))
        if isinstance(symbols, str):
            symbols = [symbols]
        if not isinstance(symbols, list):
            raise ValidationError("Symbol/currencyname must be list or string")

        if not symbols:
            raise ValidationError("At least one Symbol/currencyname is required")

        # تغییر الگوی اعتبار سنجی برای پشتیبانی از نام‌های کامل ارز (مثل Ethereum)
        validated_symbols = [
            InputValidator.validate_string(
                symbol,
                "Symbol/currencyname",
                pattern=r'^[A-Za-z0-9 ]+$'  # اجازه فاصله برای currencyname مثل Bitcoin Cash
            ) for symbol in symbols
        ]

        # Validate FiatCurrencies
        fiat_currencies = data.get('FiatCurrencies', ["USD"])
        if isinstance(fiat_currencies, str):
            fiat_currencies = [fiat_currencies]
        if not isinstance(fiat_currencies, list):
            raise ValidationError("FiatCurrencies must be list or string")
        
        if not fiat_currencies:
            fiat_currencies = ["USD"]
            
        validated_fiats = [
            InputValidator.validate_string(
                fiat,
                "FiatCurrency",
                pattern=r'^[A-Z]{3}$'
            ) for fiat in fiat_currencies
        ]

        # تبدیل Symbol یا currencyname به CurrencyID با استفاده از دیتابیس
        logger.info(f"Converting symbols/currencynames to currency IDs: {validated_symbols}")
        currency_ids = []
        symbol_to_id_map = {}  # برای نگاشت برگشتی نتایج
        id_to_symbol_map = {}  # نگاشت CurrencyID به Symbol

        session = Session(bind=engine)
        try:
            # بررسی Symbol
            symbol_matches = session.query(Currencies).filter(
                Currencies.Symbol.in_(validated_symbols)
            ).all()
            
            # بررسی CurrencyName (برای پشتیبانی از ورودی currencyname)
            name_matches = session.query(Currencies).filter(
                Currencies.CurrencyName.in_(validated_symbols)
            ).all()
            
            # بررسی CurrencyID (برای پشتیبانی از ورودی CurrencyID)
            id_matches = session.query(Currencies).filter(
                Currencies.CurrencyID.in_(validated_symbols)
            ).all()
            
            # لاگ کردن برای بررسی نتایج
            logger.debug(f"Symbol matches: {[c.Symbol for c in symbol_matches]}")
            logger.debug(f"Name matches: {[c.CurrencyName for c in name_matches]}")
            logger.debug(f"ID matches: {[c.CurrencyID for c in id_matches]}")
            
            # اضافه کردن موارد پیدا شده به لیست نهایی
            for currency in symbol_matches:
                # ذخیره CurrencyID در هر دو حالت رشته‌ای و اصلی
                currency_ids.append(currency.CurrencyID)
                symbol_to_id_map[currency.Symbol] = currency.CurrencyID
                # برای نگاشت برگشتی، همیشه از رشته استفاده می‌کنیم
                id_to_symbol_map[currency.CurrencyID] = currency.Symbol
                # برای اطمینان، رشته‌ای را هم اضافه می‌کنیم
                id_to_symbol_map[str(currency.CurrencyID)] = currency.Symbol
                logger.debug(f"Mapped Symbol {currency.Symbol} to CurrencyID {currency.CurrencyID}")
            
            # اضافه کردن تطابق‌های CurrencyName
            for currency in name_matches:
                if currency.CurrencyID not in currency_ids:  # جلوگیری از تکرار
                    currency_ids.append(currency.CurrencyID)
                    symbol_to_id_map[currency.CurrencyName] = currency.CurrencyID
                    id_to_symbol_map[currency.CurrencyID] = currency.Symbol
                    id_to_symbol_map[str(currency.CurrencyID)] = currency.Symbol
                    logger.debug(f"Mapped CurrencyName {currency.CurrencyName} to CurrencyID {currency.CurrencyID}")
                
            for currency in id_matches:
                if currency.CurrencyID not in currency_ids:  # جلوگیری از تکرار
                    currency_ids.append(currency.CurrencyID)
                    symbol_to_id_map[currency.CurrencyID] = currency.CurrencyID
                    # اینجا از Symbol واقعی استفاده می‌کنیم
                    id_to_symbol_map[currency.CurrencyID] = currency.Symbol
                    # برای اطمینان، رشته‌ای را هم اضافه می‌کنیم
                    id_to_symbol_map[str(currency.CurrencyID)] = currency.Symbol
                    logger.debug(f"Mapped CurrencyID {currency.CurrencyID} to Symbol {currency.Symbol}")
            
        finally:
            session.close()
            
        if not currency_ids:
            raise ValidationError(f"No matching currencies found for symbols: {validated_symbols}")
            
        logger.info(f"Fetching prices from database for currency IDs: {currency_ids} in fiats: {validated_fiats}")
        
        # استفاده از سرویس دیتابیس برای دریافت قیمت‌ها
        start_time = time.time()
        prices_data = PriceDbService.get_prices(currency_ids, validated_fiats)
        
        # بررسی داده‌های دریافتی
        logger.debug(f"Received price data from service: {prices_data}")
        
        # تبدیل خروجی به فرمت مورد نیاز API - استفاده از Symbol اصلی در خروجی
        final_prices = {}
        
        # لاگ برای بررسی بیشتر مقادیر
        logger.debug(f"ID to symbol map: {id_to_symbol_map}")
        
        for currency_id, fiats in prices_data.items():
            # به دنبال Symbol در نقشه بگردیم - با استفاده از هر دو حالت رشته‌ای و عددی
            symbol = None
            
            # ابتدا مستقیم جستجو می‌کنیم
            symbol = id_to_symbol_map.get(currency_id)
            
            # اگر پیدا نشد، حالت رشته‌ای را امتحان می‌کنیم
            if not symbol and not isinstance(currency_id, str):
                symbol = id_to_symbol_map.get(str(currency_id))
                
            # اگر هنوز پیدا نشد، حالت عددی را امتحان می‌کنیم
            if not symbol and isinstance(currency_id, str):
                try:
                    numeric_id = int(currency_id)
                    symbol = id_to_symbol_map.get(numeric_id)
                except (ValueError, TypeError):
                    pass
            
            # اگر هنوز پیدا نشد، از CurrencyID استفاده می‌کنیم
            if not symbol:
                logger.warning(f"No symbol found for CurrencyID {currency_id}, using CurrencyID as symbol")
                symbol = str(currency_id)
                
            # لاگ برای بررسی Symbol انتخاب شده
            logger.debug(f"Mapped currency_id {currency_id} to symbol {symbol}")
                
            final_prices[symbol] = {}
            for fiat, price_info in fiats.items():
                price_value = price_info["price"]
                change_value = price_info["change_24h"]
                
                logger.debug(f"Processing price for {symbol}/{fiat}: price={price_value}, change={change_value}")
                
                # فرمت‌بندی قیمت
                numeric_str = dynamic_decimal_format(price_value)
                
                # فرمت‌بندی درصد تغییر
                if change_value is not None:
                    change_sign = "+" if change_value > 0 else ""
                    change_str = f"{change_sign}{change_value:.2f}%"
                else:
                    change_str = "0.00%"
                
                final_prices[symbol][fiat] = {
                    "price": numeric_str,
                    "change_24h": change_str
                }
                
                logger.debug(f"Formatted price for {symbol}/{fiat}: {final_prices[symbol][fiat]}")
        
        elapsed_time = time.time() - start_time
        logger.info(f"Successfully retrieved prices for {len(validated_symbols)} symbols in {len(validated_fiats)} fiat currencies in {elapsed_time:.4f} seconds")
        
        # اگر هیچ قیمتی پیدا نشد، یک پیام هشدار در لاگ
        if not final_prices:
            logger.warning(f"No prices found for symbols: {validated_symbols} in fiats: {validated_fiats}")
        
        return jsonify({
            "prices": final_prices,
            "success": True
        }), 200

    except ValidationError as e:
        logger.warning(f"Validation error in get_currency_price: {str(e)}")
        return jsonify({
            "success": False,
            "error_type": "validation_error",
            "message": str(e)
        }), 400
    except Exception as e:
        logger.error(f"Error in get_currency_price: {str(e)}", exc_info=True)
        return jsonify({
            "success": False,
            "error_type": "internal_error",
            "message": f"Internal server error: {str(e)}"
        }), 500

@CUpdate_bp.route('/update-prices', methods=['POST'])
@SecurityUtils.rate_limit(requests=10, window=3600)  # محدودیت به 10 درخواست در ساعت
@handle_api_errors
def update_prices_manually():
    """
    Manually trigger price updates from CoinMarketCap to database
    ---
    tags:
      - Currencies
    requestBody:
      required: false
      content:
        application/json:
          schema:
            type: object
            properties:
              Symbol:
                type: array
                items:
                  type: string
                description: Optional specific currencies to update. If not provided, all currencies will be updated.
              FiatCurrencies:
                type: array
                items:
                  type: string
                description: Optional specific fiat currencies to update. If not provided, all supported fiats will be updated.
    responses:
      200:
        description: Price update process completed
      400:
        description: Invalid input data
      429:
        description: Rate limit exceeded
      500:
        description: Server error
    """
    try:
        data = request.get_json() or {}
        logger.info("Manual price update requested")
        
        # فیلترهای اختیاری - پشتیبانی از Symbol، currencyname و CurrencyID
        specific_symbols = data.get('Symbol', data.get('currencyname', data.get('CurrencyID', [])))
        specific_fiats = data.get('FiatCurrencies', [])
        
        # اگر ارزهای خاصی مشخص شده باشند، آنها را اعتبارسنجی کن
        currency_ids = []
        symbols_used = []  # نگهداری Symbol های استفاده شده برای پاسخ
        
        if specific_symbols:
            if isinstance(specific_symbols, str):
                specific_symbols = [specific_symbols]
            
            if not isinstance(specific_symbols, list):
                raise ValidationError("Symbol/currencyname must be list or string")
                
            validated_symbols = [
                InputValidator.validate_string(
                    symbol,
                    "Symbol/currencyname",
                    pattern=r'^[A-Za-z0-9 ]+$'  # اجازه فاصله برای currencyname
                ) for symbol in specific_symbols
            ]
            
            logger.info(f"Updating specific symbols/names: {validated_symbols}")
            
            # تبدیل Symbol/currencyname به CurrencyID
            session = Session(bind=engine)
            try:
                # بررسی هم با Symbol و هم با CurrencyID و CurrencyName
                symbol_matches = session.query(Currencies).filter(
                    Currencies.Symbol.in_(validated_symbols)
                ).all()
                
                name_matches = session.query(Currencies).filter(
                    Currencies.CurrencyName.in_(validated_symbols)
                ).all()
                
                id_matches = session.query(Currencies).filter(
                    Currencies.CurrencyID.in_(validated_symbols)
                ).all()
                
                # لاگ کردن برای بررسی نتایج
                logger.debug(f"Symbol matches: {[c.Symbol for c in symbol_matches]}")
                logger.debug(f"Name matches: {[c.CurrencyName for c in name_matches]}")
                logger.debug(f"ID matches: {[c.CurrencyID for c in id_matches]}")
                
                # اضافه کردن موارد پیدا شده به لیست نهایی
                for currency in symbol_matches:
                    currency_ids.append(currency.CurrencyID)
                    symbols_used.append(currency.Symbol)
                
                # اضافه کردن تطابق‌های CurrencyName
                for currency in name_matches:
                    if currency.CurrencyID not in currency_ids:  # جلوگیری از تکرار
                        currency_ids.append(currency.CurrencyID)
                        symbols_used.append(currency.Symbol)
                    
                for currency in id_matches:
                    if currency.CurrencyID not in currency_ids:  # جلوگیری از تکرار
                        currency_ids.append(currency.CurrencyID)
                        symbols_used.append(currency.Symbol)
                
            finally:
                session.close()
                
            if not currency_ids:
                raise ValidationError(f"No matching currencies found for symbols: {validated_symbols}")
                
            logger.info(f"Converted to currency IDs: {currency_ids}")
        
        # اگر ارزهای فیات خاصی مشخص شده باشند، آنها را اعتبارسنجی کن
        if specific_fiats:
            if isinstance(specific_fiats, str):
                specific_fiats = [specific_fiats]
                
            if not isinstance(specific_fiats, list):
                raise ValidationError("FiatCurrencies must be list or string")
                
            validated_fiats = [
                InputValidator.validate_string(
                    fiat,
                    "FiatCurrency",
                    pattern=r'^[A-Z]{3}$'
                ) for fiat in specific_fiats
            ]
            
            logger.info(f"Updating for specific fiats: {validated_fiats}")
        else:
            validated_fiats = None
        
        # استفاده از سرویس قیمت
        result = PriceDbService.update_prices(
            currency_ids=currency_ids if currency_ids else None,
            fiat_currencies=validated_fiats if specific_fiats else None
        )
        
        if result["success"]:
            # برای پاسخ، از Symbol های واقعی استفاده می‌کنیم
            if symbols_used:
                symbols_str = ", ".join(symbols_used)
            else:
                symbols_str = "all currencies"
                
            return jsonify({
                "message": f"Successfully updated prices for {symbols_str}",
                "symbols_updated": symbols_used if symbols_used else "all",
                "currencies_updated": result["currencies_count"],
                "fiats_updated": result["fiats_count"],
                "elapsed_time": f"{result['elapsed_time']:.2f} seconds",
                "success": True
            }), 200
        else:
            return jsonify({
                "message": result["message"],
                "elapsed_time": f"{result['elapsed_time']:.2f} seconds",
                "success": False
            }), 500
                
    except ValidationError as e:
        logger.warning(f"Validation error in update_prices_manually: {str(e)}")
        return jsonify({
            "message": str(e),
            "success": False
        }), 400
    except Exception as e:
        logger.error(f"Error in update_prices_manually: {str(e)}", exc_info=True)
        return jsonify({
            "message": f"An unexpected error occurred: {str(e)}",
            "success": False
        }), 500

@CUpdate_bp.route('/price-stats', methods=['GET'])
@SecurityUtils.rate_limit(requests=20, window=60)
@handle_api_errors
def get_price_stats():
    """
    Get statistics about price updates in the database
    ---
    tags:
      - Currencies
    responses:
      200:
        description: Price statistics retrieved successfully
      500:
        description: Server error
    """
    try:
        logger.info("Fetching price statistics")
        stats = PriceDbService.get_price_stats()
        
        # Format datetime for JSON serialization if needed
        if stats["latest_update"] is not None:
            stats["latest_update"] = stats["latest_update"].isoformat()
            
        # Format percentage
        stats["up_to_date_percentage"] = f"{stats['up_to_date_percentage']:.2f}%"
        
        logger.info("Successfully retrieved price statistics")
        return jsonify({
            "stats": stats,
            "success": True
        }), 200
    except Exception as e:
        logger.error(f"Error in get_price_stats: {str(e)}", exc_info=True)
        return jsonify({
            "message": f"An unexpected error occurred: {str(e)}",
            "success": False
        }), 500

@CUpdate_bp.route('/key-stats', methods=['GET'])
@SecurityUtils.rate_limit(requests=10, window=60)
@handle_api_errors
def get_api_key_stats():
    """
    Get statistics about API key usage
    ---
    tags:
      - Currencies
    responses:
      200:
        description: API key statistics retrieved successfully
      500:
        description: Server error
    """
    try:
        logger.info("Fetching API key statistics")
        api_key_manager = ApiKeyManager()
        stats = api_key_manager.get_key_stats('coinmarketcap')
        
        logger.info(f"Successfully retrieved stats for {stats['total_keys']} API keys")
        return jsonify({
            "stats": stats,
            "success": True
        }), 200
    except Exception as e:
        logger.error(f"Error in get_api_key_stats: {str(e)}", exc_info=True)
        return jsonify({
            "message": f"An unexpected error occurred: {str(e)}",
            "success": False
        }), 500

def run_updater():
    """
    اجرای به‌روزرسانی قیمت‌ها برای همه ارزهای دیجیتال موجود در دیتابیس.
    این تابع برای فراخوانی از price_updater.py استفاده می‌شود.
    """
    logger.info("==================== STARTING PRICE UPDATER ====================")
    
    try:
        # استفاده از سرویس قیمت برای به‌روزرسانی همه ارزها
        result = PriceDbService.update_prices()
        
        if result["success"]:
            logger.info(f"Price update completed successfully. Updated {result['currencies_count']} currencies in {result['fiats_count']} fiat currencies in {result['elapsed_time']:.2f} seconds")
        else:
            logger.error("Price update failed")
            
    except Exception as e:
        logger.error(f"Error in price update process: {str(e)}", exc_info=True)
    finally:
        logger.info("==================== PRICE UPDATER FINISHED ====================")