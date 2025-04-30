import json
from config.queue import get_rabbitmq_connection
from services.wallet_service import WalletService
from database import SessionLocal
from datetime import timedelta
import logging
from config.cache import redis_client

def process_wallet_generation(ch, method, properties, body):
    data = json.loads(body)
    session = SessionLocal()
    
    try:
        wallet_service = WalletService(session)
        
        # Get IP and device info from the message if available
        user_ip = data.get('user_ip', None)
        user_device = data.get('user_device', None)
        wallet_name = data.get('wallet_name', 'Unnamed Wallet')
        
        # Create wallet with IP and device info
        user_id, mnemonic, addresses = wallet_service.create_wallet(
            wallet_name, 
            5, 
            user_ip, 
            user_device
        )
        
        # ذخیره نتیجه در Redis برای بازیابی بعدی
        redis_client.setex(
            f"wallet_result:{data['task_id']}",
            timedelta(hours=1),
            json.dumps({
                'UserID': user_id,
                'Mnemonic': mnemonic,
                'Addresses': addresses,
                'success': True
            })
        )
        
        logging.info(f"Wallet generated asynchronously for user {user_id}")
        
    except Exception as e:
        logging.error(f"Error processing wallet generation: {e}")
        # ذخیره خطا در Redis
        redis_client.setex(
            f"wallet_result:{data['task_id']}",
            timedelta(hours=1),
            json.dumps({
                'error': str(e),
                'success': False
            })
        )
    finally:
        session.close()
        ch.basic_ack(delivery_tag=method.delivery_tag)

def run_worker():
    connection = get_rabbitmq_connection()
    channel = connection.channel()
    
    channel.queue_declare(queue='wallet_generation')
    channel.basic_consume(
        queue='wallet_generation',
        on_message_callback=process_wallet_generation
    )
    
    print("Wallet worker is running...")
    channel.start_consuming()
