from CC.utils.logging_config import get_logger

logger = get_logger(__name__)

def parse_eth_input_data(input_data):
    """
    تجزیه و تحلیل داده‌های ورودی تراکنش اتریوم
    
    Args:
        input_data (str): داده‌های ورودی تراکنش
        
    Returns:
        dict: اطلاعات استخراج شده
    """
    logger.debug(f"تجزیه داده‌های ورودی اتریوم: {input_data[:10]}...")
    
    # اگر داده‌های ورودی خالی یا کوتاه باشد، یک دیکشنری خالی برمی‌گردانیم
    if not input_data or len(input_data) < 10:
        return {}
        
    # استخراج شناسه متد (4 بایت اول یا 8 کاراکتر هگز بعد از 0x)
    method_id = input_data[:10]  # شامل 0x و 8 کاراکتر هگز
    
    # پیاده‌سازی تجزیه پارامترها بر اساس شناسه متد
    # این بخش بسته به نیازهای پروژه گسترش می‌یابد
    
    # بعضی از شناسه‌های متد معروف را تشخیص می‌دهیم
    if method_id == '0xa9059cbb':  # transfer(address,uint256)
        return {
            'method_id': method_id,
            'method_name': 'transfer',
            'type': 'token_transfer'
        }
    elif method_id == '0x095ea7b3':  # approve(address,uint256)
        return {
            'method_id': method_id,
            'method_name': 'approve',
            'type': 'token_approval'
        }
    elif method_id == '0x23b872dd':  # transferFrom(address,address,uint256)
        return {
            'method_id': method_id,
            'method_name': 'transferFrom',
            'type': 'token_transfer_from'
        }
    
    # در مورد سایر متدها، فقط شناسه متد را برمی‌گردانیم
    return {
        'method_id': method_id,
        'type': 'unknown'
    }

def format_eth_address(address):
    """
    فرمت‌سازی آدرس اتریوم (تبدیل به فرمت استاندارد با حروف کوچک)
    
    Args:
        address (str): آدرس اتریوم
        
    Returns:
        str: آدرس فرمت شده
    """
    if not address:
        return None
        
    # اطمینان از اینکه آدرس با 0x شروع می‌شود
    if not address.startswith('0x'):
        address = '0x' + address
        
    # تبدیل به حروف کوچک
    return address.lower()

def is_valid_eth_address(address):
    """
    اعتبارسنجی آدرس اتریوم
    
    Args:
        address (str): آدرس اتریوم
        
    Returns:
        bool: آیا آدرس معتبر است
    """
    if not address:
        return False
        
    # بررسی طول آدرس (0x + 40 کاراکتر هگز)
    if not address.startswith('0x') or len(address) != 42:
        return False
        
    # بررسی کاراکترهای مجاز (0-9, a-f, A-F)
    try:
        int(address[2:], 16)  # تبدیل بخش هگز به عدد
        return True
    except ValueError:
        return False 