"""
Configuration package for IronWallet application
"""

from .cache import redis_client
from .queue import get_rabbitmq_connection
from .swagger import register_swagger, swagger_config
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Database URL for connection
DATABASE_URL = os.getenv('DATABASE_URL', "mysql+mysqlconnector://coincee:09387270277Mn!!??@localhost/coincee")

# Webhook base URL for Tatum notifications
# Make sure it starts with https:// or http://
WEBHOOK_BASE_URL = os.getenv('WEBHOOK_BASE_URL', 'https://coinceeper.com')
if WEBHOOK_BASE_URL and not WEBHOOK_BASE_URL.startswith(('http://', 'https://')):
    WEBHOOK_BASE_URL = 'https://' + WEBHOOK_BASE_URL

__all__ = [
    'redis_client',
    'get_rabbitmq_connection',
    'register_swagger',
    'swagger_config',
    'DATABASE_URL',
    'WEBHOOK_BASE_URL'
] 