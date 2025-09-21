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
from Currencies.currency_price_service import dynamic_decimal_format, fiat_symbols, CurrencyPriceService

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
              include_historical:
                type: boolean
                description: Include historical data for charts (default false)
              days:
                type: integer
                description: Number of days of historical data (default 30, max 365)
    responses:
      200:
        description: Currency prices retrieved successfully
        content:
          application/json:
            schema:
              type: object
              properties:
                prices:
                  type: object
                  additionalProperties:
                    type: object
                    additionalProperties:
                      type: object
                      properties:
                        price:
                          type: string
                          description: Formatted price (e.g., "50,123.45")
                        market_cap:
                          type: string
                          description: Formatted market cap (e.g., "$1.2T", "$500.5B")
                        volume_24h:
                          type: string
                          description: Formatted 24h volume (e.g., "$25.4B")
                        change_1h:
                          type: string
                          description: 1-hour change percentage (e.g., "+2.45%")
                        change_24h:
                          type: string
                          description: 24-hour change percentage (e.g., "-1.23%")
                        change_7d:
                          type: string
                          description: 7-day change percentage (e.g., "+5.67%")
                success:
                  type: boolean
                historical_data:
                  type: object
                  description: Historical data (if include_historical is true)
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

        # Historical data parameters
        include_historical = data.get('include_historical', False)
        days = data.get('days', 30)
        if days > 365:
            days = 365
        elif days < 1:
            days = 30

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
                
                # فرمت‌بندی فیلدهای اضافی
                market_cap_value = price_info.get("market_cap")
                volume_24h_value = price_info.get("volume_24h")
                change_1h_value = price_info.get("change_1h")
                change_7d_value = price_info.get("change_7d")
                
                # فرمت market cap
                market_cap_str = None
                if market_cap_value and market_cap_value > 0:
                    if market_cap_value >= 1e12:
                        market_cap_str = f"${market_cap_value/1e12:.2f}T"
                    elif market_cap_value >= 1e9:
                        market_cap_str = f"${market_cap_value/1e9:.2f}B"
                    elif market_cap_value >= 1e6:
                        market_cap_str = f"${market_cap_value/1e6:.2f}M"
                    elif market_cap_value >= 1e3:
                        market_cap_str = f"${market_cap_value/1e3:.2f}K"
                    else:
                        market_cap_str = f"${market_cap_value:.2f}"
                
                # فرمت volume 24h
                volume_24h_str = None
                if volume_24h_value and volume_24h_value > 0:
                    if volume_24h_value >= 1e12:
                        volume_24h_str = f"${volume_24h_value/1e12:.2f}T"
                    elif volume_24h_value >= 1e9:
                        volume_24h_str = f"${volume_24h_value/1e9:.2f}B"
                    elif volume_24h_value >= 1e6:
                        volume_24h_str = f"${volume_24h_value/1e6:.2f}M"
                    elif volume_24h_value >= 1e3:
                        volume_24h_str = f"${volume_24h_value/1e3:.2f}K"
                    else:
                        volume_24h_str = f"${volume_24h_value:.2f}"
                
                # فرمت change 1h
                change_1h_str = None
                if change_1h_value is not None:
                    change_1h_sign = "+" if change_1h_value > 0 else ""
                    change_1h_str = f"{change_1h_sign}{change_1h_value:.2f}%"
                
                # فرمت change 7d
                change_7d_str = None
                if change_7d_value is not None:
                    change_7d_sign = "+" if change_7d_value > 0 else ""
                    change_7d_str = f"{change_7d_sign}{change_7d_value:.2f}%"

                final_prices[symbol][fiat] = {
                    "price": numeric_str,
                    "market_cap": market_cap_str,
                    "volume_24h": volume_24h_str,
                    "change_1h": change_1h_str,
                    "change_24h": change_str,
                    "change_7d": change_7d_str
                }
                
                logger.debug(f"Formatted price for {symbol}/{fiat}: {final_prices[symbol][fiat]}")
        
        elapsed_time = time.time() - start_time
        logger.info(f"Successfully retrieved prices for {len(validated_symbols)} symbols in {len(validated_fiats)} fiat currencies in {elapsed_time:.4f} seconds")
        
        # اگر هیچ قیمتی پیدا نشد، یک پیام هشدار در لاگ
        if not final_prices:
            logger.warning(f"No prices found for symbols: {validated_symbols} in fiats: {validated_fiats}")
        
        # اگر داده‌های تاریخی درخواست شده باشد، آنها را اضافه کن
        response_data = {
            "prices": final_prices,
            "success": True
        }
        
        if include_historical:
            logger.info(f"Including historical data for {days} days")
            try:
                # محاسبه زمان شروع
                from datetime import datetime, timedelta
                time_end = datetime.now().isoformat() + "Z"
                time_start = (datetime.now() - timedelta(days=days)).isoformat() + "Z"
                
                # دریافت داده‌های تاریخی
                price_service = CurrencyPriceService()
                historical_data = price_service.get_historical_data(
                    currency_ids, time_start, time_end, "daily", validated_fiats
                )
                
                if historical_data.get("success"):
                    # تبدیل داده‌های تاریخی به فرمت مناسب
                    historical_chart_data = {}
                    data_points = historical_data.get("data", {})
                    
                    for currency_id, fiats in data_points.items():
                        symbol = id_to_symbol_map.get(currency_id) or id_to_symbol_map.get(str(currency_id)) or str(currency_id)
                        historical_chart_data[symbol] = {}
                        
                        for fiat, price_history in fiats.items():
                            historical_chart_data[symbol][fiat] = {
                                "prices": [],
                                "timestamps": [],
                                "market_caps": [],
                                "volumes": []
                            }
                            
                            for point in price_history:
                                historical_chart_data[symbol][fiat]["timestamps"].append(point["timestamp"])
                                historical_chart_data[symbol][fiat]["prices"].append(point["price"])
                                historical_chart_data[symbol][fiat]["market_caps"].append(point["market_cap"])
                                historical_chart_data[symbol][fiat]["volumes"].append(point["volume_24h"])
                    
                    response_data["historical_data"] = historical_chart_data
                    response_data["days"] = days
                else:
                    logger.warning(f"Failed to fetch historical data: {historical_data.get('message')}")
                    
            except Exception as hist_error:
                logger.error(f"Error fetching historical data: {str(hist_error)}")
        
        return jsonify(response_data), 200

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

