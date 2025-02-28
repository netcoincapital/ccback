import logging
from flask import Blueprint, jsonify, request
from database import SessionLocal, Currencies
from security.validators import InputValidator, SecurityUtils, ValidationError
from services.currency_service import CurrencyService
from utils.error_handlers import handle_api_errors

logger = logging.getLogger(__name__)

# تعریف Blueprint برای نمایش تمامی کارنسی‌ها
CPost_bp = Blueprint('currency_post', __name__)

@CPost_bp.route('/all-currencies', methods=['POST'])
@SecurityUtils.rate_limit(requests=100, window=60)
@handle_api_errors
def get_all_currencies():
    """دریافت لیست تمام ارزها"""
    session = SessionLocal()
    try:
        data = request.get_json()
        if not data:
            raise ValidationError("Invalid request data")

        page = InputValidator.validate_integer(
            data.get('page', 1),
            "Page",
            min_value=1
        )
        per_page = InputValidator.validate_integer(
            data.get('per_page', 10),
            "PerPage",
            min_value=1,
            max_value=100
        )

        currency_service = CurrencyService(session)
        currencies = currency_service.get_all_currencies(page, per_page)

        return jsonify({
            'currencies': currencies,
            'success': True
        }), 200

    finally:
        session.close()
