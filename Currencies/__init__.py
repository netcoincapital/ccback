from utils.logging_config import get_logger

# Configure logging
logger = get_logger(__file__)
logger.info("Initializing Currencies package")

# تنظیم مسیر واردسازی‌ها برای جلوگیری از واردسازی دوری
# ابتدا کلاس‌های پایه که واردسازی دوری ندارند تعریف شوند
from .currency_price_service import CurrencyPriceService, fiat_symbols

# سپس سرویس‌های دیگر
from .price_service import PriceDbService

# در نهایت قطعات رابط کاربری
from .Prices import CUpdate_bp
from .All_Currencies import CPost_bp

# برای حفظ سازگاری با کد قبل، Prices_bp را هم export می‌کنیم
Prices_bp = CUpdate_bp

# Define what gets exported when using "from Currencies import *"
__all__ = ['Prices_bp', 'CPost_bp', 'CUpdate_bp', 'PriceDbService', 'CurrencyPriceService', 'fiat_symbols']

logger.debug("Blueprints and services initialized and exported")
