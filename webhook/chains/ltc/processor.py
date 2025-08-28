from CC.webhook.transaction_processor import TransactionProcessor
from CC.utils.logging_config import get_logger
from CC.webhook.chains.ltc.utils import (
    parse_ltc_input_data,
    format_ltc_address,
    is_valid_ltc_address,
    calculate_ltc_fee,
    ltc_to_litoshi,
    litoshi_to_ltc,
    extract_tx_inputs_outputs
)

logger = get_logger(__name__)

class LitecoinProcessor(TransactionProcessor):
    """پردازشگر وب‌هوک‌های مخصوص لایت‌کوین (LTC)"""
    
    def __init__(self):
        super().__init__()
        logger.info("پردازشگر لایت‌کوین راه‌اندازی شد")
    
    def process_webhook(self, webhook_data):
        """
        پردازش وب‌هوک لایت‌کوین
        این متد منطق خاص لایت‌کوین را اجرا می‌کند
        
        Args:
            webhook_data (dict): داده‌های وب‌هوک دریافتی
            
        Returns:
            dict: نتیجه پردازش
        """
        logger.info("پردازش وب‌هوک لایت‌کوین")
        
        # نرمال‌سازی داده‌های وب‌هوک
        self._normalize_webhook_data(webhook_data)
        
        # بررسی داده‌های ورودی تراکنش (در لایت‌کوین معمولاً وجود ندارد)
        input_data = webhook_data.get('input', '')
        if input_data:
            parsed_data = parse_ltc_input_data(input_data)
            webhook_data['ltc_input_data'] = parsed_data
        
        # محاسبه کارمزد تراکنش اگر اطلاعات آن موجود باشد
        if 'size' in webhook_data and 'feeRate' in webhook_data:
            try:
                tx_size = webhook_data.get('size')
                fee_rate = webhook_data.get('feeRate')
                fee = calculate_ltc_fee(tx_size, fee_rate)
                webhook_data['fee'] = fee
                logger.info(f"کارمزد محاسبه شده برای تراکنش: {fee} LTC")
            except Exception as e:
                logger.error(f"خطا در محاسبه کارمزد: {str(e)}")
                
                # استفاده از کارمزد پیش‌فرض در صورت خطا
                webhook_data['fee'] = calculate_ltc_fee()
        else:
            # استفاده از کارمزد پیش‌فرض اگر اطلاعات کافی نباشد
            webhook_data['fee'] = calculate_ltc_fee()
        
        # تنظیم نوع دارایی (در لایت‌کوین فقط انتقال ارز اصلی است)
        webhook_data['asset_type'] = 'native'
        
        # افزودن اطلاعات تکمیلی به داده‌های وب‌هوک
        webhook_data['chain'] = 'litecoin'
        if 'currency' not in webhook_data:
            webhook_data['currency'] = 'ltc'
        
        # تبدیل مقدار به فرمت صحیح
        if 'amount' in webhook_data and 'valueIn' in webhook_data:
            # این حالت برای تراکنش‌های ورودی است
            webhook_data['amount'] = litoshi_to_ltc(float(webhook_data.get('valueIn', 0)))
        elif 'amount' in webhook_data and isinstance(webhook_data['amount'], str):
            try:
                # تبدیل مقدار به عدد اعشاری
                amount = float(webhook_data['amount'])
                
                # اگر مقدار بزرگ است، احتمالاً در واحد لایتوشی است
                if amount > 1e7:  # احتمالاً در واحد لایتوشی است
                    amount = litoshi_to_ltc(amount)
                    webhook_data['amount'] = str(amount)
            except (ValueError, TypeError):
                pass
        
        # استخراج ورودی‌ها و خروجی‌های تراکنش
        if 'vin' in webhook_data or 'vout' in webhook_data:
            inputs, outputs = extract_tx_inputs_outputs(webhook_data)
            webhook_data['inputs'] = inputs
            webhook_data['outputs'] = outputs
            
            # تعیین آدرس فرستنده و گیرنده از ورودی‌ها و خروجی‌ها اگر مشخص نباشند
            if not webhook_data.get('from') and inputs:
                # آدرس فرستنده اولین ورودی است
                webhook_data['from'] = inputs[0].get('address', '')
            
            if not webhook_data.get('to') and outputs:
                # آدرس گیرنده اولین خروجی است (به جز خروجی change)
                for output in outputs:
                    if output.get('address') != webhook_data.get('from'):
                        webhook_data['to'] = output.get('address', '')
                        break
                
                # اگر هنوز آدرس گیرنده نداریم، فقط اولین خروجی را استفاده می‌کنیم
                if not webhook_data.get('to') and outputs:
                    webhook_data['to'] = outputs[0].get('address', '')
            
        # فراخوانی پردازشگر اصلی
        return super().process_webhook(webhook_data)
    
    def _normalize_webhook_data(self, webhook_data):
        """
        نرمال‌سازی داده‌های وب‌هوک لایت‌کوین
        بعضی از فیلدها در وب‌هوک لایت‌کوین ممکن است با فرمت‌های مختلف ارسال شوند
        
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
            'toAddress': 'to',
            'to_address': 'to',
            'recipient': 'to',
            'value': 'amount',
            'txvalue': 'amount',
            'tx_value': 'amount'
        }
        
        for old_field, new_field in field_mappings.items():
            if old_field in webhook_data and new_field not in webhook_data:
                webhook_data[new_field] = webhook_data[old_field]
        
        # بررسی ساختار خاص وب‌هوک لایت‌کوین
        # در بعضی وب‌هوک‌ها، اطلاعات فرستنده و گیرنده در آرایه‌های 'vin' و 'vout' ذخیره می‌شود
        if 'vin' in webhook_data and isinstance(webhook_data['vin'], list) and len(webhook_data['vin']) > 0:
            first_input = webhook_data['vin'][0]
            if 'addr' in first_input:
                webhook_data['from'] = first_input['addr']
            elif 'address' in first_input:
                webhook_data['from'] = first_input['address']
        
        if 'vout' in webhook_data and isinstance(webhook_data['vout'], list) and len(webhook_data['vout']) > 0:
            for vout in webhook_data['vout']:
                # جستجو برای یافتن آدرس گیرنده در خروجی‌ها
                address = None
                
                if 'scriptPubKey' in vout and 'addresses' in vout['scriptPubKey'] and isinstance(vout['scriptPubKey']['addresses'], list) and vout['scriptPubKey']['addresses']:
                    address = vout['scriptPubKey']['addresses'][0]
                elif 'addresses' in vout and isinstance(vout['addresses'], list) and vout['addresses']:
                    address = vout['addresses'][0]
                elif 'address' in vout:
                    address = vout['address']
                
                if address and address != webhook_data.get('from'):
                    webhook_data['to'] = address
                    if 'value' in vout:
                        webhook_data['amount'] = vout['value']
                    break
    
    def update_transaction(self, blockchain, tx_hash):
        """
        به‌روزرسانی تراکنش لایت‌کوین
        
        Args:
            blockchain (str): نام بلاکچین
            tx_hash (str): هش تراکنش
            
        Returns:
            dict: نتیجه به‌روزرسانی
        """
        logger.info(f"به‌روزرسانی تراکنش لایت‌کوین: {tx_hash}")
        
        # فراخوانی متد اصلی
        return super().update_transaction(blockchain, tx_hash)
    
    def _process_address_transaction(self, blockchain, from_address, to_address, value, transaction_id, webhook_data):
        """
        پردازش تراکنش آدرس لایت‌کوین
        
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
        logger.info(f"پردازش تراکنش آدرس لایت‌کوین: {transaction_id}")
        
        # بررسی اعتبار آدرس گیرنده
        if not is_valid_ltc_address(to_address):
            logger.warning(f"آدرس لایت‌کوین نامعتبر: {to_address}")
        
        # فرمت‌بندی آدرس‌ها
        formatted_from = format_ltc_address(from_address)
        formatted_to = format_ltc_address(to_address)
        
        # بازنویسی اطلاعات با آدرس‌های فرمت شده
        if formatted_from:
            webhook_data['from'] = formatted_from
        if formatted_to:
            webhook_data['to'] = formatted_to
            
        # فراخوانی متد اصلی
        return super()._process_address_transaction(blockchain, formatted_from, formatted_to, value, transaction_id, webhook_data)
    
    def _process_contract_event(self, blockchain, webhook_data, transaction_id):
        """
        پردازش رویداد قرارداد لایت‌کوین
        (لایت‌کوین قرارداد هوشمند ندارد، اما برای سازگاری با API پیاده‌سازی می‌شود)
        
        Args:
            blockchain (str): نام بلاکچین
            webhook_data (dict): داده‌های وب‌هوک
            transaction_id (str): شناسه تراکنش
            
        Returns:
            dict: نتیجه پردازش
        """
        logger.info(f"پردازش رویداد قرارداد لایت‌کوین: {transaction_id}")
        logger.warning("لایت‌کوین قرارداد هوشمند پشتیبانی نمی‌کند")
        
        # فراخوانی متد اصلی
        return super()._process_contract_event(blockchain, webhook_data, transaction_id) 