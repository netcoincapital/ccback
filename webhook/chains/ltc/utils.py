from CC.utils.logging_config import get_logger

logger = get_logger(__name__)

def parse_ltc_input_data(input_data):
    """
    تجزیه و تحلیل داده‌های ورودی تراکنش لایت‌کوین
    
    Args:
        input_data (str): داده‌های ورودی تراکنش
        
    Returns:
        dict: اطلاعات استخراج شده
    """
    logger.debug(f"تجزیه داده‌های ورودی لایت‌کوین: {input_data[:10] if input_data else 'خالی'}...")
    
    # لایت‌کوین ساختار ساده‌ای دارد و معمولاً فقط انتقال وجه بدون داده‌های پیچیده قراردادهوشمند است
    # در مورد لایت‌کوین، داده‌های ورودی معمولاً خالی است یا ساختار خاصی ندارد
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

def format_ltc_address(address):
    """
    فرمت‌سازی آدرس لایت‌کوین
    
    Args:
        address (str): آدرس لایت‌کوین
        
    Returns:
        str: آدرس فرمت شده
    """
    if not address:
        return None
    
    # حذف فاصله‌های اضافی
    return address.strip()

def is_valid_ltc_address(address):
    """
    اعتبارسنجی آدرس لایت‌کوین
    
    Args:
        address (str): آدرس لایت‌کوین
        
    Returns:
        bool: آیا آدرس معتبر است
    """
    if not address:
        return False
    
    # آدرس‌های لایت‌کوین سنتی با L شروع می‌شوند و 34 کاراکتر هستند
    # آدرس‌های Segwit با M شروع می‌شوند
    # آدرس‌های Bech32 با ltc1 شروع می‌شوند
    if not (address.startswith('L') or address.startswith('M') or address.startswith('ltc1')):
        return False
    
    # بررسی طول آدرس
    if address.startswith('ltc1'):
        # آدرس‌های Bech32 معمولاً بین 42 تا 62 کاراکتر هستند
        if not (42 <= len(address) <= 62):
            return False
    else:
        # آدرس‌های سنتی معمولاً 34 کاراکتر هستند
        if len(address) != 34:
            return False
    
    # بررسی کاراکترهای مجاز برای آدرس‌های سنتی (Base58)
    if address.startswith('L') or address.startswith('M'):
        allowed_chars = set("123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz")
        return all(c in allowed_chars for c in address)
    
    # بررسی کاراکترهای مجاز برای آدرس‌های Bech32
    if address.startswith('ltc1'):
        allowed_chars = set("023456789acdefghjklmnpqrstuvwxyz")
        return all(c in allowed_chars for c in address[4:])  # بررسی بعد از پیشوند ltc1
    
    return False

def calculate_ltc_fee(tx_size=None, fee_rate=None):
    """
    محاسبه کارمزد تراکنش لایت‌کوین
    
    Args:
        tx_size (int): اندازه تراکنش به بایت
        fee_rate (float): نرخ کارمزد برای هر بایت
        
    Returns:
        float: کارمزد تراکنش به LTC
    """
    # مقادیر پیش‌فرض برای نرخ کارمزد و اندازه تراکنش
    DEFAULT_TX_SIZE = 250  # بایت
    DEFAULT_FEE_RATE = 0.0001 / 1000  # LTC per byte
    
    # استفاده از مقادیر پیش‌فرض اگر ورودی‌ها خالی باشند
    tx_size = tx_size or DEFAULT_TX_SIZE
    fee_rate = fee_rate or DEFAULT_FEE_RATE
    
    # محاسبه کارمزد
    fee = float(tx_size) * float(fee_rate)
    
    logger.debug(f"کارمزد محاسبه شده برای تراکنش لایت‌کوین: {fee} LTC")
    return fee

def ltc_to_litoshi(ltc_amount):
    """
    تبدیل مقدار LTC به لایتوشی (کوچکترین واحد)
    
    Args:
        ltc_amount (float): مقدار به LTC
        
    Returns:
        int: مقدار به لایتوشی
    """
    # هر LTC = 10^8 لایتوشی
    return int(float(ltc_amount) * 10**8)

def litoshi_to_ltc(litoshi_amount):
    """
    تبدیل مقدار لایتوشی به LTC
    
    Args:
        litoshi_amount (int): مقدار به لایتوشی
        
    Returns:
        float: مقدار به LTC
    """
    # هر LTC = 10^8 لایتوشی
    return float(litoshi_amount) / 10**8

def extract_tx_inputs_outputs(transaction_data):
    """
    استخراج ورودی‌ها و خروجی‌های تراکنش لایت‌کوین
    
    Args:
        transaction_data (dict): داده‌های تراکنش
        
    Returns:
        tuple: (ورودی‌ها، خروجی‌ها)
    """
    inputs = []
    outputs = []
    
    # استخراج ورودی‌ها
    if 'vin' in transaction_data and isinstance(transaction_data['vin'], list):
        for vin in transaction_data['vin']:
            input_data = {
                'txid': vin.get('txid', ''),
                'vout': vin.get('vout', 0),
                'address': vin.get('addr', '') or vin.get('address', ''),
                'value': vin.get('value', 0)
            }
            inputs.append(input_data)
    
    # استخراج خروجی‌ها
    if 'vout' in transaction_data and isinstance(transaction_data['vout'], list):
        for vout in transaction_data['vout']:
            # استخراج آدرس از ساختارهای مختلف داده
            address = ''
            if 'scriptPubKey' in vout and 'addresses' in vout['scriptPubKey'] and isinstance(vout['scriptPubKey']['addresses'], list):
                address = vout['scriptPubKey']['addresses'][0] if vout['scriptPubKey']['addresses'] else ''
            elif 'addresses' in vout and isinstance(vout['addresses'], list):
                address = vout['addresses'][0] if vout['addresses'] else ''
            elif 'address' in vout:
                address = vout['address']
            
            output_data = {
                'n': vout.get('n', 0),
                'address': address,
                'value': vout.get('value', 0)
            }
            outputs.append(output_data)
    
    return inputs, outputs 