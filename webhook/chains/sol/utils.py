from utils.logging_config import get_logger

logger = get_logger(__name__)

def parse_sol_input_data(input_data):
    """
    تجزیه و تحلیل داده‌های ورودی تراکنش سولانا
    
    Args:
        input_data (str): داده‌های ورودی تراکنش
        
    Returns:
        dict: اطلاعات استخراج شده
    """
    logger.debug(f"تجزیه داده‌های ورودی سولانا: {input_data[:10] if input_data else 'None'}...")
    
    # اگر داده‌های ورودی خالی یا کوتاه باشد، یک دیکشنری خالی برمی‌گردانیم
    if not input_data:
        return {}
        
    # برای سولانا، ساختار داده‌های ورودی متفاوت است
    # در اینجا باید منطق تجزیه داده‌های سولانا را پیاده‌سازی کنیم
    try:
        # نمونه ساده - تشخیص SPL توکن ترانسفر
        if 'spl_token::instruction::TokenInstruction::Transfer' in input_data:
            return {
                'type': 'token_transfer',
                'method_name': 'spl_token_transfer'
            }
        elif 'system_program::transfer' in input_data:
            return {
                'type': 'native_transfer',
                'method_name': 'system_transfer'
            }
        
        # برای سایر انواع تراکنش‌ها
        return {
            'type': 'unknown',
            'raw_data': input_data[:100]  # فقط 100 کاراکتر اول را نگه می‌داریم
        }
    except Exception as e:
        logger.error(f"خطا در تجزیه داده‌های ورودی سولانا: {str(e)}")
        return {'type': 'error', 'error': str(e)}

def format_sol_address(address):
    """
    فرمت‌سازی آدرس سولانا (تبدیل به فرمت استاندارد)
    
    Args:
        address (str): آدرس سولانا
        
    Returns:
        str: آدرس فرمت شده
    """
    if not address:
        return None
        
    # آدرس‌های سولانا پیشوند خاصی ندارند
    # فقط مطمئن می‌شویم که فضاهای خالی اضافه حذف شده باشند
    return address.strip()

def is_valid_sol_address(address):
    """
    اعتبارسنجی آدرس سولانا
    
    Args:
        address (str): آدرس سولانا
        
    Returns:
        bool: آیا آدرس معتبر است
    """
    if not address:
        return False
        
    # آدرس‌های سولانا معمولاً 44 کاراکتر هستند و با حروف و اعداد تشکیل شده‌اند
    # و از الفبای base58 استفاده می‌کنند
    
    # بررسی طول آدرس
    if len(address) != 44 and len(address) != 43:
        return False
        
    # بررسی کاراکترهای مجاز (حروف و اعداد)
    valid_chars = set("123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz")
    return all(c in valid_chars for c in address)

def calculate_sol_fee(fee_lamports):
    """
    محاسبه کارمزد تراکنش سولانا
    
    Args:
        fee_lamports (int): کارمزد به lamports
        
    Returns:
        float: کارمزد به SOL
    """
    if not fee_lamports:
        return 0
        
    # تبدیل از lamports به SOL (1 SOL = 10^9 lamports)
    try:
        fee_sol = float(fee_lamports) / 1e9
        return fee_sol
    except (ValueError, TypeError):
        logger.error(f"خطا در محاسبه کارمزد سولانا: {fee_lamports}")
        return 0

def is_token_transfer(program_id):
    """
    تشخیص آیا تراکنش یک انتقال توکن SPL است
    
    Args:
        program_id (str): شناسه برنامه اجرا شده در تراکنش
        
    Returns:
        bool: آیا تراکنش انتقال توکن SPL است
    """
    # شناسه برنامه توکن SPL
    SPL_TOKEN_PROGRAM_ID = "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"
    
    return program_id == SPL_TOKEN_PROGRAM_ID 