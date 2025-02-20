import os
import requests

# تنظیمات پایگاه داده
DATABASE_URL = "mysql+mysqlconnector://root:Q#-76(12Kji09?@localhost/IronWallet"

# پیکربندی API‌ها
ETHERSCAN_API_URL = 'https://api.etherscan.io/api'
ETHERSCAN_API_KEY = '77D1W3AMVN6ZGUXQ7116ECFQC2M9M3WFKY'

TRONSCAN_API_URL = 'https://apilist.tronscanapi.com/api'
TRONSCAN_API_KEY = '87a006f2-b397-4961-9597-cb2a7e7e5577'

BNBSCAN_API_URL = 'https://api.bscscan.com/api'
BNBSCAN_API_KEY = 'AXZ8211BAB2GVKKMMUVU24ERT858ZGE3SJ'

COINMARKETCAP_API_URL = 'https://pro-api.coinmarketcap.com/v1/cryptocurrency/quotes/latest'
COINMARKETCAP_API_KEY = 'bbae831b-bd1b-4949-8945-2b5ab0b9456d'


class BaseConfig:
    """
    کلاس پایه برای پیکربندی بلاکچین‌ها
    """
    def __init__(self, api_url: str, api_key: str):
        self.api_url = api_url
        self.api_key = api_key


HMAC_SECRET_KEY = os.getenv('HMAC_SECRET_KEY', 'my_secret_key')

# URL اصلی برای ارجاعات
MAIN_URL = os.getenv('MAIN_URL', 'http://url/referrals/generate')