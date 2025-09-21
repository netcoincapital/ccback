#!/usr/bin/env python3
"""
سیستم کامل مدیریت خطاهای اتریوم
Complete Ethereum error management system
"""

from datetime import datetime


def map_ethereum_error_to_http_status(error_message: str) -> tuple[int, str]:
    """
    نگاشت خطاهای اتریوم به کدهای HTTP مناسب
    Map Ethereum errors to appropriate HTTP status codes
    """
    if not error_message:
        return 500, "Unknown error"
    
    error_lower = error_message.lower()
    
    # خطاهای ورودی نامعتبر - 422 Unprocessable Entity
    if error_message.startswith("invalid_input:"):
        clean_message = error_message.replace("invalid_input: ", "")
        return 422, clean_message
    
    # خطاهای شبکه/سرور - 502 Bad Gateway
    elif error_message.startswith("upstream_error:"):
        clean_message = error_message.replace("upstream_error: ", "")
        return 502, f"Network error: {clean_message}"
    
    # خطاهای اختصاصی
    elif "insufficient funds" in error_lower:
        return 422, "Insufficient balance for this transaction"
    
    elif "invalid address" in error_lower or "ens" in error_lower:
        return 422, "Invalid address format or ENS domain"
    
    elif "execution reverted" in error_lower or "revert" in error_lower:
        return 422, "Transaction would fail - recipient contract rejected the transfer"
    
    elif "nonce too low" in error_lower:
        return 429, "Transaction conflict - please try again in a few seconds"
    
    elif "gas price too low" in error_lower or "underpriced" in error_lower:
        return 429, "Network congestion - please try again with higher fee"
    
    elif "timeout" in error_lower or "connection" in error_lower:
        return 503, "Network connectivity issues - please try again"
    
    elif "rate limit" in error_lower:
        return 429, "API rate limit exceeded - please try again later"
    
    # خطای عمومی
    else:
        return 500, error_message

def handle_ethereum_transaction_error(error_message: str) -> dict:
    """
    مدیریت کامل خطاهای تراکنش اتریوم
    Complete Ethereum transaction error handling
    """
    status_code, user_message = map_ethereum_error_to_http_status(error_message)
    
    # تعیین قابلیت retry
    retry_recommended = status_code in [429, 502, 503]
    
    # تعیین زمان انتظار برای retry
    retry_delay = {
        422: 0,      # خطای ورودی - retry بی‌فایده
        429: 30,     # Rate limit/congestion - 30 ثانیه
        500: 60,     # خطای سرور - 1 دقیقه
        502: 120,    # مشکل شبکه - 2 دقیقه
        503: 180     # سرویس ناموجود - 3 دقیقه
    }.get(status_code, 60)
    
    return {
        "status": "error",
        "error": {
            "code": f"ETH_{status_code}",
            "message": user_message,
            "technical_details": error_message,
            "http_status": status_code,
            "retry_recommended": retry_recommended,
            "retry_after_seconds": retry_delay if retry_recommended else None,
            "category": {
                422: "validation_error",
                429: "rate_limit_or_congestion",
                500: "internal_error", 
                502: "network_error",
                503: "service_unavailable"
            }.get(status_code, "unknown_error")
        },
        "timestamp": datetime.now().isoformat()
    }



from flask import jsonify

def ethereum_error_middleware(func):
    """
    Decorator برای مدیریت خطاهای اتریوم در API endpoints
    """
    def wrapper(*args, **kwargs):
        try:
            result = func(*args, **kwargs)
            return result
            
        except Exception as e:
            error_response = handle_ethereum_transaction_error(str(e))
            status_code = error_response["error"]["http_status"]
            
            return jsonify(error_response), status_code
    
    return wrapper

# استفاده در API endpoints:
@ethereum_error_middleware
@app.route('/api/ethereum/send', methods=['POST'])
def send_ethereum_transaction():
    # کد ارسال تراکنش
    result, error = ethereum_service.send_transaction(tx_id, private_key)
    
    if error:
        # خطا به صورت خودکار به HTTP status مناسب نگاشت می‌شود
        raise Exception(error)
    
    return jsonify(result)

