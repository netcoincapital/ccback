import logging
from flask import Blueprint, jsonify, request
from database import SessionLocal, Currencies, Blockchains
from security.validators import InputValidator, SecurityUtils, ValidationError
from services.currency_service import CurrencyService
from utils.error_handlers import handle_api_errors
from utils.logging_config import get_logger
from schemas import (
    CurrencyListRequest,
    CurrencyListResponse,
    ErrorResponse
)
import json
import time
from sqlalchemy import and_, not_, exists

# Configure logging
logger = get_logger(__file__)
logger.info("Initializing currency post module")

# تعریف Blueprint برای نمایش تمامی کارنسی‌ها
CPost_bp = Blueprint('CPost_bp', __name__)

@CPost_bp.route('/all-currencies', methods=['GET'])
@SecurityUtils.rate_limit(requests=100, window=60)
@handle_api_errors
def get_all_currencies():
    """
    Get all currencies at once
    ---
    tags:
      - Currencies
    responses:
      200:
        description: Complete list of all currencies
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/CurrencyListResponse'
    """
    session = SessionLocal()
    try:
        start_time = time.time()
        
        # Get all currencies with blockchain information
        currencies_query = session.query(
            Currencies, 
            Blockchains.BlockchainName
        ).join(
            Blockchains, 
            Currencies.BlockchainID == Blockchains.BlockchainID
        ).all()
        
        # Convert to dictionary with blockchain name
        currencies = []
        for currency, blockchain_name in currencies_query:
            # ایجاد دیکشنری با ترتیب مشخص فیلدها
            currency_dict = {
                'BlockchainName': blockchain_name,
                'CurrencyID': currency.CurrencyID,
                'CurrencyName': currency.CurrencyName,
                'DecimalPlaces': currency.DecimalPlaces,
                'Icon': currency.Icon,
                'IsToken': currency.IsToken,
                'SmartContractAddress': currency.SmartContractAddress,
                'Symbol': currency.Symbol
            }
            currencies.append(currency_dict)
        
        total_count = len(currencies)
        
        end_time = time.time()
        processing_time = end_time - start_time
        
        logger.info(f"Sending ALL {total_count} currencies at once. Processing time: {processing_time:.2f} seconds")
        
        response_data = {
            'currencies': currencies,
            'success': True
        }
        
        return jsonify(response_data), 200
    except Exception as e:
        logger.error(f"Error fetching all currencies: {str(e)}")
        raise
    finally:
        session.close()

# برای سازگاری با کدهای قبلی، روت قدیمی را هم نگه می‌داریم
@CPost_bp.route('/all-currencies/all', methods=['GET'])
@SecurityUtils.rate_limit(requests=100, window=60)
@handle_api_errors
def get_all_currencies_redirect():
    """
    Same as the main all-currencies endpoint
    ---
    tags:
      - Currencies
    responses:
      200:
        description: Complete list of all currencies
    """
    return get_all_currencies()
