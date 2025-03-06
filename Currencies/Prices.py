import logging
import json
import requests
from flask import Blueprint, jsonify, request
from database import SessionLocal, Currencies
from security.validators import InputValidator, SecurityUtils, ValidationError
from services.currency_service import CurrencyService
from utils.error_handlers import handle_api_errors
from utils.logging_config import get_logger
from schemas import (
    CurrencyPriceRequest,
    CurrencyPriceResponse,
    CurrencyUpdateResponse,
    ErrorResponse
)

# Configure logging
logger = get_logger(__file__)
logger.info("Initializing currency update module")

fiat_symbols = {
    "USD": "$", "CAD": "CA$", "AUD": "AU$", "GBP": "£", "EUR": "€",
    "KWD": "KD", "TRY": "₺", "IRR": "﷼", "SAR": "﷼", "CNY": "¥",
    "KRW": "₩", "JPY": "¥", "INR": "₹", "RUB": "₽", "IQD": "ع.د",
    "TND": "د.ت", "BHD": "ب.د"
}

def dynamic_decimal_format(price_value: float) -> str:
    """
    Format decimal values based on their magnitude
    
    Args:
        price_value (float): The price value to format
        
    Returns:
        str: Formatted price string with appropriate decimal places
    """
    if price_value >= 1:
        return f"{price_value:,.2f}"
    elif price_value >= 0.01:
        return f"{price_value:,.4f}"
    elif price_value >= 0.0001:
        return f"{price_value:,.6f}"
    else:
        return f"{price_value:,.8f}"

# Define CurrencyPriceService class
class CurrencyPriceService:
    """Service for retrieving cryptocurrency prices"""
    
    def __init__(self):
        self.api_key = "bbae831b-bd1b-4949-8945-2b5ab0b9456d"  # CoinMarketCap API key
        self.base_url = "https://pro-api.coinmarketcap.com/v1"
        
    def get_latest_prices(self, symbols, fiat="USD"):
        """
        Get latest prices for specified symbols in the given fiat currency
        
        Args:
            symbols (list): List of cryptocurrency symbols
            fiat (str): Fiat currency code
            
        Returns:
            dict: Dictionary of prices by symbol
        """
        try:
            logger.debug(f"Fetching latest prices for {symbols} in {fiat}")
            
            # Join symbols for API request
            symbol_str = ",".join(symbols)
            
            # Make API request
            url = f"{self.base_url}/cryptocurrency/quotes/latest"
            headers = {
                "X-CMC_PRO_API_KEY": self.api_key,
                "Accept": "application/json"
            }
            params = {
                "symbol": symbol_str,
                "convert": fiat
            }
            
            response = requests.get(url, headers=headers, params=params)
            data = response.json()
            
            # Extract prices
            result = {}
            if "data" in data:
                for symbol, info in data["data"].items():
                    if symbol in symbols and "quote" in info and fiat in info["quote"]:
                        result[symbol] = info["quote"][fiat]["price"]
            
            return result
        except Exception as e:
            logger.error(f"Error fetching latest prices: {str(e)}")
            return {"status": "error", "message": str(e)}
    
    def get_24h_changes(self, symbols, fiat="USD"):
        """
        Get 24-hour price changes for specified symbols in the given fiat currency
        
        Args:
            symbols (list): List of cryptocurrency symbols
            fiat (str): Fiat currency code
            
        Returns:
            dict: Dictionary of 24h price changes by symbol
        """
        try:
            logger.debug(f"Fetching 24h changes for {symbols} in {fiat}")
            
            # Join symbols for API request
            symbol_str = ",".join(symbols)
            
            # Make API request
            url = f"{self.base_url}/cryptocurrency/quotes/latest"
            headers = {
                "X-CMC_PRO_API_KEY": self.api_key,
                "Accept": "application/json"
            }
            params = {
                "symbol": symbol_str,
                "convert": fiat
            }
            
            response = requests.get(url, headers=headers, params=params)
            data = response.json()
            
            # Extract 24h changes
            result = {}
            if "data" in data:
                for symbol, info in data["data"].items():
                    if symbol in symbols and "quote" in info and fiat in info["quote"]:
                        result[symbol] = info["quote"][fiat]["percent_change_24h"]
            
            return result
        except Exception as e:
            logger.error(f"Error fetching 24h changes: {str(e)}")
            return {"status": "error", "message": str(e)}

CUpdate_bp = Blueprint('currency_update', __name__)

