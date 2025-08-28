from CC.webhook.transaction_processor import TransactionProcessor
from CC.utils.logging_config import get_logger
from CC.webhook.chains.doge.utils import (
    parse_doge_input_data,
    format_doge_address,
    is_valid_doge_address,
    calculate_doge_fee,
    doge_to_satoshi,
    satoshi_to_doge
)

logger = get_logger(__name__)

class DogecoinProcessor(TransactionProcessor):
    """پردازشگر وب‌هوک‌های مخصوص دوج‌کوین (DOGE)"""
    
    def __init__(self):
        super().__init__()
        logger.info("پردازشگر دوج‌کوین راه‌اندازی شد")
    
    def process_webhook(self, webhook_data):
        """
        پردازش وب‌هوک دوج‌کوین
        این متد منطق خاص دوج‌کوین را اجرا می‌کند
        
        Args:
            webhook_data (dict): داده‌های وب‌هوک دریافتی
            
        Returns:
            dict: نتیجه پردازش
        """
        logger.info("پردازش وب‌هوک دوج‌کوین")
        
        # نرمال‌سازی داده‌های وب‌هوک
        self._normalize_webhook_data(webhook_data)
        
        # بررسی داده‌های ورودی تراکنش (در دوج‌کوین معمولاً وجود ندارد)
        input_data = webhook_data.get('input', '')
        if input_data:
            parsed_data = parse_doge_input_data(input_data)
            webhook_data['doge_input_data'] = parsed_data
        
        # محاسبه کارمزد تراکنش اگر اطلاعات آن موجود باشد
        if 'size' in webhook_data and 'feeRate' in webhook_data:
            try:
                tx_size = webhook_data.get('size')
                fee_rate = webhook_data.get('feeRate')
                fee = calculate_doge_fee(tx_size, fee_rate)
                webhook_data['fee'] = fee
                logger.info(f"کارمزد محاسبه شده برای تراکنش: {fee} DOGE")
            except Exception as e:
                logger.error(f"خطا در محاسبه کارمزد: {str(e)}")
                
                # استفاده از کارمزد پیش‌فرض در صورت خطا
                webhook_data['fee'] = calculate_doge_fee()
        else:
            # استفاده از کارمزد پیش‌فرض اگر اطلاعات کافی نباشد
            webhook_data['fee'] = calculate_doge_fee()
        
        # تنظیم نوع دارایی (در دوج‌کوین فقط انتقال ارز اصلی است)
        webhook_data['asset_type'] = 'native'
        
        # افزودن اطلاعات تکمیلی به داده‌های وب‌هوک
        webhook_data['chain'] = 'dogecoin'
        if 'currency' not in webhook_data:
            webhook_data['currency'] = 'doge'
        
        # تبدیل مقدار به فرمت صحیح
        if 'amount' in webhook_data and 'valueIn' in webhook_data:
            # این حالت برای تراکنش‌های ورودی است
            webhook_data['amount'] = satoshi_to_doge(float(webhook_data.get('valueIn', 0)))
        elif 'amount' in webhook_data and isinstance(webhook_data['amount'], str):
            try:
                # تبدیل مقدار به عدد اعشاری
                amount = float(webhook_data['amount'])
                
                # اگر مقدار بزرگ است، احتمالاً در واحد ساتوشی است
                if amount > 1e7:  # احتمالاً در واحد ساتوشی است
                    amount = satoshi_to_doge(amount)
                    webhook_data['amount'] = str(amount)
            except (ValueError, TypeError):
                pass
            
        # فراخوانی پردازشگر اصلی
        return super().process_webhook(webhook_data)
    
    def _normalize_webhook_data(self, webhook_data):
        """
        نرمال‌سازی داده‌های وب‌هوک دوج‌کوین
        بعضی از فیلدها در وب‌هوک دوج‌کوین ممکن است با فرمت‌های مختلف ارسال شوند
        
        Args:
            webhook_data (dict): داده‌های وب‌هوک دریافتی
        """
        # استاندارد کردن نام‌های فیلدها
        field_mappings = {
            'txid': 'hash',
            'tx_hash': 'hash',
            'transactionHash': 'hash',
            'transaction_hash': 'hash',
            'blockNumber': 'blockNumber',
            'block_number': 'blockNumber',
            'height': 'blockNumber',
            'blockHash': 'blockHash',
            'block_hash': 'blockHash',
            'fromAddress': 'from',
            'from_address': 'from',
            'sender': 'from',
            'vin': 'from',
            'toAddress': 'to',
            'to_address': 'to',
            'recipient': 'to',
            'vout': 'to',
            'value': 'amount',
            'txvalue': 'amount',
            'tx_value': 'amount'
        }
        
        for old_field, new_field in field_mappings.items():
            if old_field in webhook_data and new_field not in webhook_data:
                webhook_data[new_field] = webhook_data[old_field]
        
        # بررسی ساختار خاص وب‌هوک دوج‌کوین
        # در بعضی وب‌هوک‌ها، اطلاعات فرستنده و گیرنده در آرایه‌های 'vin' و 'vout' ذخیره می‌شود
        if 'vin' in webhook_data and isinstance(webhook_data['vin'], list) and len(webhook_data['vin']) > 0:
            first_input = webhook_data['vin'][0]
            if 'addr' in first_input:
                webhook_data['from'] = first_input['addr']
            elif 'address' in first_input:
                webhook_data['from'] = first_input['address']
        
        if 'vout' in webhook_data and isinstance(webhook_data['vout'], list) and len(webhook_data['vout']) > 0:
            first_output = webhook_data['vout'][0]
            if 'addresses' in first_output and isinstance(first_output['addresses'], list) and len(first_output['addresses']) > 0:
                webhook_data['to'] = first_output['addresses'][0]
            elif 'address' in first_output:
                webhook_data['to'] = first_output['address']
            
            # استخراج مقدار انتقال
            if 'value' in first_output:
                webhook_data['amount'] = first_output['value']
    
    def update_transaction(self, blockchain, tx_hash):
        """
        به‌روزرسانی تراکنش دوج‌کوین
        
        Args:
            blockchain (str): نام بلاکچین
            tx_hash (str): هش تراکنش
            
        Returns:
            dict: نتیجه به‌روزرسانی
        """
        logger.info(f"به‌روزرسانی تراکنش دوج‌کوین: {tx_hash}")
        
        # فراخوانی متد اصلی
        return super().update_transaction(blockchain, tx_hash)
    
    def _process_address_transaction(self, blockchain, from_address, to_address, value, transaction_id, webhook_data):
        """
        پردازش تراکنش آدرس دوج‌کوین
        
        Args:
            blockchain (str): نام بلاکچین
            from_address (str): آدرس فرستنده
            to_address (str): آدرس گیرنده
            value (str): مقدار تراکنش
            transaction_id (str): شناسه تراکنش
            webhook_data (dict): داده‌های کامل وب‌هوک
            
        Returns:
            dict: نتیجه پردازش
        """
        logger.info(f"پردازش تراکنش آدرس دوج‌کوین: {transaction_id}")
        
        # بررسی اعتبار آدرس گیرنده
        if not is_valid_doge_address(to_address):
            logger.warning(f"آدرس دوج‌کوین نامعتبر: {to_address}")
        
        # فرمت‌بندی آدرس‌ها
        formatted_from = format_doge_address(from_address)
        formatted_to = format_doge_address(to_address)
        
        # بازنویسی اطلاعات با آدرس‌های فرمت شده
        if formatted_from:
            webhook_data['from'] = formatted_from
        if formatted_to:
            webhook_data['to'] = formatted_to
            
        # فراخوانی متد اصلی
        return super()._process_address_transaction(blockchain, formatted_from, formatted_to, value, transaction_id, webhook_data)
    
    def _process_contract_event(self, blockchain, webhook_data, transaction_id):
        """
        پردازش رویداد قرارداد دوج‌کوین
        (دوج‌کوین قرارداد هوشمند ندارد، اما برای سازگاری با API پیاده‌سازی می‌شود)
        
        Args:
            blockchain (str): نام بلاکچین
            webhook_data (dict): داده‌های وب‌هوک
            transaction_id (str): شناسه تراکنش
            
        Returns:
            dict: نتیجه پردازش
        """
        logger.info(f"پردازش رویداد قرارداد دوج‌کوین: {transaction_id}")
        logger.warning("دوج‌کوین قرارداد هوشمند پشتیبانی نمی‌کند")
        
        # فراخوانی متد اصلی
        return super()._process_contract_event(blockchain, webhook_data, transaction_id) 