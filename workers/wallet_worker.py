import json
from config.queue import get_rabbitmq_connection
from services.wallet_service import WalletService
from database import SessionLocal
from datetime import timedelta
import logging

def process_wallet_generation(ch, method, properties, body):
    data = json.loads(body)
    session = SessionLocal()
    
    try:
        wallet_service = WalletService(session)
        result = wallet_service.create_wallet(data['wallet_name'])
        
        # ذخیره نتیجه در Redis برای بازیابی بعدی
        redis_client.setex(
            f"wallet_result:{data['task_id']}",
            timedelta(hours=1),
            json.dumps(result)
        )
        
    except Exception as e:
        logging.error(f"Error processing wallet generation: {e}")
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