@CUpdate_bp.route('/historical-prices', methods=['POST'])
@SecurityUtils.rate_limit(requests=50, window=60)
@handle_api_errors
def get_historical_prices():
    """
    Get historical price data for cryptocurrency charts
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
                description: List of cryptocurrency symbols
              FiatCurrencies:
                type: array
                items:
                  type: string
                description: List of fiat currencies (default USD)
              time_start:
                type: string
                format: date-time
                description: Start time in ISO format (default 30 days ago)
              time_end:
                type: string
                format: date-time
                description: End time in ISO format (default now)
              interval:
                type: string
                description: Time interval (daily, hourly, etc.) (default daily)
    responses:
      200:
        description: Historical price data retrieved successfully
      400:
        description: Invalid input data
      429:
        description: Rate limit exceeded
      500:
        description: Server error
    """
    try:
        data = request.get_json() or {}
        
        # پشتیبانی از هر دو فرمت Symbol و currencyname
        symbols = data.get('Symbol', data.get('currencyname', data.get('CurrencyID', [])))
        if isinstance(symbols, str):
            symbols = [symbols]
        if not isinstance(symbols, list) or not symbols:
            raise ValidationError("At least one Symbol/currencyname is required")

        validated_symbols = [
            InputValidator.validate_string(
                symbol,
                "Symbol/currencyname",
                pattern=r'^[A-Za-z0-9 ]+$'
            ) for symbol in symbols
        ]

        # Validate FiatCurrencies
        fiat_currencies = data.get('FiatCurrencies', ["USD"])
        if isinstance(fiat_currencies, str):
            fiat_currencies = [fiat_currencies]
        if not isinstance(fiat_currencies, list):
            raise ValidationError("FiatCurrencies must be list or string")
        
        validated_fiats = [
            InputValidator.validate_string(
                fiat,
                "FiatCurrency",
                pattern=r'^[A-Z]{3}$'
            ) for fiat in fiat_currencies
        ]

        # Time parameters
        time_start = data.get('time_start')
        time_end = data.get('time_end')
        interval = data.get('interval', 'daily')

        # Validate interval
        valid_intervals = ['5m', '10m', '15m', '30m', '45m', '1h', '2h', '3h', '4h', '6h', '12h', '1d', '2d', '3d', '7d', '14d', '15d', '30d', '60d', '90d', '365d', 'daily', 'hourly']
        if interval not in valid_intervals:
            interval = 'daily'

        logger.info(f"Getting historical data for symbols: {validated_symbols}, fiats: {validated_fiats}, interval: {interval}")

        # تبدیل Symbol یا currencyname به CurrencyID
        currency_ids = []
        symbol_to_id_map = {}
        id_to_symbol_map = {}

        session = Session(bind=engine)
        try:
            # بررسی Symbol
            symbol_matches = session.query(Currencies).filter(
                Currencies.Symbol.in_(validated_symbols)
            ).all()
            
            # بررسی CurrencyName
            name_matches = session.query(Currencies).filter(
                Currencies.CurrencyName.in_(validated_symbols)
            ).all()
            
            # بررسی CurrencyID
            id_matches = session.query(Currencies).filter(
                Currencies.CurrencyID.in_(validated_symbols)
            ).all()
            
            # اضافه کردن موارد پیدا شده
            for currency in symbol_matches:
                currency_ids.append(currency.CurrencyID)
                symbol_to_id_map[currency.Symbol] = currency.CurrencyID
                id_to_symbol_map[currency.CurrencyID] = currency.Symbol
                id_to_symbol_map[str(currency.CurrencyID)] = currency.Symbol
            
            for currency in name_matches:
                if currency.CurrencyID not in currency_ids:
                    currency_ids.append(currency.CurrencyID)
                    symbol_to_id_map[currency.CurrencyName] = currency.CurrencyID
                    id_to_symbol_map[currency.CurrencyID] = currency.Symbol
                    id_to_symbol_map[str(currency.CurrencyID)] = currency.Symbol
                
            for currency in id_matches:
                if currency.CurrencyID not in currency_ids:
                    currency_ids.append(currency.CurrencyID)
                    symbol_to_id_map[currency.CurrencyID] = currency.CurrencyID
                    id_to_symbol_map[currency.CurrencyID] = currency.Symbol
                    id_to_symbol_map[str(currency.CurrencyID)] = currency.Symbol
            
        finally:
            session.close()
            
        if not currency_ids:
            raise ValidationError(f"No matching currencies found for symbols: {validated_symbols}")

        # استفاده از سرویس قیمت برای دریافت داده‌های تاریخی
        price_service = CurrencyPriceService()
        historical_data = price_service.get_historical_data(
            currency_ids, time_start, time_end, interval, validated_fiats
        )

        if not historical_data.get("success"):
            return jsonify({
                "success": False,
                "error_type": "data_fetch_error",
                "message": historical_data.get("message", "Failed to fetch historical data")
            }), 500

        # تبدیل خروجی به فرمت مناسب برای چارت
        chart_data = {}
        data_points = historical_data.get("data", {})

        for currency_id, fiats in data_points.items():
            symbol = id_to_symbol_map.get(currency_id) or id_to_symbol_map.get(str(currency_id)) or str(currency_id)
            chart_data[symbol] = {}
            
            for fiat, price_history in fiats.items():
                chart_data[symbol][fiat] = {
                    "prices": [],
                    "timestamps": [],
                    "market_caps": [],
                    "volumes": []
                }
                
                for point in price_history:
                    chart_data[symbol][fiat]["timestamps"].append(point["timestamp"])
                    chart_data[symbol][fiat]["prices"].append(point["price"])
                    chart_data[symbol][fiat]["market_caps"].append(point["market_cap"])
                    chart_data[symbol][fiat]["volumes"].append(point["volume_24h"])

        logger.info(f"Successfully retrieved historical data for {len(validated_symbols)} symbols")
        
        return jsonify({
            "historical_data": chart_data,
            "success": True,
            "interval": interval,
            "time_start": time_start,
            "time_end": time_end
        }), 200

    except ValidationError as e:
        logger.warning(f"Validation error in get_historical_prices: {str(e)}")
        return jsonify({
            "success": False,
            "error_type": "validation_error",
            "message": str(e)
        }), 400
    except Exception as e:
        logger.error(f"Error in get_historical_prices: {str(e)}", exc_info=True)
        return jsonify({
            "success": False,
            "error_type": "internal_error",
            "message": f"Internal server error: {str(e)}"
        }), 500

