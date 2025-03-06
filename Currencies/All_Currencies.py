import logging
from flask import Blueprint, jsonify, request
from database import SessionLocal, Currencies
from security.validators import InputValidator, SecurityUtils, ValidationError
from services.currency_service import CurrencyService
from utils.error_handlers import handle_api_errors
from utils.logging_config import get_logger
from schemas import (
    CurrencyListRequest,
    CurrencyListResponse,
    ErrorResponse
)

# Configure logging
logger = get_logger(__file__)
logger.info("Initializing currency post module")

# تعریف Blueprint برای نمایش تمامی کارنسی‌ها
CPost_bp = Blueprint('currency_post', __name__)

@CPost_bp.route('/all-currencies', methods=['GET'])
@SecurityUtils.rate_limit(requests=100, window=60)
@handle_api_errors
def get_all_currencies():
    """
    Get list of all currencies
    ---
    tags:
      - Currencies
    parameters:
      - name: page
        in: query
        schema:
          type: integer
          default: 1
        description: Page number for pagination
      - name: per_page
        in: query
        schema:
          type: integer
          default: 1000
          maximum: 1000
        description: Number of items per page (default and max is 1000)
      - name: all
        in: query
        schema:
          type: boolean
          default: false
        description: If true, returns all currencies regardless of pagination
    responses:
      200:
        description: List of currencies retrieved successfully
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/CurrencyListResponse'
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
    return _get_currencies(request.args.get('all'), request.args.get('page'), request.args.get('per_page'))

@CPost_bp.route('/all-currencies/all', methods=['GET'])
@SecurityUtils.rate_limit(requests=100, window=60)
@handle_api_errors
def get_all_currencies_direct():
    """
    Get all currencies at once
    ---
    tags:
      - Currencies
    responses:
      200:
        description: All currencies retrieved successfully
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/CurrencyListResponse'
      429:
        description: Rate limit exceeded
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/ErrorResponse'
    """
    return _get_currencies(all_param='true')

def _get_currencies(all_param=None, page_param=None, per_page_param=None):
    """Helper function to get currencies with pagination or all at once"""
    session = SessionLocal()
    try:
        # For GET requests, use query parameters
        try:
            page = int(page_param) if page_param is not None else 1
            per_page = int(per_page_param) if per_page_param is not None else 1000
            
            # Check for 'all' parameter in different formats
            logger.debug(f"Raw 'all' parameter value: {all_param}")
            
            if all_param is not None:
                if isinstance(all_param, str):
                    get_all = all_param.lower() in ['true', '1', 'yes', 'y']
                else:
                    get_all = bool(all_param)
            else:
                get_all = False
                
            logger.debug(f"Parsed get_all value: {get_all}")
        except (ValueError, TypeError) as e:
            logger.warning(f"Error parsing parameters: {str(e)}")
            page = 1
            per_page = 1000
            get_all = False
            
        # Validate parameters
        if page < 1:
            page = 1
        if per_page < 1:
            per_page = 1000
        if per_page > 1000:
            per_page = 1000

        logger.debug(f"Fetching currencies page {page} with {per_page} items per page, get_all={get_all}")
        
        currency_service = CurrencyService(session)
        
        try:
            if get_all:
                # Get total count first - use direct query to ensure we get the actual count
                total_count = session.query(Currencies).count()
                logger.info(f"Fetching all {total_count} currencies")
                
                # Fetch all currencies directly from the database
                all_currencies = [c.to_dict() for c in session.query(Currencies).all()]
                logger.info(f"Retrieved all {len(all_currencies)} currencies directly from database")
                
                currencies = all_currencies
            else:
                # Normal pagination
                currencies = currency_service.get_all_currencies_without_cache(page, per_page)
                logger.info(f"Retrieved {len(currencies)} currencies for page {page}")
        except Exception as e:
            logger.error(f"Error fetching currencies: {str(e)}")
            # Fallback to direct database query without caching
            if get_all:
                currencies = [c.to_dict() for c in session.query(Currencies).all()]
                logger.info(f"Fallback: Retrieved all {len(currencies)} currencies directly from database")
            else:
                offset = (page - 1) * per_page
                currencies_query = session.query(Currencies).offset(offset).limit(per_page).all()
                currencies = [c.to_dict() for c in currencies_query]
                logger.info(f"Fallback: Retrieved {len(currencies)} currencies for page {page} directly from database")
        
        # Get total count for pagination info
        total_count = session.query(Currencies).count()
        total_pages = (total_count + per_page - 1) // per_page  # Ceiling division
        
        response_data = {
            'currencies': currencies,
            'pagination': {
                'current_page': 1 if get_all else page,
                'per_page': total_count if get_all else per_page,
                'total_items': total_count,
                'total_pages': 1 if get_all else total_pages
            },
            'success': True
        }
        
        return jsonify(response_data), 200

    except ValidationError as e:
        logger.warning(f"Validation error in get_all_currencies: {str(e)}")
        raise
    except Exception as e:
        logger.error(f"Error in get_all_currencies: {str(e)}", exc_info=True)
        raise
    finally:
        session.close()
