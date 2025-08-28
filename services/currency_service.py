from sqlalchemy.orm import Session
from CC.database.Currencies import Currencies
import requests
import logging
from CC.config.cache import redis_client
import json
from datetime import timedelta

class CurrencyService:
    CACHE_TTL = timedelta(minutes=5)  # مدت زمان اعتبار کش
    
    def __init__(self, session: Session):
        self.session = session
        
    def get_all_currencies(self, page: int, per_page: int) -> list:
        """Get paginated list of currencies"""
        cache_key = f"currencies:page:{page}:per_page:{per_page}"
        
        # تلاش برای خواندن از کش
        try:
            cached_data = redis_client.get(cache_key)
            if cached_data:
                return json.loads(cached_data)
        except Exception as e:
            logging.warning(f"Redis cache error: {str(e)}")
            # Continue with database query if Redis fails
            
        # اگر در کش نبود، از دیتابیس بخوان
        offset = (page - 1) * per_page
        currencies = self.session.query(Currencies)\
            .offset(offset)\
            .limit(per_page)\
            .all()
        result = [currency.to_dict() for currency in currencies]
        
        # ذخیره در کش
        try:
            redis_client.setex(
                cache_key,
                self.CACHE_TTL,
                json.dumps(result)
            )
        except Exception as e:
            logging.warning(f"Redis cache set error: {str(e)}")
            # Continue without caching if Redis fails
        
        return result

    def get_all_currencies_without_cache(self, page: int, per_page: int) -> list:
        """Get paginated list of currencies without using Redis cache"""
        offset = (page - 1) * per_page
        currencies = self.session.query(Currencies)\
            .offset(offset)\
            .limit(per_page)\
            .all()
        return [currency.to_dict() for currency in currencies]

    def update_prices(self) -> dict:
        """Update currency prices from external API"""
        # پاک کردن کش قیمت‌ها
        redis_client.delete("prices:*")
        try:
            # Implement price update logic here
            # This is a placeholder that should be replaced with actual API calls
            return {"status": "success", "message": "Prices updated"}
        except Exception as e:
            logging.error(f"Error updating prices: {str(e)}")
            return {"status": "error", "message": str(e)}