@CUpdate_bp.route('/historical-prices-bulk', methods=['POST'])
@SecurityUtils.rate_limit(requests=2, window=3600)  # محدودیت به 2 درخواست در ساعت برای bulk
@handle_api_errors
def get_bulk_historical_prices():
    """
    Get bulk historical price data for long periods (months/years)
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
                description: List of cryptocurrency symbols
              FiatCurrencies:
                type: array
                items:
                  type: string
                description: List of fiat currencies (default USD)
              months:
                type: integer
                description: Number of months to fetch (max 12 for Hobbyist plan)
                minimum: 1
                maximum: 12
              interval:
                type: string
                description: Time interval (daily recommended for long periods)
                default: daily
    """
    try:
        data = request.get_json() or {}
        
        # Validate symbols
        symbols = data.get('Symbol', [])
        if isinstance(symbols, str):
            symbols = [symbols]
        if not symbols:
            raise ValidationError("At least one Symbol is required")

        # Validate months
        months = data.get('months', 1)
        if not isinstance(months, int) or months < 1 or months > 12:
            raise ValidationError("months must be between 1 and 12")

        # Validate other parameters
        fiat_currencies = data.get('FiatCurrencies', ["USD"])
        if isinstance(fiat_currencies, str):
            fiat_currencies = [fiat_currencies]
            
        interval = data.get('interval', 'daily')
        
        logger.info(f"Bulk historical data request: {symbols} for {months} months")
        
        # Convert symbols to currency IDs (same logic as regular endpoint)
        currency_ids = []
        session = Session(bind=engine)
        try:
            symbol_matches = session.query(Currencies).filter(
                Currencies.Symbol.in_(symbols)
            ).all()
            
            name_matches = session.query(Currencies).filter(
                Currencies.CurrencyName.in_(symbols)
            ).all()
            
            for currency in symbol_matches + name_matches:
                if currency.CurrencyID not in currency_ids:
                    currency_ids.append(currency.CurrencyID)
                    
        finally:
            session.close()
            
        if not currency_ids:
            raise ValidationError(f"No matching currencies found for symbols: {symbols}")

        # Use batch fetcher for long-term data
        from utils.batch_historical_fetcher import BatchHistoricalFetcher
        
        fetcher = BatchHistoricalFetcher()
        result = fetcher.fetch_long_term_data(
            currency_ids=currency_ids,
            months=months,
            interval=interval,
            fiat_currencies=fiat_currencies
        )
        
        if result.get('success'):
            return jsonify({
                'success': True,
                'message': result['message'],
                'records_added': result['total_records_added'],
                'batches_processed': result['total_batches'],
                'months_processed': result['months_processed'],
                'recommendation': 'Use /historical-prices endpoint to retrieve the stored data'
            }), 200
        else:
            return jsonify({
                'success': False,
                'error_type': 'bulk_fetch_error',
                'message': result.get('message')
            }), 500
            
    except ValidationError as e:
        return jsonify({
            'success': False,
            'error_type': 'validation_error',
            'message': str(e)
        }), 400
    except Exception as e:
        logger.error(f"Error in bulk historical prices: {str(e)}", exc_info=True)
        return jsonify({
            'success': False,
            'error_type': 'internal_error',
            'message': str(e)
        }), 500

