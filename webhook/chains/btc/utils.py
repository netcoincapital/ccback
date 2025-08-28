from CC.utils.logging_config import get_logger

logger = get_logger(__name__)

def analyze_btc_inputs_outputs(inputs, outputs):
    """
    تحلیل ورودی‌ها و خروجی‌های تراکنش بیت‌کوین
    
    Args:
        inputs (list): لیست ورودی‌های تراکنش
        outputs (list): لیست خروجی‌های تراکنش
        
    Returns:
        dict: نتایج تحلیل
    """
    logger.debug(f"تحلیل {len(inputs)} ورودی و {len(outputs)} خروجی بیت‌کوین")
    
    # محاسبه مجموع مقادیر ورودی و خروجی
    total_input = sum(float(inp.get('value', 0)) for inp in inputs)
    total_output = sum(float(out.get('value', 0)) for out in outputs)
    
    # محاسبه کارمزد
    fee = total_input - total_output
    
    # آنالیز نوع احتمالی تراکنش
    transaction_type = "unknown"
    
    # تراکنش ساده (1 ورودی، 1 یا 2 خروجی - یکی برای گیرنده و یکی برای باقیمانده)
    if len(inputs) == 1 and len(outputs) <= 2:
        transaction_type = "simple_transfer"
    
    # تراکنش با ورودی‌های متعدد (احتمالاً تجمیع یا coinjoin)
    elif len(inputs) > 1 and len(outputs) == 1:
        transaction_type = "consolidation"
    
    # تراکنش با خروجی‌های متعدد (احتمالاً پرداخت به چندین آدرس)
    elif len(inputs) == 1 and len(outputs) > 2:
        transaction_type = "multi_payment"
    
    # تراکنش پیچیده (ورودی‌ها و خروجی‌های متعدد)
    elif len(inputs) > 1 and len(outputs) > 1:
        transaction_type = "complex"
        
    return {
        "transaction_type": transaction_type,
        "input_count": len(inputs),
        "output_count": len(outputs),
        "total_input": total_input,
        "total_output": total_output,
        "fee": fee
    }

def is_p2pkh_address(address):
    """
    بررسی آیا آدرس از نوع Pay-to-Public-Key-Hash است
    
    Args:
        address (str): آدرس بیت‌کوین
        
    Returns:
        bool: نتیجه بررسی
    """
    # آدرس‌های P2PKH با 1 شروع می‌شوند
    return address and address.startswith('1')

def is_p2sh_address(address):
    """
    بررسی آیا آدرس از نوع Pay-to-Script-Hash است
    
    Args:
        address (str): آدرس بیت‌کوین
        
    Returns:
        bool: نتیجه بررسی
    """
    # آدرس‌های P2SH با 3 شروع می‌شوند
    return address and address.startswith('3')

def is_bech32_address(address):
    """
    بررسی آیا آدرس از نوع Bech32 (SegWit) است
    
    Args:
        address (str): آدرس بیت‌کوین
        
    Returns:
        bool: نتیجه بررسی
    """
    # آدرس‌های Bech32 با bc1 شروع می‌شوند
    return address and address.startswith('bc1') 