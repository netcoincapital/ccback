import os
import pika

RABBITMQ_CONFIG = {
    'host': os.getenv('RABBITMQ_HOST', 'localhost'),
    'port': int(os.getenv('RABBITMQ_PORT', 5672)),
    'username': os.getenv('RABBITMQ_USER', 'guest'),
    'password': os.getenv('RABBITMQ_PASSWORD', 'guest')
}

def get_rabbitmq_connection():
    credentials = pika.PlainCredentials(
        RABBITMQ_CONFIG['username'],
        RABBITMQ_CONFIG['password']
    )
    parameters = pika.ConnectionParameters(
        host=RABBITMQ_CONFIG['host'],
        port=RABBITMQ_CONFIG['port'],
        credentials=credentials
    )
    return pika.BlockingConnection(parameters) 