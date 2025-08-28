from typing import Optional
import re
from dataclasses import dataclass
import html
from flask import request, abort
import logging
from functools import wraps
import time
from datetime import datetime
import redis
from flask_wtf.csrf import CSRFProtect

# Redis connection
try:
    redis_client = redis.Redis(host='localhost', port=6379, db=0, socket_connect_timeout=1)
    # Test connection
    redis_client.ping()
    redis_available = True
    logging.info("Redis connection successful")
except (redis.RedisError, ConnectionError):
    logging.warning("Redis server is not available. Rate limiting will be disabled.")
    redis_available = False
    redis_client = None

@dataclass
class ValidationError(Exception):
    message: str
    status_code: int = 400

class SecurityUtils:
    @staticmethod
    def rate_limit(requests: int, window: int):
        """
        Rate limiting decorator
        requests: تعداد درخواست‌های مجاز
        window: پنجره زمانی به ثانیه
        """
        def decorator(f):
            @wraps(f)
            def wrapped(*args, **kwargs):
                # If Redis is not available, skip rate limiting
                if not redis_available:
                    return f(*args, **kwargs)
                    
                ip = request.remote_addr
                
                # Skip rate limiting for localhost
                if ip in ['127.0.0.1', 'localhost', '::1']:
                    return f(*args, **kwargs)
                    
                key = f"{ip}:{request.endpoint}"
                
                try:
                    # افزایش شمارنده در Redis
                    current = redis_client.get(key)
                    if current is None:
                        redis_client.setex(key, window, 1)
                    else:
                        if int(current) >= requests:
                            logging.warning(f"Rate limit exceeded for IP: {ip}")
                            return {"error": "Rate limit exceeded"}, 429
                        redis_client.incr(key)
                    
                    return f(*args, **kwargs)
                except redis.RedisError:
                    logging.error("Redis error in rate limiting")
                    return f(*args, **kwargs)
            return wrapped
        return decorator

    @staticmethod
    def log_failed_attempt(ip: str, endpoint: str, reason: str):
        """ثبت تلاش‌های ناموفق"""
        logging.warning(f"Failed attempt from IP: {ip}, Endpoint: {endpoint}, Reason: {reason}")
        if not redis_available:
            return
            
        try:
            key = f"failed_attempts:{ip}"
            redis_client.incr(key)
            redis_client.expire(key, 3600)  # منقضی شدن بعد از 1 ساعت
        except redis.RedisError:
            logging.error("Redis error in logging failed attempt")

class InputValidator:
    @staticmethod
    def validate_string(value: str, 
                       field_name: str, 
                       min_length: int = 1, 
                       max_length: int = 100,
                       pattern: Optional[str] = None) -> str:
        if not isinstance(value, str):
            raise ValidationError(f"{field_name} must be a string")
        
        value = value.strip()
        
        if len(value) < min_length:
            raise ValidationError(f"{field_name} must be at least {min_length} characters")
        if len(value) > max_length:
            raise ValidationError(f"{field_name} must be at most {max_length} characters")
            
        if pattern and not re.match(pattern, value):
            raise ValidationError(f"{field_name} contains invalid characters")
            
        return html.escape(value)

    @staticmethod
    def validate_blockchain_id(blockchain_id: int) -> int:
        if not isinstance(blockchain_id, int) or blockchain_id < 1:
            raise ValidationError("Invalid blockchain ID")
        return blockchain_id

    @staticmethod
    def validate_uuid(value: str, field_name: str) -> str:
        pattern = r'^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$'
        if not re.match(pattern, value.lower()):
            raise ValidationError(f"Invalid {field_name} format")
        return value 