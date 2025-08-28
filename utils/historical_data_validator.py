"""
Validation utilities for historical data
"""
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import logging

logger = logging.getLogger(__name__)

class HistoricalDataValidator:
    """Validator for historical data requests and responses"""
    
    VALID_INTERVALS = [
        '5m', '10m', '15m', '30m', '45m', '1h', '2h', '3h', '4h', '6h', '12h',
        '1d', '2d', '3d', '7d', '14d', '15d', '30d', '60d', '90d', '365d',
        'daily', 'hourly'
    ]
    
    VALID_FIAT_CURRENCIES = [
        'USD', 'EUR', 'GBP', 'JPY', 'KRW', 'CNY', 'CAD', 'AUD', 'INR', 'RUB',
        'BRL', 'TRY', 'SAR', 'KWD', 'BHD', 'TND', 'IQD'
    ]
    
    @classmethod
    def validate_time_range(cls, time_start: Optional[str], time_end: Optional[str]) -> Dict:
        """
        Validate time range for historical data requests
        
        Args:
            time_start: Start time in ISO format
            time_end: End time in ISO format
            
        Returns:
            Dict with validation result and normalized times
        """
        try:
            # Set defaults if not provided
            if not time_end:
                end_time = datetime.now()
            else:
                end_time = datetime.fromisoformat(time_end.replace('Z', '+00:00'))
            
            if not time_start:
                start_time = end_time - timedelta(days=30)
            else:
                start_time = datetime.fromisoformat(time_start.replace('Z', '+00:00'))
            
            # Validate time order
            if start_time >= end_time:
                return {
                    'valid': False,
                    'error': 'time_start must be before time_end'
                }
            
            # Validate time range (max 1 year for free plan)
            max_days = 365
            if (end_time - start_time).days > max_days:
                return {
                    'valid': False,
                    'error': f'Time range cannot exceed {max_days} days'
                }
            
            # Check if dates are too far in the past (API limitation)
            one_year_ago = datetime.now() - timedelta(days=365)
            if start_time < one_year_ago:
                logger.warning(f"Requested start time {start_time} may be outside API limits")
            
            return {
                'valid': True,
                'time_start': start_time.isoformat() + 'Z',
                'time_end': end_time.isoformat() + 'Z',
                'start_datetime': start_time,
                'end_datetime': end_time
            }
            
        except ValueError as e:
            return {
                'valid': False,
                'error': f'Invalid time format: {str(e)}'
            }
    
    @classmethod
    def validate_interval(cls, interval: str) -> Dict:
        """Validate time interval"""
        if interval not in cls.VALID_INTERVALS:
            return {
                'valid': False,
                'error': f'Invalid interval. Must be one of: {", ".join(cls.VALID_INTERVALS)}'
            }
        return {'valid': True, 'interval': interval}
    
    @classmethod
    def validate_fiat_currencies(cls, fiat_currencies: List[str]) -> Dict:
        """Validate fiat currencies"""
        invalid_fiats = [fiat for fiat in fiat_currencies if fiat not in cls.VALID_FIAT_CURRENCIES]
        
        if invalid_fiats:
            return {
                'valid': False,
                'error': f'Invalid fiat currencies: {invalid_fiats}. Valid options: {", ".join(cls.VALID_FIAT_CURRENCIES)}'
            }
        
        return {'valid': True, 'fiat_currencies': fiat_currencies}
    
    @classmethod
    def validate_api_response(cls, response_data: Dict) -> Dict:
        """Validate CoinMarketCap API response"""
        if not isinstance(response_data, dict):
            return {'valid': False, 'error': 'Response is not a dictionary'}
        
        if 'status' not in response_data:
            return {'valid': False, 'error': 'No status in response'}
        
        status = response_data['status']
        if status.get('error_code', 0) != 0:
            return {
                'valid': False,
                'error': f"API Error {status.get('error_code')}: {status.get('error_message')}"
            }
        
        if 'data' not in response_data:
            return {'valid': False, 'error': 'No data in response'}
        
        data = response_data['data']
        if not isinstance(data, dict) or 'quotes' not in data:
            return {'valid': False, 'error': 'Invalid data structure in response'}
        
        quotes = data['quotes']
        if not isinstance(quotes, list) or len(quotes) == 0:
            return {'valid': False, 'error': 'No quotes in response'}
        
        return {'valid': True, 'quotes_count': len(quotes)}