@CUpdate_bp.route('/update-prices', methods=['POST'])
@SecurityUtils.rate_limit(requests=10, window=60)
@handle_api_errors
def update_currency_prices():
    """
    Update currency prices
    ---
    tags:
      - Currencies
    responses:
      200:
        description: Currency prices updated successfully
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/CurrencyUpdateResponse'
      400:
        description: Invalid input data
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/ErrorResponse'
      429:
        description: Rate limit exceeded
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/ErrorResponse'
    """
    session = SessionLocal()
    try:
        logger.info("Starting currency price update")
        currency_service = CurrencyService(session)
        with session.begin():
            updated_prices = currency_service.update_prices()

        logger.info("Currency prices updated successfully")
        return jsonify({
            'updated_prices': updated_prices,
            'success': True
        }), 200

    except Exception as e:
        logger.error(f"Error updating currency prices: {str(e)}", exc_info=True)
        raise
    finally:
        session.close()

@CUpdate_bp.route('/prices', methods=['POST'])
@SecurityUtils.rate_limit(requests=100, window=60)
@handle_api_errors
def get_currency_price():
    """
    Get currency prices
    ---
    tags:
      - Currencies
    requestBody:
      required: true
      content:
        application/json:
          schema:
            $ref: '#/components/schemas/CurrencyPriceRequest'
    responses:
      200:
        description: Currency prices retrieved successfully
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/CurrencyPriceResponse'
      400:
        description: Invalid input data
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/ErrorResponse'
      429:
        description: Rate limit exceeded
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/ErrorResponse'
    """
    db_session = None
    try:
        data = request.get_json()
        if not data:
            raise ValidationError("Invalid request data")

        # Validate UserID
        user_id = InputValidator.validate_uuid(
            data.get('UserID', ''),
            "UserID"
        )

        # Validate CurrencyID
        currency_ids = data.get('CurrencyID', [])
        if isinstance(currency_ids, str):
            currency_ids = [currency_ids]
        if not isinstance(currency_ids, list):
            raise ValidationError("CurrencyID must be list or string")

        validated_currency_ids = [
            InputValidator.validate_string(
                cid,
                "CurrencyID",
                pattern=r'^[A-Z0-9]+$'
            ) for cid in currency_ids
        ]

        # Validate FiatCurrencies
        fiat_currencies = data.get('FiatCurrencies', None)
        if fiat_currencies is not None:
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

        logger.info(f"Fetching prices for currencies: {validated_currency_ids} in fiats: {validated_fiats}")

        # Query requested currencies
        db_session = SessionLocal()
        currencies = db_session.query(Currencies).filter(Currencies.Symbol.in_(currency_ids)).all()
        if not currencies:
            logger.warning(f"No currencies found for symbols: {currency_ids}")
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
                    # Decode if JSON
                    prices_response = json.loads(prices_response)
                except json.JSONDecodeError:
                    # Create error dictionary if not JSON
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

            # Must be dictionaries at this point
            if not isinstance(prices_response, dict):
                logger.error(f"prices_response is not a dict: {type(prices_response)}")
                return jsonify({"success": False, "message": "Invalid response format from get_latest_prices."}), 500

            if not isinstance(changes_response, dict):
                logger.error(f"changes_response is not a dict: {type(changes_response)}")
                return jsonify({"success": False, "message": "Invalid response format from get_24h_changes."}), 500

            # Check for error status
            if prices_response.get("status") == "error":
                logger.error(f"Error in prices response: {prices_response.get('message')}")
                return jsonify({"success": False, "message": prices_response.get("message", "Unknown error.")}), 500

            if changes_response.get("status") == "error":
                logger.error(f"Error in changes response: {changes_response.get('message')}")
                return jsonify({"success": False, "message": changes_response.get("message", "Unknown error.")}), 500

            # Create final output structure
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

        logger.info(f"Successfully retrieved prices for {len(symbols)} currencies in {len(fiat_currencies)} fiat currencies")
        return jsonify({"success": True, "prices": final_prices}), 200

    except ValidationError as e:
        logger.warning(f"Validation error in get_currency_price: {str(e)}")
        SecurityUtils.log_failed_attempt(
            request.remote_addr,
            request.endpoint,
            str(e)
        )
        raise
    except Exception as e:
        logger.error(f"Error in get_currency_price: {str(e)}", exc_info=True)
        raise
    finally:
        if db_session:
            db_session.close()