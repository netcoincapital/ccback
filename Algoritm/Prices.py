from APIs import CoinMarketCapService
import logging

class CurrencyPriceService:
    def __init__(self):
        self.coin_market_cap = CoinMarketCapService()
        self.logger = logging.getLogger(self.__class__.__name__)

    def get_latest_prices(self, symbols: list[str], convert: str = "USD") -> dict:
        """
        دریافت قیمت لحظه‌ای چندین ارز دیجیتال.

        :param symbols: لیستی از نماد ارزهای دیجیتال (مانند ['BTC', 'ETH']).
        :param convert: ارز تبدیل (پیش‌فرض: 'USD').
        :return: دیکشنری شامل قیمت لحظه‌ای هر ارز.
        """
        try:
            self.logger.info(f"Fetching latest prices for symbols: {symbols}, convert: {convert}")
            symbol_str = ",".join(symbols)  # تبدیل لیست به رشته با جداکننده ","
            response = self.coin_market_cap.get_token_price(symbol_str, convert)
            
            if response.get("status") and response["status"].get("error_code") == 0:
                # استخراج قیمت‌ها از پاسخ
                prices = {}
                for symbol in symbols:
                    price_data = response["data"].get(symbol)
                    if price_data:
                        prices[symbol] = price_data["quote"][convert]["price"]
                self.logger.info(f"Prices fetched successfully: {prices}")
                return prices
            else:
                error_msg = response.get("status", {}).get("error_message", "Unknown error")
                self.logger.error(f"Error fetching prices: {error_msg}")
                return {"status": "error", "message": error_msg}
        except Exception as e:
            self.logger.error(f"Exception in get_latest_prices: {str(e)}")
            return {"status": "error", "message": str(e)}

# نمونه استفاده:
if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    service = CurrencyPriceService()
    symbols = ["BTC", "ETH", "BNB", "NCC"]
    prices = service.get_latest_prices(symbols)
    print(prices)
