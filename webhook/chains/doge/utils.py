from CC.utils.logging_config import get_logger

logger = get_logger(__name__)

def parse_doge_input_data(input_data):
    """
    تجزیه و تحلیل داده‌های ورودی تراکنش دوج‌کوین
    
    Args:
        input_data (str): داده‌های ورودی تراکنش
        
    Returns:
        dict: اطلاعات استخراج شده
    """
    logger.debug(f"تجزیه داده‌های ورودی دوج‌کوین: {input_data[:10] if input_data else 'خالی'}...")
    
    # دوج‌کوین ساختار ساده‌ای دارد و معمولاً فقط انتقال وجه بدون داده‌های پیچیده قراردادهوشمند است
    # در مورد دوج‌کوین، داده‌های ورودی معمولاً خالی است یا ساختار خاصی ندارد
    if not input_data or len(input_data) < 10:
        return {
            'method_id': None,
            'method_name': 'transfer',
            'type': 'native_transfer'
        }
    
    # در صورتی که داده‌های ورودی وجود داشته باشد، آن را تحلیل می‌کنیم
    return {
        'method_id': input_data[:10] if len(input_data) >= 10 else None,
        'method_name': 'unknown',
        'type': 'unknown'
    }

def format_doge_address(address):
    """
    فرمت‌سازی آدرس دوج‌کوین
    
    Args:
        address (str): آدرس دوج‌کوین
        
    Returns:
        str: آدرس فرمت شده
    """
    if not address:
        return None
    
    # حذف فاصله‌های اضافی
    return address.strip()

def is_valid_doge_address(address):
    """
    اعتبارسنجی آدرس دوج‌کوین
    
    Args:
        address (str): آدرس دوج‌کوین
        
    Returns:
        bool: آیا آدرس معتبر است
    """
    if not address:
        return False
    
    # آدرس‌های دوج‌کوین معمولاً با D شروع می‌شوند و 34 کاراکتر هستند
    if not address.startswith('D') or len(address) != 34:
        return False
    
    # بررسی کاراکترهای مجاز (Base58)
    allowed_chars = set("123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz")
    return all(c in allowed_chars for c in address)

def calculate_doge_fee(tx_size=None, fee_rate=None):
    """
    محاسبه کارمزد تراکنش دوج‌کوین
    
    Args:
        tx_size (int): اندازه تراکنش به بایت
        fee_rate (float): نرخ کارمزد برای هر بایت
        
    Returns:
        float: کارمزد تراکنش به DOGE
    """
    # مقادیر پیش‌فرض برای نرخ کارمزد و اندازه تراکنش
    DEFAULT_TX_SIZE = 250  # بایت
    DEFAULT_FEE_RATE = 0.01 / 1000  # DOGE per byte
    
    # استفاده از مقادیر پیش‌فرض اگر ورودی‌ها خالی باشند
    tx_size = tx_size or DEFAULT_TX_SIZE
    fee_rate = fee_rate or DEFAULT_FEE_RATE
    
    # محاسبه کارمزد
    fee = float(tx_size) * float(fee_rate)
    
    logger.debug(f"کارمزد محاسبه شده برای تراکنش دوج‌کوین: {fee} DOGE")
    return fee

def doge_to_satoshi(doge_amount):
    """
    تبدیل مقدار DOGE به ساتوشی (کوچکترین واحد)
    
    Args:
        doge_amount (float): مقدار به DOGE
        
    Returns:
        int: مقدار به ساتوشی
    """
    # هر DOGE = 10^8 ساتوشی
    return int(float(doge_amount) * 10**8)

def satoshi_to_doge(satoshi_amount):
    """
    تبدیل مقدار ساتوشی به DOGE
    
    Args:
        satoshi_amount (int): مقدار به ساتوشی
        
    Returns:
        float: مقدار به DOGE
    """
    # هر DOGE = 10^8 ساتوشی
    return float(satoshi_amount) / 10**8 