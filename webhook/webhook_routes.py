import logging
from flask import Blueprint, request, jsonify
from CC.utils.logging_config import get_logger
from CC.webhook.transaction_processor import TransactionProcessor
import uuid
import json
from datetime import datetime

# Chain-specific processors
from CC.webhook.chains.eth import processor as eth_processor
from CC.webhook.chains.btc import processor as btc_processor
from CC.webhook.chains.trx import processor as trx_processor
from CC.webhook.chains.matic import processor as matic_processor
from CC.webhook.chains.sol import processor as sol_processor
from CC.webhook.chains.xrp import processor as xrp_processor
from CC.webhook.chains.doge import processor as doge_processor
from CC.webhook.chains.ltc import processor as ltc_processor
from CC.webhook.chains.ada import processor as ada_processor
from CC.webhook.chains.bnb import processor as bnb_processor

# تنظیم لاگر
logger = get_logger(__file__)

# ایجاد Blueprint برای مسیرهای وب‌هوک
webhook_bp = Blueprint('webhook', __name__)

@webhook_bp.route('/webhook/tatum/transaction', methods=['POST'])
def handle_tatum_transaction():
    """
    دریافت و مدیریت وب‌هوک‌های تاتوم برای رویدادهای قرارداد هوشمند یا تراکنش‌های آدرس.
    """
    # تست قطعی - نوشتن در فایل
    with open('/tmp/webhook_test.log', 'a') as f:
        f.write(f"WEBHOOK RECEIVED AT {datetime.now()}\n")
    
    req_id = str(uuid.uuid4())[:8]  # ایجاد یک شناسه منحصر به فرد برای هر درخواست
    
    with open('/tmp/webhook_test.log', 'a') as f:
        f.write(f"Request ID: {req_id}\n")
    
    logger.info(f"[{req_id}] 🔥 وب‌هوک دریافت شد 🔥")
    
    with open('/tmp/webhook_test.log', 'a') as f:
        f.write(f"After logger.info\n")
    
    # بررسی وجود داده JSON در درخواست
    if not request.is_json:
        with open('/tmp/webhook_test.log', 'a') as f:
            f.write(f"Not JSON request\n")
        logger.error(f"[{req_id}] درخواست غیر-JSON دریافت شد")
        return jsonify({"ok": True}), 200  # فرمت پاسخ مورد انتظار تاتوم
    
    with open('/tmp/webhook_test.log', 'a') as f:
        f.write(f"JSON request OK\n")
    
    # دریافت داده‌های وب‌هوک
    webhook_data = request.json
    
    with open('/tmp/webhook_test.log', 'a') as f:
        f.write(f"Webhook data: {webhook_data}\n")
    
    try:
        # تشخیص بلاکچین از داده‌های وب‌هوک
        blockchain = webhook_data.get('chain', '').lower()
        currency = webhook_data.get('currency', '').lower()
        
        with open('/tmp/webhook_test.log', 'a') as f:
            f.write(f"Blockchain: {blockchain}, Currency: {currency}\n")
        
        # انتخاب پردازشگر مناسب بر اساس بلاکچین
        if blockchain == 'ethereum' or currency == 'eth':
            processor = eth_processor
        elif blockchain == 'bitcoin' or currency == 'btc':
            processor = btc_processor
        elif blockchain == 'tron' or currency == 'trx':
            processor = trx_processor
        elif blockchain == 'polygon' or currency == 'matic':
            processor = matic_processor
            with open('/tmp/webhook_test.log', 'a') as f:
                f.write(f"Selected matic_processor\n")
        elif blockchain == 'solana' or currency == 'sol':
            processor = sol_processor
        elif blockchain == 'ripple' or currency == 'xrp':
            processor = xrp_processor
        elif blockchain == 'dogecoin' or currency == 'doge':
            processor = doge_processor
        elif blockchain == 'litecoin' or currency == 'ltc':
            processor = ltc_processor
        elif blockchain == 'cardano' or currency == 'ada':
            processor = ada_processor
        elif blockchain == 'binance smart chain' or currency == 'bnb':
            # استفاده از پردازشگر مخصوص Binance Smart Chain
            processor = bnb_processor
        else:
            # در صورت عدم تشخیص بلاکچین، از پردازشگر پیش‌فرض استفاده می‌کنیم
            logger.warning(f"[{req_id}] بلاکچین ناشناخته: {blockchain}/{currency}، استفاده از پردازشگر پیش‌فرض")
            processor = TransactionProcessor()
            with open('/tmp/webhook_test.log', 'a') as f:
                f.write(f"Using default processor\n")
        
        with open('/tmp/webhook_test.log', 'a') as f:
            f.write(f"About to call processor.process_webhook\n")
        
        # پردازش وب‌هوک و دریافت نتیجه
        result = processor.process_webhook(webhook_data)
        
        with open('/tmp/webhook_test.log', 'a') as f:
            f.write(f"Processor result: {result}\n")
        logger.info(f"[{req_id}] نتیجه پردازش: {json.dumps(result, ensure_ascii=False)}")
        
        # پاسخ به درخواست در فرمت مورد انتظار تاتوم
        response = {"ok": True}
        logger.info(f"[{req_id}] پاسخ ارسالی: {json.dumps(response, ensure_ascii=False)}")
        return jsonify(response), 200
        
    except Exception as e:
        logger.error(f"[{req_id}] خطا در پردازش وب‌هوک: {str(e)}", exc_info=True)
        # حتی در صورت خطا، فرمت پاسخ مورد انتظار تاتوم را برمی‌گردانیم
        return jsonify({"ok": True}), 200

