from CC.webhook.transaction_processor import TransactionProcessor
from CC.utils.logging_config import get_logger

logger = get_logger(__name__)

class SolanaProcessor(TransactionProcessor):
    """پردازشگر وب‌هوک‌های مخصوص سولانا (SOL)"""
    
    def __init__(self):
        super().__init__()
        logger.info("پردازشگر سولانا راه‌اندازی شد")
    
    def process_webhook(self, webhook_data):
        """
        پردازش وب‌هوک سولانا
        این متد منطق خاص سولانا را اجرا می‌کند
        
        Args:
            webhook_data (dict): داده‌های وب‌هوک دریافتی
            
        Returns:
            dict: نتیجه پردازش
        """
        logger.info("پردازش وب‌هوک سولانا")
        
        # نرمال‌سازی داده‌های وب‌هوک
        self._normalize_webhook_data(webhook_data)
        
        # افزودن اطلاعات تکمیلی به داده‌های وب‌هوک
        webhook_data['chain'] = 'solana'
        if 'currency' not in webhook_data:
            webhook_data['currency'] = 'sol'
            
        # فراخوانی پردازشگر اصلی
        return super().process_webhook(webhook_data)
    
    def _normalize_webhook_data(self, webhook_data):
        """
        نرمال‌سازی داده‌های وب‌هوک سولانا
        بعضی از فیلدها در وب‌هوک سولانا ممکن است با فرمت‌های مختلف ارسال شوند
        
        Args:
            webhook_data (dict): داده‌های وب‌هوک دریافتی
        """
        # استاندارد کردن نام‌های فیلدها
        field_mappings = {
            'txid': 'hash',
            'transactionHash': 'hash',
            'signature': 'hash',
            'blockNumber': 'blockNumber',
            'slot': 'blockNumber',
            'blockHeight': 'blockNumber',
            'blockHash': 'blockHash',
            'fromAddress': 'from',
            'from_address': 'from',
            'sender': 'from',
            'toAddress': 'to',
            'to_address': 'to',
            'recipient': 'to',
            'value': 'amount',
            'lamports': 'amount'
        }
        
        for old_field, new_field in field_mappings.items():
            if old_field in webhook_data and new_field not in webhook_data:
                webhook_data[new_field] = webhook_data[old_field]
        
        # اطمینان از وجود مقدار در فرمت صحیح
        if 'amount' in webhook_data and isinstance(webhook_data['amount'], str):
            try:
                # تبدیل مقدار به عدد اعشاری
                amount = float(webhook_data['amount'])
                
                # اگر مقدار برای SOL در واحد lamports است، آن را به SOL تبدیل کنیم
                if amount > 1e8:  # احتمالاً در واحد lamports است
                    amount = amount / 1e9
                    webhook_data['amount'] = str(amount)
            except (ValueError, TypeError):
                pass
    
    def update_transaction(self, blockchain, tx_hash):
        """
        به‌روزرسانی تراکنش سولانا
        
        Args:
            blockchain (str): نام بلاکچین
            tx_hash (str): هش تراکنش
            
        Returns:
            dict: نتیجه به‌روزرسانی
        """
        logger.info(f"به‌روزرسانی تراکنش سولانا: {tx_hash}")
        
        # فراخوانی متد اصلی
        return super().update_transaction(blockchain, tx_hash)
    
    def _process_address_transaction(self, blockchain, from_address, to_address, value, transaction_id, webhook_data):
        """
        پردازش تراکنش آدرس سولانا
        
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
        logger.info(f"پردازش تراکنش آدرس سولانا: {transaction_id}")
        
        # فراخوانی متد اصلی
        return super()._process_address_transaction(blockchain, from_address, to_address, value, transaction_id, webhook_data)
    
    def _process_contract_event(self, blockchain, webhook_data, transaction_id):
        """
        پردازش رویداد قرارداد سولانا
        
        Args:
            blockchain (str): نام بلاکچین
            webhook_data (dict): داده‌های وب‌هوک
            transaction_id (str): شناسه تراکنش
            
        Returns:
            dict: نتیجه پردازش
        """
        logger.info(f"پردازش رویداد قرارداد سولانا: {transaction_id}")
        
        # فراخوانی متد اصلی
        return super()._process_contract_event(blockchain, webhook_data, transaction_id) 