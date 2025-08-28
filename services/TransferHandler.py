from CC.database import SessionLocal, Transfers
import json
import logging
from CC.utils.logging_config import get_logger
import traceback

# Configure logging
logger = get_logger(__file__)

def on_new_transfer(transfer_id: int):
    """
    Handle a new transfer by updating the user's holdings
    
    Args:
        transfer_id: ID of the newly created transfer
    """
    # Move import inside function to avoid circular imports
    from services.balance_service import BalanceService
    
    session = SessionLocal()
    try:
        service = BalanceService(session)

        # Get the transfer from the database
        transfer = session.query(Transfers).filter(Transfers.TransferID == transfer_id).first()
        if not transfer:
            logger.warning(f"Transfer with ID {transfer_id} not found")
            return
            
        # Apply the transfer to update user holdings
        logger.info(f"Applying transfer {transfer_id} to user holdings")
        service.apply_transfer_to_user_holding(transfer)
        
        logger.info(f"Successfully processed transfer {transfer_id}")
    except Exception as e:
        error_details = traceback.format_exc()
        logger.error(f"Error processing transfer {transfer_id}: {str(e)}\n{error_details}")
    finally:
        session.close()

def handle_transfer_queue_message(ch, method, properties, body):
    """
    RabbitMQ message handler for the transfer queue
    
    Args:
        ch: Channel
        method: Method
        properties: Properties
        body: Message body
    """
    try:
        data = json.loads(body)
        transfer_id = data.get('transfer_id')
        
        if not transfer_id:
            logger.error("Transfer ID missing from message")
            ch.basic_ack(delivery_tag=method.delivery_tag)
            return
            
        on_new_transfer(transfer_id)
        
        # Acknowledge the message
        ch.basic_ack(delivery_tag=method.delivery_tag)
    except Exception as e:
        error_details = traceback.format_exc()
        logger.error(f"Error handling transfer message: {str(e)}\n{error_details}")
        # Still acknowledge to prevent message buildup in queue
        ch.basic_ack(delivery_tag=method.delivery_tag)

def register_transfer_created(transfer_id: int):
    """
    Register a newly created transfer for processing
    
    This function can be called when a new transfer is created in the database.
    It either processes the transfer directly or sends it to the queue for asynchronous processing.
    
    Args:
        transfer_id: ID of the newly created transfer
    """
    try:
        # Simplified implementation for debugging that just logs instead of using RabbitMQ
        logger.info(f"Transfer {transfer_id} registered for processing (direct mode)")
        on_new_transfer(transfer_id)
    except Exception as e:
        error_details = traceback.format_exc()
        logger.error(f"Error in register_transfer_created for {transfer_id}: {str(e)}\n{error_details}")

# Original implementation with RabbitMQ commented out for debugging
"""
def register_transfer_created(transfer_id: int):
    # Import here to avoid circular dependencies
    from config.queue import get_rabbitmq_connection
    
    try:
        # Try to send to RabbitMQ queue if available
        try:
            connection = get_rabbitmq_connection()
            channel = connection.channel()
            
            # Ensure the queue exists
            channel.queue_declare(queue='transfers', durable=True)
            
            # Send transfer ID to the queue
            channel.basic_publish(
                exchange='',
                routing_key='transfers',
                body=json.dumps({'transfer_id': transfer_id}),
                properties=None
            )
            
            connection.close()
            logger.info(f"Transfer {transfer_id} queued for processing")
            
        except Exception as e:
            logger.warning(f"Could not queue transfer {transfer_id}: {str(e)}. Processing synchronously.")
            # Fall back to synchronous processing
            on_new_transfer(transfer_id)
            
    except Exception as e:
        logger.error(f"Error in register_transfer_created for {transfer_id}: {str(e)}")
"""

def run_transfer_worker():
    """
    Start the transfer worker to process queued transfers
    
    This function should be called to start a worker process
    that listens for transfer messages and processes them.
    """
    # Import here to avoid circular dependencies
    from config.queue import get_rabbitmq_connection
    
    try:
        connection = get_rabbitmq_connection()
        channel = connection.channel()
        
        # Ensure the queue exists and is durable
        channel.queue_declare(queue='transfers', durable=True)
        
        # Set prefetch count to limit the number of unacknowledged messages
        channel.basic_qos(prefetch_count=1)
        
        # Set up the consumer
        channel.basic_consume(
            queue='transfers',
            on_message_callback=handle_transfer_queue_message
        )
        
        logger.info("Transfer worker started. Waiting for messages.")
        channel.start_consuming()
        
    except Exception as e:
        logger.error(f"Error starting transfer worker: {str(e)}") 