@webhook_bp.route('/webhook/update-transaction/<blockchain>/<tx_hash>', methods=['GET'])
def manual_update_transaction(blockchain, tx_hash):
    """
    به روزرسانی دستی اطلاعات تراکنش.
    """
    try:
        # انتخاب پردازشگر مناسب بر اساس بلاکچین
        if blockchain.lower() == 'ethereum' or blockchain.lower() == 'eth':
            processor = eth_processor
        elif blockchain.lower() == 'bitcoin' or blockchain.lower() == 'btc':
            processor = btc_processor
        elif blockchain.lower() == 'tron' or blockchain.lower() == 'trx':
            processor = trx_processor
        elif blockchain.lower() == 'polygon' or blockchain.lower() == 'matic':
            processor = matic_processor
        elif blockchain.lower() == 'solana' or blockchain.lower() == 'sol':
            processor = sol_processor
        elif blockchain.lower() == 'ripple' or blockchain.lower() == 'xrp':
            processor = xrp_processor
        elif blockchain.lower() == 'dogecoin' or blockchain.lower() == 'doge':
            processor = doge_processor
        elif blockchain.lower() == 'litecoin' or blockchain.lower() == 'ltc':
            processor = ltc_processor
        elif blockchain.lower() == 'cardano' or blockchain.lower() == 'ada':
            processor = ada_processor
        elif blockchain.lower() == 'binance smart chain' or blockchain.lower() == 'bnb':
            # استفاده از پردازشگر مخصوص Binance Smart Chain
            processor = bnb_processor
        else:
            # در صورت عدم تشخیص بلاکچین، از پردازشگر پیش‌فرض استفاده می‌کنیم
            logger.warning(f"بلاکچین ناشناخته: {blockchain}، استفاده از پردازشگر پیش‌فرض")
            processor = TransactionProcessor()
            
        result = processor.update_transaction(blockchain, tx_hash)
        return jsonify(result), 200
    except Exception as e:
        logger.error(f"خطا در به‌روزرسانی دستی تراکنش: {str(e)}", exc_info=True)
        return jsonify({"status": "خطا", "message": str(e)}), 500

@webhook_bp.route('/webhook/test', methods=['GET'])
def test_webhook():
    """
    نقطه پایانی ساده برای بررسی صحت ثبت مسیرهای وب‌هوک
    """
    logger.info("نقطه پایانی تست وب‌هوک فراخوانی شد")
    return jsonify({
        "status": "موفق",
        "message": "مسیرهای وب‌هوک به درستی کار می‌کنند",
        "timestamp": datetime.now().isoformat()
    })

@webhook_bp.route('/webhook/test-tatum', methods=['GET', 'POST'])
def test_tatum_format():
    """
    نقطه پایانی برای تست فرمت پاسخ تاتوم
    """
    logger.info("نقطه پایانی تست فرمت تاتوم فراخوانی شد")
    # پاسخ در فرمت مورد انتظار تاتوم
    return jsonify({"ok": True}), 200 