from sqlalchemy.orm import Session
from database.Currencies import Currencies
import requests
import logging

class CurrencyService:
    def __init__(self, session: Session):
        self.session = session

    def get_all_currencies(self, page: int, per_page: int) -> list:
        """Get paginated list of currencies"""
        offset = (page - 1) * per_page
        currencies = self.session.query(Currencies)\
            .offset(offset)\
            .limit(per_page)\
            .all()
        return [currency.to_dict() for currency in currencies]

    def update_prices(self) -> dict:
        """Update currency prices from external API"""
        try:
            # Implement price update logic here
            # This is a placeholder that should be replaced with actual API calls
            return {"status": "success", "message": "Prices updated"}
        except Exception as e:
            logging.error(f"Error updating prices: {str(e)}")
            return {"status": "error", "message": str(e)}
