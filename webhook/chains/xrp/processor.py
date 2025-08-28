from CC.webhook.transaction_processor import TransactionProcessor
from CC.utils.logging_config import get_logger
from CC.webhook.chains.xrp.utils import (
    parse_xrp_input_data,
    format_xrp_address,
    is_valid_xrp_address,
    calculate_xrp_fee,
    drops_to_xrp,
    xrp_to_drops,
    extract_transaction_type,
    extract_destination_tag
)

logger = get_logger(__name__)

class RippleProcessor(TransactionProcessor):
    """پردازشگر وب‌هوک‌های مخصوص ریپل (XRP)"""
    
    def __init__(self):
        super().__init__()
        logger.info("پردازشگر ریپل راه‌اندازی شد")
    
    def process_webhook(self, webhook_data):
        """
        پردازش وب‌هوک ریپل
        این متد منطق خاص ریپل را اجرا می‌کند
        
        Args:
            webhook_data (dict): داده‌های وب‌هوک دریافتی
            
        Returns:
            dict: نتیجه پردازش
        """
        logger.info("پردازش وب‌هوک ریپل")
        
        # نرمال‌سازی داده‌های وب‌هوک
        self._normalize_webhook_data(webhook_data)
        
        # استخراج نوع تراکنش ریپل
        transaction_type = extract_transaction_type(webhook_data)
        webhook_data['transaction_type'] = transaction_type
        
        # بررسی داده‌های ورودی تراکنش
        # در ریپل، به جای input_data معمولاً از TransactionType استفاده می‌شود
        input_data = webhook_data.get('input', transaction_type)
        parsed_data = parse_xrp_input_data(input_data)
        webhook_data['xrp_input_data'] = parsed_data
        
        # محاسبه کارمزد تراکنش
        fee_drops = webhook_data.get('Fee')
        fee = calculate_xrp_fee(fee_drops)
        webhook_data['fee'] = fee
        logger.info(f"کارمزد محاسبه شده برای تراکنش: {fee} XRP")
        
        # استخراج تگ مقصد (Destination Tag) - ویژگی خاص ریپل
        destination_tag = extract_destination_tag(webhook_data)
        if destination_tag is not None:
            webhook_data['destination_tag'] = destination_tag
            logger.info(f"تگ مقصد: {destination_tag}")
        
        # تنظیم نوع دارایی (توکن یا ارز اصلی)
        # در ریپل، تراکنش‌های Payment می‌توانند XRP یا توکن‌های دیگر باشند
        if 'Currency' in webhook_data and webhook_data['Currency'] != 'XRP':
            webhook_data['asset_type'] = 'token'
            webhook_data['token'] = webhook_data['Currency']
        else:
            webhook_data['asset_type'] = 'native'
        
        # افزودن اطلاعات تکمیلی به داده‌های وب‌هوک
        webhook_data['chain'] = 'ripple'
        if 'currency' not in webhook_data:
            webhook_data['currency'] = 'xrp'
        
        # تبدیل مقدار به فرمت صحیح
        if 'Amount' in webhook_data:
            try:
                # در ریپل، مقدار می‌تواند عدد یا یک شیء JSON باشد
                amount = webhook_data['Amount']
                if isinstance(amount, str) and amount.isdigit():
                    # اگر مقدار یک رشته عددی است، آن را به XRP تبدیل می‌کنیم
                    webhook_data['amount'] = drops_to_xrp(amount)
                elif isinstance(amount, dict) and 'value' in amount:
                    # اگر مقدار یک شیء است، این توکن است (نه XRP)
                    webhook_data['amount'] = float(amount['value'])
                    webhook_data['token'] = amount.get('currency', 'UNKNOWN')
                    webhook_data['asset_type'] = 'token'
            except (ValueError, TypeError) as e:
                logger.error(f"خطا در تبدیل مقدار: {str(e)}")
                
        # فراخوانی پردازشگر اصلی
        return super().process_webhook(webhook_data)
    
    def _normalize_webhook_data(self, webhook_data):
        """
        نرمال‌سازی داده‌های وب‌هوک ریپل
        بعضی از فیلدها در وب‌هوک ریپل با نام‌های مختلفی ارسال می‌شوند
        
        Args:
            webhook_data (dict): داده‌های وب‌هوک دریافتی
        """
        # استاندارد کردن نام‌های فیلدها
        field_mappings = {
            'hash': 'hash',
            'tx_hash': 'hash',
            'transaction_hash': 'hash',
            'txid': 'hash',
            'TransactionHash': 'hash',
            'ledger_index': 'blockNumber',
            'LedgerIndex': 'blockNumber',
            'ledger': 'blockNumber',
            'Account': 'from',
            'account': 'from',
            'from_account': 'from',
            'source_account': 'from',
            'Destination': 'to',
            'destination': 'to',
            'to_account': 'to',
            'dest': 'to',
            'Amount': 'Amount',  # نگه داشتن نام اصلی برای پردازش بیشتر
            'amount': 'Amount',
            'value': 'Amount',
            'Fee': 'Fee',  # نگه داشتن نام اصلی برای پردازش بیشتر
            'fee': 'Fee',
            'tx_fee': 'Fee'
        }
        
        for old_field, new_field in field_mappings.items():
            if old_field in webhook_data and new_field not in webhook_data:
                webhook_data[new_field] = webhook_data[old_field]
        
        # اطمینان از وجود مقدار در فرمت صحیح
        if 'Amount' in webhook_data and isinstance(webhook_data['Amount'], str) and webhook_data['Amount'].isdigit():
            # تبدیل مقدار به فرمت استاندارد XRP
            try:
                webhook_data['amount'] = drops_to_xrp(webhook_data['Amount'])
            except (ValueError, TypeError):
                pass
    
    def update_transaction(self, blockchain, tx_hash):
        """
        به‌روزرسانی تراکنش ریپل
        
        Args:
            blockchain (str): نام بلاکچین
            tx_hash (str): هش تراکنش
            
        Returns:
            dict: نتیجه به‌روزرسانی
        """
        logger.info(f"به‌روزرسانی تراکنش ریپل: {tx_hash}")
        
        # فراخوانی متد اصلی
        return super().update_transaction(blockchain, tx_hash)
    
    def _process_address_transaction(self, blockchain, from_address, to_address, value, transaction_id, webhook_data):
        """
        پردازش تراکنش آدرس ریپل
        
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
        logger.info(f"پردازش تراکنش آدرس ریپل: {transaction_id}")
        
        # بررسی اعتبار آدرس گیرنده
        if not is_valid_xrp_address(to_address):
            logger.warning(f"آدرس ریپل نامعتبر: {to_address}")
        
        # فرمت‌بندی آدرس‌ها
        formatted_from = format_xrp_address(from_address)
        formatted_to = format_xrp_address(to_address)
        
        # بازنویسی اطلاعات با آدرس‌های فرمت شده
        if formatted_from:
            webhook_data['from'] = formatted_from
        if formatted_to:
            webhook_data['to'] = formatted_to
            
        # افزودن تگ مقصد به داده‌های تراکنش اگر وجود داشته باشد
        if 'destination_tag' in webhook_data:
            logger.info(f"تراکنش با تگ مقصد: {webhook_data['destination_tag']}")
            
        # فراخوانی متد اصلی
        return super()._process_address_transaction(blockchain, formatted_from, formatted_to, value, transaction_id, webhook_data)
    
    def _process_contract_event(self, blockchain, webhook_data, transaction_id):
        """
        پردازش رویداد قرارداد ریپل
        (ریپل به طور دقیق قراردادهای هوشمند مانند اتریوم ندارد،
        اما برای سازگاری با API و پشتیبانی از تراکنش‌های پیچیده‌تر پیاده‌سازی می‌شود)
        
        Args:
            blockchain (str): نام بلاکچین
            webhook_data (dict): داده‌های وب‌هوک
            transaction_id (str): شناسه تراکنش
            
        Returns:
            dict: نتیجه پردازش
        """
        logger.info(f"پردازش رویداد خاص ریپل: {transaction_id}")
        
        # بررسی نوع تراکنش
        transaction_type = webhook_data.get('transaction_type', 'Unknown')
        logger.info(f"نوع تراکنش ریپل: {transaction_type}")
        
        # پردازش انواع مختلف تراکنش‌های ریپل
        if transaction_type in ['OfferCreate', 'OfferCancel', 'TrustSet', 'EscrowCreate', 'EscrowFinish', 'EscrowCancel']:
            logger.info(f"پردازش تراکنش ویژه ریپل: {transaction_type}")
            # در اینجا می‌توانید منطق خاص برای هر نوع تراکنش اضافه کنید
        
        # فراخوانی متد اصلی
        return super()._process_contract_event(blockchain, webhook_data, transaction_id) 