@CUpdate_bp.route('/historical-prices-auto', methods=['POST'])
@SecurityUtils.rate_limit(requests=3, window=3600)  # محدودیت به 3 درخواست در ساعت
@handle_api_errors
def get_historical_prices_auto():
    """
    Automatically fetch historical data for all currencies in database
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
              time_start:
                type: string
                format: date-time
                description: Start time in ISO format
              time_end:
                type: string
                format: date-time
                description: End time in ISO format
              interval:
                type: string
                description: Time interval (default daily)
              fiat_currencies:
                type: array
                items:
                  type: string
                description: List of fiat currencies (default USD)
              max_currencies:
                type: integer
                description: Maximum number of currencies to process (default 20)
    """
    try:
        data = request.get_json() or {}
        
        # Parameters
        time_start = data.get('time_start')
        time_end = data.get('time_end')
        interval = data.get('interval', 'daily')
        fiat_currencies = data.get('fiat_currencies', ['USD'])
        max_currencies = data.get('max_currencies', 20)
        
        logger.info(f"Auto historical data request: {max_currencies} currencies, interval {interval}")
        
        # Get all currencies with CMC_ID from database
        session = Session(bind=engine)
        try:
            currencies = session.query(Currencies).filter(
                Currencies.CMC_ID.isnot(None),
                Currencies.CMC_ID != '',
                Currencies.CMC_ID != 0
            ).limit(max_currencies).all()
            
            if not currencies:
                raise ValidationError("No currencies with valid CMC_ID found in database")
            
            currency_ids = [c.CurrencyID for c in currencies]
            currency_info = [(c.Symbol, c.CurrencyName, c.CMC_ID) for c in currencies]
            
            logger.info(f"Found {len(currency_ids)} currencies with CMC_ID")
            for symbol, name, cmc_id in currency_info:
                logger.debug(f"  {symbol} ({name}) - CMC_ID: {cmc_id}")
                
        finally:
            session.close()
        
        # Use historical data service
        price_service = CurrencyPriceService()
        result = price_service.update_historical_data(
            currency_ids=currency_ids,
            time_start=time_start,
            time_end=time_end,
            interval=interval,
            fiat_currencies=fiat_currencies
        )
        
        if result.get('success'):
            return jsonify({
                'success': True,
                'message': f'Historical data updated for {len(currency_ids)} currencies',
                'currencies_processed': len(currency_ids),
                'currency_list': [f"{info[0]} ({info[1]})" for info in currency_info],
                'records_added': result.get('records_added', 0),
                'time_range': f"{time_start} to {time_end}",
                'interval': interval
            }), 200
        else:
            return jsonify({
                'success': False,
                'error_type': 'update_error',
                'message': result.get('message', 'Failed to update historical data')
            }), 500
            
    except ValidationError as e:
        return jsonify({
            'success': False,
            'error_type': 'validation_error',
            'message': str(e)
        }), 400
    except Exception as e:
        logger.error(f"Error in auto historical prices: {str(e)}", exc_info=True)
        return jsonify({
            'success': False,
            'error_type': 'internal_error',
            'message': str(e)
        }), 500

