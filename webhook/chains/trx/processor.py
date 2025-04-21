from webhook.transaction_processor import TransactionProcessor
from utils.logging_config import get_logger
from webhook.chains.trx.utils import parse_tron_contract_data

logger = get_logger(__name__)

class TronProcessor(TransactionProcessor):
    """پردازشگر وب‌هوک‌های مخصوص ترون"""
    
    def __init__(self):
        super().__init__()
        logger.info("پردازشگر ترون راه‌اندازی شد")
    
    def process_webhook(self, webhook_data):
        """
        پردازش وب‌هوک ترون
        این متد می‌تواند منطق خاص ترون را اجرا کند
        
        Args:
            webhook_data (dict): داده‌های وب‌هوک دریافتی
            
        Returns:
            dict: نتیجه پردازش
        """
        logger.info("پردازش وب‌هوک ترون")
        
        # پردازش داده‌های قرارداد ترون
        contract_data = webhook_data.get('contractData')
        contract_type = webhook_data.get('contractType')
        
        if contract_data and contract_type:
            parsed_data = parse_tron_contract_data(contract_data, contract_type)
            webhook_data['tron_parsed_data'] = parsed_data
            
            # استفاده از داده‌های تجزیه شده برای افزودن اطلاعات به وب‌هوک
            if parsed_data.get('token_transfer') and 'amount' not in webhook_data:
                webhook_data['amount'] = parsed_data.get('amount')
                
            if parsed_data.get('to_address') and 'to' not in webhook_data:
                webhook_data['to'] = parsed_data.get('to_address')
                
            if parsed_data.get('from_address') and 'from' not in webhook_data:
                webhook_data['from'] = parsed_data.get('from_address')
        
        # تطبیق فرمت آدرس‌های ترون (تبدیل Base58 به Hex و بالعکس در صورت نیاز)
        if 'from' in webhook_data and webhook_data['from'] and webhook_data['from'].startswith('T'):
            logger.debug(f"آدرس فرستنده ترون: {webhook_data['from']}")
            
        if 'to' in webhook_data and webhook_data['to'] and webhook_data['to'].startswith('T'):
            logger.debug(f"آدرس گیرنده ترون: {webhook_data['to']}")
        
        # افزودن اطلاعات تکمیلی به داده‌های وب‌هوک
        webhook_data['chain'] = 'tron'
        if 'currency' not in webhook_data:
            webhook_data['currency'] = 'trx'
            
        # فراخوانی پردازشگر اصلی
        return super().process_webhook(webhook_data)
    
    def update_transaction(self, blockchain, tx_hash):
        """
        به‌روزرسانی تراکنش ترون
        
        Args:
            blockchain (str): نام بلاکچین
            tx_hash (str): هش تراکنش
            
        Returns:
            dict: نتیجه به‌روزرسانی
        """
        logger.info(f"به‌روزرسانی تراکنش ترون: {tx_hash}")
        
        # فراخوانی متد اصلی
        return super().update_transaction(blockchain, tx_hash) 