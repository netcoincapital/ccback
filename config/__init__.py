"""
Configuration package for IronWallet application
"""

from .cache import redis_client
from .queue import get_rabbitmq_connection
from .swagger import register_swagger, swagger_config
import os
from urllib.parse import quote_plus
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Build DATABASE_URL from individual env vars with URL-encoded password
# (The password contains special chars like ! and ? that break raw URL strings)
DB_USER = os.getenv('DB_USER', 'coincee')
DB_PASSWORD = os.getenv('DB_PASSWORD', '')
DB_HOST = os.getenv('DB_HOST', 'localhost')
DB_NAME = os.getenv('DB_NAME', 'coincee')
DB_DRIVER = os.getenv('DB_DRIVER', 'pymysql')

if DB_PASSWORD:
    DB_PASSWORD_ENCODED = quote_plus(DB_PASSWORD)
else:
    DB_PASSWORD_ENCODED = ''

DATABASE_URL = f"mysql+{DB_DRIVER}://{DB_USER}:{DB_PASSWORD_ENCODED}@{DB_HOST}/{DB_NAME}"

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

"""Config package initialization."""
