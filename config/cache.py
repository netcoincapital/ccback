import os
from redis import Redis

REDIS_CONFIG = {
    'host': os.getenv('REDIS_HOST', 'localhost'),
    'port': int(os.getenv('REDIS_PORT', 6379)),
    'db': int(os.getenv('REDIS_DB', 0)),
    'password': os.getenv('REDIS_PASSWORD', None)
}

redis_client = Redis(**REDIS_CONFIG)

# config/queue.py
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
