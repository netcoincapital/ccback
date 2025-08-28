import re
from CC.utils.logging_config import get_logger

logger = get_logger(__name__)

def parse_xrp_input_data(input_data):
    """
    تجزیه و تحلیل داده‌های ورودی تراکنش ریپل
    
    Args:
        input_data (str): داده‌های ورودی تراکنش
        
    Returns:
        dict: اطلاعات استخراج شده
    """
    logger.debug(f"تجزیه داده‌های ورودی ریپل: {input_data[:10] if input_data else 'خالی'}...")
    
    # ریپل ساختار داده متفاوتی دارد و معمولاً به جای داده‌های ورودی، از ساختاری
    # به نام TransactionType برای مشخص کردن نوع تراکنش استفاده می‌کند
    
    result = {
        'method_id': None,
        'method_name': 'unknown',
        'type': 'unknown'
    }
    
    # اگر داده ورودی نداریم، تراکنش را Payment فرض می‌کنیم
    if not input_data or len(input_data) < 2:
        result['method_name'] = 'Payment'
        result['type'] = 'payment'
        return result
    
    # بررسی برخی الگوهای معمول در داده‌های تراکنش ریپل
    if input_data.startswith('Payment'):
        result['method_name'] = 'Payment'
        result['type'] = 'payment'
    elif input_data.startswith('OfferCreate'):
        result['method_name'] = 'OfferCreate'
        result['type'] = 'offer_create'
    elif input_data.startswith('OfferCancel'):
        result['method_name'] = 'OfferCancel'
        result['type'] = 'offer_cancel'
    elif input_data.startswith('TrustSet'):
        result['method_name'] = 'TrustSet'
        result['type'] = 'trust_set'
    elif input_data.startswith('EscrowCreate'):
        result['method_name'] = 'EscrowCreate'
        result['type'] = 'escrow_create'
    elif input_data.startswith('EscrowFinish'):
        result['method_name'] = 'EscrowFinish'
        result['type'] = 'escrow_finish'
    elif input_data.startswith('EscrowCancel'):
        result['method_name'] = 'EscrowCancel'
        result['type'] = 'escrow_cancel'
    
    return result

def format_xrp_address(address):
    """
    فرمت‌سازی آدرس ریپل
    
    Args:
        address (str): آدرس ریپل
        
    Returns:
        str: آدرس فرمت شده
    """
    if not address:
        return None
    
    # حذف فاصله‌های اضافی
    return address.strip()

def is_valid_xrp_address(address):
    """
    اعتبارسنجی آدرس ریپل
    
    Args:
        address (str): آدرس ریپل
        
    Returns:
        bool: آیا آدرس معتبر است
    """
    if not address:
        return False
    
    # آدرس‌های ریپل معمولاً با r شروع می‌شوند و بین 25 تا 35 کاراکتر هستند
    pattern = r'^r[a-zA-Z0-9]{24,34}$'
    return bool(re.match(pattern, address))

def calculate_xrp_fee(fee_drops):
    """
    محاسبه کارمزد تراکنش ریپل
    در شبکه ریپل، کارمزد بر اساس واحد "drops" است (1 XRP = 1,000,000 drops)
    
    Args:
        fee_drops (str): کارمزد به واحد drops
        
    Returns:
        float: کارمزد به واحد XRP
    """
    if not fee_drops:
        # کارمزد پیش‌فرض شبکه ریپل (12 drops)
        fee_drops = "12"
    
    try:
        # تبدیل از drops به XRP
        fee_xrp = float(fee_drops) / 1000000
        logger.debug(f"کارمزد محاسبه شده برای تراکنش ریپل: {fee_xrp} XRP")
        return fee_xrp
    except (ValueError, TypeError) as e:
        logger.error(f"خطا در محاسبه کارمزد ریپل: {str(e)}")
        # مقدار پیش‌فرض در صورت خطا
        return 0.000012  # 12 drops

def drops_to_xrp(drops):
    """
    تبدیل مقدار drops به XRP
    
    Args:
        drops (str): مقدار به واحد drops
        
    Returns:
        float: مقدار به واحد XRP
    """
    try:
        return float(drops) / 1000000
    except (ValueError, TypeError):
        return 0

def xrp_to_drops(xrp):
    """
    تبدیل مقدار XRP به drops
    
    Args:
        xrp (float): مقدار به واحد XRP
        
    Returns:
        int: مقدار به واحد drops
    """
    try:
        return int(float(xrp) * 1000000)
    except (ValueError, TypeError):
        return 0

def extract_transaction_type(transaction_data):
    """
    استخراج نوع تراکنش ریپل
    
    Args:
        transaction_data (dict): داده‌های تراکنش
        
    Returns:
        str: نوع تراکنش
    """
    # ریپل انواع تراکنش را در فیلد TransactionType نگهداری می‌کند
    transaction_type = transaction_data.get('TransactionType')
    if transaction_type:
        return transaction_type
    
    # اگر TransactionType نداریم، سعی می‌کنیم از فیلدهای دیگر تشخیص دهیم
    if 'Amount' in transaction_data and ('Destination' in transaction_data or 'to' in transaction_data):
        return 'Payment'
    
    return 'Unknown'

def extract_destination_tag(transaction_data):
    """
    استخراج تگ مقصد (Destination Tag) از داده‌های تراکنش ریپل
    
    Args:
        transaction_data (dict): داده‌های تراکنش
        
    Returns:
        int or None: تگ مقصد
    """
    # تگ مقصد می‌تواند با نام‌های مختلفی در داده‌های تراکنش وجود داشته باشد
    for field in ['DestinationTag', 'destination_tag', 'dt']:
        if field in transaction_data:
            try:
                return int(transaction_data[field])
            except (ValueError, TypeError):
                pass
    
    return None 