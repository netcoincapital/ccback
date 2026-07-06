import base58

from CC.utils.logging_config import get_logger

logger = get_logger(__name__)

def parse_tron_contract_data(contract_data, contract_type):
    """
    تجزیه و تحلیل داده‌های قرارداد ترون
    
    Args:
        contract_data (dict): داده‌های قرارداد
        contract_type (str): نوع قرارداد
        
    Returns:
        dict: اطلاعات استخراج شده
    """
    logger.debug(f"تجزیه داده‌های قرارداد ترون نوع {contract_type}")
    
    result = {
        'contract_type': contract_type
    }
    
    # بررسی نوع قرارداد و استخراج اطلاعات مربوطه
    if contract_type == 'TransferContract':
        # انتقال TRX معمولی
        owner_address = contract_data.get('owner_address')
        to_address = contract_data.get('to_address')
        amount = contract_data.get('amount')
        
        if owner_address:
            result['from_address'] = owner_address
            
        if to_address:
            result['to_address'] = to_address
            
        if amount:
            # تبدیل به ترکس (تقسیم بر 1,000,000)
            trx_amount = float(amount) / 1000000
            result['amount'] = trx_amount
            result['asset'] = 'TRX'  # استفاده از TRX به جای TRON
        
    elif contract_type == 'TriggerSmartContract':
        # فراخوانی قرارداد هوشمند
        owner_address = contract_data.get('owner_address')
        contract_address = contract_data.get('contract_address')
        data = contract_data.get('data')
        
        result['from_address'] = owner_address
        result['contract_address'] = contract_address
        
        # تلاش برای تجزیه داده‌های ABI
        if data and data.startswith('a9059cbb'):  # تشخیص متد transfer
            result['method'] = 'transfer'
            result['token_transfer'] = True
            
            try:
                # استخراج آدرس گیرنده (24 کاراکتر بعدی پس از 8 کاراکتر اول)
                to_address_hex = data[8:72]
                result['to_address_hex'] = '41' + to_address_hex  # افزودن پیشوند 41 برای آدرس‌های ترون
                
                # استخراج مقدار (باقیمانده داده)
                amount_hex = data[72:]
                amount = int(amount_hex, 16)
                result['amount_raw'] = amount
                
                # نیاز به تقسیم بر دسیمال توکن دارد که معمولاً 6 یا 18 است
                # مقدار پیش‌فرض 18 در نظر گرفته می‌شود
                token_decimals = 18
                amount_adjusted = amount / (10 ** token_decimals)
                result['amount'] = amount_adjusted
            except Exception as e:
                logger.error(f"خطا در تجزیه داده‌های TRC20: {str(e)}")
    
    elif contract_type == 'TransferAssetContract':
        # انتقال توکن TRC10
        owner_address = contract_data.get('owner_address')
        to_address = contract_data.get('to_address')
        asset_name = contract_data.get('asset_name')
        amount = contract_data.get('amount')
        
        result['from_address'] = owner_address
        result['to_address'] = to_address
        
        # استانداردسازی نام دارایی
        if asset_name and asset_name.upper() == 'TRON':
            asset_name = 'TRX'
            
        result['asset'] = asset_name
        
        if amount:
            # تبدیل به مقدار واقعی (تقسیم بر 10^precision)
            # برای TRC10 معمولاً precision=6 است
            token_amount = float(amount) / 1000000  # برای سادگی از 10^6 استفاده می‌کنیم
            result['amount'] = token_amount
            result['token_transfer'] = True
    
    return result

def tron_address_to_hex(address):
    """
    تبدیل آدرس ترون از فرمت Base58 به Hex (hexadecimal).
    
    Args:
        address (str): آدرس ترون در فرمت Base58 (شروع با T)
        
    Returns:
        str: آدرس در فرمت هگز (شروع با 41) یا None در صورت خطا
    """
    if not address or not isinstance(address, str) or not address.startswith('T'):
        logger.warning(f"Invalid TRON address format for hex conversion: {address}")
        return None
    try:
        decoded = base58.b58decode_check(address)
        return decoded.hex()
    except Exception as e:
        logger.error(f"Error converting TRON address to hex: {address}, error: {str(e)}")
        return None

def hex_to_tron_address(hex_address):
    """
    تبدیل آدرس ترون از فرمت Hex (hexadecimal) به Base58.
    
    Args:
        hex_address (str): آدرس ترون در فرمت هگز (شروع با 41)
        
    Returns:
        str: آدرس در فرمت Base58 (شروع با T) یا None در صورت خطا
    """
    if not hex_address or not isinstance(hex_address, str):
        logger.warning(f"Invalid TRON hex address format for base58 conversion: {hex_address}")
        return None
    try:
        # Remove 0x prefix first if present
        clean_hex = hex_address
        if clean_hex.startswith('0x'):
            clean_hex = clean_hex[2:]

        # Now validate it starts with 41 (TRON hex prefix)
        if not clean_hex.startswith('41'):
            logger.warning(f"Invalid TRON hex address format for base58 conversion: {hex_address}")
            return None

        decoded = bytes.fromhex(clean_hex)
        return base58.b58encode_check(decoded).decode()
    except Exception as e:
        logger.error(f"Error converting TRON hex address to base58: {hex_address}, error: {str(e)}")
        return None 