"""
Configuration package for IronWallet application
"""

from .cache import redis_client
from .queue import get_rabbitmq_connection
from .swagger import register_swagger, swagger_config

# Database URL from environment or default
import os
DATABASE_URL = os.getenv('DATABASE_URL', "mysql+mysqlconnector://root:Q#-76(12Kji09?@localhost/IronWallet")

__all__ = [
    'redis_client',
    'get_rabbitmq_connection',
    'register_swagger',
    'swagger_config',
    'DATABASE_URL'
] 