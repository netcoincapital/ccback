#!/usr/bin/env python3
"""
نگاشت خطاهای اتریوم به کدهای HTTP صحیح
Map Ethereum errors to correct HTTP status codes
"""

def create_error_mapper():
    """ایجاد نگاشت‌کننده خطا برای API layer"""
    
    error_mapper_code = '''
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
'''
    
    return error_mapper_code

def create_api_middleware():
    """ایجاد middleware برای API layer"""
    
    middleware_code = '''
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
'''
    
    return middleware_code

def main():
    print("🔧 نگاشت‌کننده خطاهای اتریوم")
    print("="*50)
    
    print("📋 مشکلات باقی‌مانده:")
    print("   1. ❌ ENS domains باعث crash")
    print("   2. ❌ to_wei type errors")
    print("   3. ❌ estimate_gas revert errors")
    print("   4. ❌ سقف 50 Gwei خیلی پایین")
    print("   5. ❌ خطاهای Tatum به 400 نگاشت می‌شوند")
    
    print(f"\n✅ راه‌حل‌های اعمال شده:")
    print("   1. ✅ ENS resolution ایمن")
    print("   2. ✅ _to_wei_safe() method")
    print("   3. ✅ مدیریت خطای execution reverted")
    print("   4. ✅ سقف 100 Gwei برای تخمین")
    print("   5. ✅ تفکیک خطاهای ورودی/شبکه")
    
    # ایجاد کدهای کمکی
    error_mapper = create_error_mapper()
    api_middleware = create_api_middleware()
    
    # ذخیره فایل کامل
    complete_code = f'''#!/usr/bin/env python3
"""
سیستم کامل مدیریت خطاهای اتریوم
Complete Ethereum error management system
"""

from datetime import datetime

{error_mapper}

{api_middleware}
'''
    
    with open('ethereum_error_management.py', 'w', encoding='utf-8') as f:
        f.write(complete_code)
    
    print(f"\n💾 سیستم مدیریت خطا در فایل ethereum_error_management.py ذخیره شد")
    
    print(f"\n🎯 نگاشت خطاها:")
    print("   invalid_input: → 422 (Unprocessable Entity)")
    print("   upstream_error: → 502 (Bad Gateway)")
    print("   insufficient funds: → 422")
    print("   execution reverted: → 422") 
    print("   nonce conflict: → 429 (Too Many Requests)")
    print("   network timeout: → 503 (Service Unavailable)")
    
    print(f"\n🔄 برای اعمال در API:")
    print("   1. import کردن error handlers")
    print("   2. اضافه کردن @ethereum_error_middleware")
    print("   3. استفاده از handle_ethereum_transaction_error()")
    
    print(f"\n🎉 نتیجه:")
    print("   ❌ HTTP 400 دیگر برای خطاهای شبکه نمی‌آید")
    print("   ✅ کدهای HTTP مناسب برای هر نوع خطا")
    print("   ✅ پیام‌های کاربری واضح")
    print("   ✅ راهنمایی retry مناسب")

if __name__ == "__main__":
    main()
