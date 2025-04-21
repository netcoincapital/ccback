from utils.logging_config import get_logger

logger = get_logger(__name__)

def parse_avax_input_data(input_data):
    """
    تجزیه و تحلیل داده‌های ورودی تراکنش آوالانچ
    
    Args:
        input_data (str): داده‌های ورودی تراکنش
        
    Returns:
        dict: اطلاعات استخراج شده
    """
    logger.debug(f"تجزیه داده‌های ورودی آوالانچ: {input_data[:10]}...")
    
    # اگر داده‌های ورودی خالی یا کوتاه باشد، یک دیکشنری خالی برمی‌گردانیم
    if not input_data or len(input_data) < 10:
        return {}
        
    # استخراج شناسه متد (4 بایت اول یا 8 کاراکتر هگز بعد از 0x)
    method_id = input_data[:10]  # شامل 0x و 8 کاراکتر هگز
    
    # پیاده‌سازی تجزیه پارامترها بر اساس شناسه متد
    # آوالانچ از EVM استفاده می‌کند، بنابراین شناسه‌های متد مشابه اتریوم هستند
    
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
    elif method_id == '0xd0e30db0':  # deposit()
        return {
            'method_id': method_id,
            'method_name': 'deposit',
            'type': 'deposit'
        }
    
    # در مورد سایر متدها، فقط شناسه متد را برمی‌گردانیم
    return {
        'method_id': method_id,
        'type': 'unknown'
    }

def format_avax_address(address):
    """
    فرمت‌سازی آدرس آوالانچ (تبدیل به فرمت استاندارد با حروف کوچک)
    
    Args:
        address (str): آدرس آوالانچ
        
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

def is_valid_avax_address(address):
    """
    اعتبارسنجی آدرس آوالانچ
    
    Args:
        address (str): آدرس آوالانچ
        
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

def calculate_avax_fee(gas_price, gas_used):
    """
    محاسبه کارمزد تراکنش آوالانچ
    
    Args:
        gas_price (float): قیمت گاز
        gas_used (float): مقدار گاز مصرف شده
        
    Returns:
        float: کارمزد تراکنش
    """
    if not gas_price or not gas_used:
        return 0
        
    # محاسبه کارمزد (gas_price * gas_used)
    fee = float(gas_price) * float(gas_used)
    
    # AVAX با 18 رقم اعشار نشان داده می‌شود
    return fee / (10 ** 18)

def is_token_transfer(input_data):
    """
    تشخیص آیا تراکنش یک انتقال توکن است
    
    Args:
        input_data (str): داده‌های ورودی تراکنش
        
    Returns:
        bool: آیا تراکنش انتقال توکن است
    """
    if not input_data or len(input_data) < 10:
        return False
        
    # بررسی شناسه متد انتقال توکن
    return input_data.startswith('0xa9059cbb') 