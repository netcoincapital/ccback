from CC.webhook.transaction_processor import TransactionProcessor
from CC.utils.logging_config import get_logger
from CC.webhook.chains.arb.utils import parse_arb_input_data, calculate_arb_fee, is_token_transfer

logger = get_logger(__name__)

class ArbitrumProcessor(TransactionProcessor):
    """پردازشگر وب‌هوک‌های مخصوص آربیتروم (ARB)"""
    
    def __init__(self):
        super().__init__()
        logger.info("پردازشگر آربیتروم راه‌اندازی شد")
    
    def process_webhook(self, webhook_data):
        """
        پردازش وب‌هوک آربیتروم
        این متد منطق خاص آربیتروم را اجرا می‌کند
        
        Args:
            webhook_data (dict): داده‌های وب‌هوک دریافتی
            
        Returns:
            dict: نتیجه پردازش
        """
        logger.info("پردازش وب‌هوک آربیتروم")
        
        # نرمال‌سازی داده‌های وب‌هوک
        self._normalize_webhook_data(webhook_data)
        
        # بررسی داده‌های ورودی تراکنش برای تشخیص نوع عملیات
        input_data = webhook_data.get('input')
        if input_data and len(input_data) > 10:
            parsed_data = parse_arb_input_data(input_data)
            webhook_data['arb_input_data'] = parsed_data
            
            # بررسی نوع تراکنش
            if parsed_data.get('type') == 'token_transfer':
                logger.info(f"تراکنش انتقال توکن شناسایی شد: {webhook_data.get('hash', '')}")
                
                # افزودن اطلاعات توکن به داده‌های وب‌هوک
                contract_address = webhook_data.get('to')
                if contract_address:
                    webhook_data['token_contract'] = contract_address
                
        # محاسبه کارمزد تراکنش - آربیتروم کارمزد کمتری نسبت به اتریوم دارد
        if 'gasPrice' in webhook_data and 'gasUsed' in webhook_data:
            try:
                gas_price = webhook_data.get('gasPrice')
                gas_used = webhook_data.get('gasUsed')
                fee = calculate_arb_fee(gas_price, gas_used)
                webhook_data['fee'] = fee
                logger.info(f"کارمزد محاسبه شده برای تراکنش: {fee} ETH")
            except Exception as e:
                logger.error(f"خطا در محاسبه کارمزد: {str(e)}")
        
        # تنظیم نوع دارایی (توکن یا ارز اصلی)
        if is_token_transfer(webhook_data.get('input', '')):
            webhook_data['asset_type'] = 'token'
        else:
            webhook_data['asset_type'] = 'native'
        
        # افزودن اطلاعات تکمیلی به داده‌های وب‌هوک
        webhook_data['chain'] = 'arbitrum'
        if 'currency' not in webhook_data:
            webhook_data['currency'] = 'arb'
            
        # فراخوانی پردازشگر اصلی
        return super().process_webhook(webhook_data)
    
    def _normalize_webhook_data(self, webhook_data):
        """
        نرمال‌سازی داده‌های وب‌هوک آربیتروم
        بعضی از فیلدها در وب‌هوک آربیتروم ممکن است با فرمت‌های مختلف ارسال شوند
        
        Args:
            webhook_data (dict): داده‌های وب‌هوک دریافتی
        """
        # استاندارد کردن نام‌های فیلدها
        field_mappings = {
            'txid': 'hash',
            'transactionHash': 'hash',
            'transaction_hash': 'hash',
            'blockNumber': 'blockNumber',
            'block_number': 'blockNumber',
            'blockHash': 'blockHash',
            'block_hash': 'blockHash',
            'fromAddress': 'from',
            'from_address': 'from',
            'sender': 'from',
            'toAddress': 'to',
            'to_address': 'to',
            'recipient': 'to',
            'value': 'amount'
        }
        
        for old_field, new_field in field_mappings.items():
            if old_field in webhook_data and new_field not in webhook_data:
                webhook_data[new_field] = webhook_data[old_field]
        
        # اطمینان از وجود مقدار در فرمت صحیح
        if 'amount' in webhook_data and isinstance(webhook_data['amount'], str):
            try:
                # تبدیل مقدار به عدد اعشاری
                amount = float(webhook_data['amount'])
                
                # اگر مقدار برای ARB در واحد wei است، آن را به ETH تبدیل کنیم
                if amount > 1e10:  # احتمالاً در واحد wei است
                    amount = amount / 1e18
                    webhook_data['amount'] = str(amount)
            except (ValueError, TypeError):
                pass
    
    def update_transaction(self, blockchain, tx_hash):
        """
        به‌روزرسانی تراکنش آربیتروم
        
        Args:
            blockchain (str): نام بلاکچین
            tx_hash (str): هش تراکنش
            
        Returns:
            dict: نتیجه به‌روزرسانی
        """
        logger.info(f"به‌روزرسانی تراکنش آربیتروم: {tx_hash}")
        
        # فراخوانی متد اصلی
        return super().update_transaction(blockchain, tx_hash)
    
    def _process_address_transaction(self, blockchain, from_address, to_address, value, transaction_id, webhook_data):
        """
        پردازش تراکنش آدرس آربیتروم
        
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
        logger.info(f"پردازش تراکنش آدرس آربیتروم: {transaction_id}")
        
        # فراخوانی متد اصلی
        return super()._process_address_transaction(blockchain, from_address, to_address, value, transaction_id, webhook_data)
    
    def _process_contract_event(self, blockchain, webhook_data, transaction_id):
        """
        پردازش رویداد قرارداد آربیتروم
        
        Args:
            blockchain (str): نام بلاکچین
            webhook_data (dict): داده‌های وب‌هوک
            transaction_id (str): شناسه تراکنش
            
        Returns:
            dict: نتیجه پردازش
        """
        logger.info(f"پردازش رویداد قرارداد آربیتروم: {transaction_id}")
        
        # فراخوانی متد اصلی
        return super()._process_contract_event(blockchain, webhook_data, transaction_id) 