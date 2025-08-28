"""
Configuration for Historical Data System
"""
import os
from datetime import timedelta

class HistoricalConfig:
    """Configuration settings for historical data collection"""
    
    # Scheduler settings
    UPDATE_INTERVAL_HOURS = int(os.getenv('HISTORICAL_UPDATE_INTERVAL_HOURS', '24'))
    MAX_CURRENCIES_PER_BATCH = int(os.getenv('HISTORICAL_MAX_CURRENCIES', '10'))
    DAYS_TO_FETCH_PER_UPDATE = int(os.getenv('HISTORICAL_DAYS_TO_FETCH', '7'))
    
    # API settings
    API_DELAY_BETWEEN_REQUESTS = float(os.getenv('HISTORICAL_API_DELAY', '2.0'))
    MAX_RETRIES = int(os.getenv('HISTORICAL_MAX_RETRIES', '3'))
    REQUEST_TIMEOUT = int(os.getenv('HISTORICAL_REQUEST_TIMEOUT', '30'))
    
    # Data retention settings
    KEEP_HISTORICAL_DATA_DAYS = int(os.getenv('HISTORICAL_RETENTION_DAYS', '365'))
    AUTO_CLEANUP_ENABLED = os.getenv('HISTORICAL_AUTO_CLEANUP', 'true').lower() == 'true'
    
    # Performance settings
    BATCH_SIZE_FOR_DB_OPERATIONS = int(os.getenv('HISTORICAL_DB_BATCH_SIZE', '100'))
    ENABLE_PARALLEL_PROCESSING = os.getenv('HISTORICAL_PARALLEL', 'false').lower() == 'true'
    
    # Plan-based limits
    PLAN_TYPE = os.getenv('CMC_PLAN_TYPE', 'hobbyist').lower()
    
    PLAN_LIMITS = {
        'hobbyist': {
            'max_months': 12,
            'monthly_credits': 110000,
            'max_calls_per_day': 3650  # ~110K/30 days
        },
        'startup': {
            'max_months': 24,
            'monthly_credits': 1000000,
            'max_calls_per_day': 33333
        },
        'standard': {
            'max_months': 60,
            'monthly_credits': 3000000,
            'max_calls_per_day': 100000
        }
    }
    
    @classmethod
    def get_plan_limits(cls):
        """Get limits for current plan"""
        return cls.PLAN_LIMITS.get(cls.PLAN_TYPE, cls.PLAN_LIMITS['hobbyist'])
    
    @classmethod
    def get_max_fetchable_months(cls):
        """Get maximum months that can be fetched with current plan"""
        return cls.get_plan_limits()['max_months']
    
    @classmethod
    def estimate_credit_usage(cls, currencies_count: int, days: int):
        """Estimate credit usage for a request"""
        # Each currency per day typically uses 1 credit
        return currencies_count * days
    
    @classmethod
    def validate_bulk_request(cls, currencies_count: int, months: int):
        """Validate if a bulk request is feasible with current plan"""
        max_months = cls.get_max_fetchable_months()
        plan_limits = cls.get_plan_limits()
        
        if months > max_months:
            return {
                'valid': False,
                'error': f'Plan {cls.PLAN_TYPE} supports maximum {max_months} months'
            }
        
        estimated_credits = cls.estimate_credit_usage(currencies_count, months * 30)
        monthly_limit = plan_limits['monthly_credits']
        
        if estimated_credits > monthly_limit:
            return {
                'valid': False,
                'error': f'Estimated {estimated_credits} credits exceeds monthly limit {monthly_limit}'
            }
        
        return {
            'valid': True,
            'estimated_credits': estimated_credits,
            'monthly_limit': monthly_limit,
            'usage_percentage': (estimated_credits / monthly_limit) * 100
        }