@CUpdate_bp.route('/update-historical-prices', methods=['POST'])
@SecurityUtils.rate_limit(requests=5, window=3600)  # محدودیت به 5 درخواست در ساعت
@handle_api_errors
def update_historical_prices():
    """
    Manually update historical price data from CoinMarketCap
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
                description: Optional specific currencies to update
              FiatCurrencies:
                type: array
                items:
                  type: string
                description: Optional specific fiat currencies to update
              time_start:
                type: string
                format: date-time
                description: Start time for historical data
              time_end:
                type: string
                format: date-time
                description: End time for historical data
              interval:
                type: string
                description: Time interval for data points
    responses:
      200:
        description: Historical price update process completed
      400:
        description: Invalid input data
      429:
        description: Rate limit exceeded
      500:
        description: Server error
    """
    try:
        data = request.get_json() or {}
        logger.info("Manual historical price update requested")
        
        # فیلترهای اختیاری
        specific_symbols = data.get('Symbol', data.get('currencyname', data.get('CurrencyID', [])))
        specific_fiats = data.get('FiatCurrencies', [])
        time_start = data.get('time_start')
        time_end = data.get('time_end')
        interval = data.get('interval', 'daily')
        
        # تبدیل symbols به currency_ids
        currency_ids = []
        symbols_used = []
        
        if specific_symbols:
            if isinstance(specific_symbols, str):
                specific_symbols = [specific_symbols]
            
            validated_symbols = [
                InputValidator.validate_string(
                    symbol,
                    "Symbol/currencyname",
                    pattern=r'^[A-Za-z0-9 ]+$'
                ) for symbol in specific_symbols
            ]
            
            session = Session(bind=engine)
            try:
                symbol_matches = session.query(Currencies).filter(
                    Currencies.Symbol.in_(validated_symbols)
                ).all()
                
                name_matches = session.query(Currencies).filter(
                    Currencies.CurrencyName.in_(validated_symbols)
                ).all()
                
                id_matches = session.query(Currencies).filter(
                    Currencies.CurrencyID.in_(validated_symbols)
                ).all()
                
                for currency in symbol_matches:
                    currency_ids.append(currency.CurrencyID)
                    symbols_used.append(currency.Symbol)
                
                for currency in name_matches:
                    if currency.CurrencyID not in currency_ids:
                        currency_ids.append(currency.CurrencyID)
                        symbols_used.append(currency.Symbol)
                    
                for currency in id_matches:
                    if currency.CurrencyID not in currency_ids:
                        currency_ids.append(currency.CurrencyID)
                        symbols_used.append(currency.Symbol)
                
            finally:
                session.close()
                
            if not currency_ids:
                raise ValidationError(f"No matching currencies found for symbols: {validated_symbols}")

        # اعتبارسنجی fiat currencies
        if specific_fiats:
            if isinstance(specific_fiats, str):
                specific_fiats = [specific_fiats]
                
            validated_fiats = [
                InputValidator.validate_string(
                    fiat,
                    "FiatCurrency",
                    pattern=r'^[A-Z]{3}$'
                ) for fiat in specific_fiats
            ]
        else:
            validated_fiats = None

        # استفاده از سرویس قیمت برای به‌روزرسانی
        price_service = CurrencyPriceService()
        result = price_service.update_historical_data(
            currency_ids=currency_ids if currency_ids else None,
            time_start=time_start,
            time_end=time_end,
            interval=interval,
            fiat_currencies=validated_fiats
        )
        
        if result["success"]:
            symbols_str = ", ".join(symbols_used) if symbols_used else "all currencies"
            return jsonify({
                "message": f"Successfully updated historical data for {symbols_str}",
                "symbols_updated": symbols_used if symbols_used else "all",
                "records_added": result.get("records_added", 0),
                "records_failed": result.get("records_failed", 0),
                "success": True
            }), 200
        else:
            return jsonify({
                "message": result["message"],
                "success": False
            }), 500
                
    except ValidationError as e:
        logger.warning(f"Validation error in update_historical_prices: {str(e)}")
        return jsonify({
            "message": str(e),
            "success": False
        }), 400
    except Exception as e:
        logger.error(f"Error in update_historical_prices: {str(e)}", exc_info=True)
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