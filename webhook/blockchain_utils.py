import logging
import requests
import os
from CC.utils.logging_config import get_logger

# تنظیم لاگر
logger = get_logger(__file__)

# تعریف URL پایه API تاتوم
TATUM_API_BASE_URL = "https://api.tatum.io/v3"

class BlockchainUtils:
    """
    کلاس ابزاری برای کار با بلاکچین‌های مختلف
    """
    
    def __init__(self):
        """
        مقداردهی اولیه کلاس ابزار بلاکچین
        """
        # تعریف نگاشت از فرمت بلاکچین تاتوم به فرمت داخلی
        self.TATUM_TO_INTERNAL_MAPPING = {
            "ethereum-mainnet": "ETH",
            "bitcoin-mainnet": "BTC",
            "polygon-mainnet": "MATIC",
            "polygon": "MATIC",  # اضافه کردن polygon بدون mainnet
            "bsc-mainnet": "BSC",
            "avax-mainnet": "AVAX",
            "solana-mainnet": "SOL",
            "tron-mainnet": "TRX",
            "ripple-mainnet": "XRP",
            "arb-one-mainnet": "ARB"
        }
        
        # انواع دیگر
        self.BSC_VARIANTS = ["BSC", "BNB", "Binance", "BINANCE", "bsc", "bnb", "binance"]
        self.ETH_VARIANTS = ["ETH", "Ethereum", "ETHEREUM", "eth", "ethereum"]
        self.POLYGON_VARIANTS = ["POLYGON", "MATIC", "Polygon", "polygon", "matic", "Matic"]
    
    def convert_chain_format(self, chain):
        """
        تبدیل فرمت نام بلاکچین تاتوم به فرمت داخلی.
        
        Args:
            chain (str): نام بلاکچین از وب‌هوک تاتوم
            
        Returns:
            str: نام بلاکچین در فرمت داخلی
        """
        if not chain:
            return None
        
        # ثبت لاگ نام اصلی بلاکچین برای دیباگ
        logger.info(f"نام اصلی بلاکچین از تاتوم: {chain}")
        
        # بررسی اینکه آیا بلاکچین در حال حاضر در فرمت ما است (فقط نماد)
        if chain in ["ETH", "BTC", "MATIC", "BSC", "AVAX", "SOL", "TRX", "XRP", "ARB"]:
            logger.debug(f"بلاکچین {chain} از قبل در فرمت داخلی است")
            return chain
        
        # تلاش برای تبدیل از فرمت تاتوم به فرمت ما
        internal_chain = self.TATUM_TO_INTERNAL_MAPPING.get(chain)
        if internal_chain:
            logger.info(f"فرمت بلاکچین تاتوم '{chain}' به فرمت داخلی '{internal_chain}' تبدیل شد")
            return internal_chain
        
        # اگر نتوانستیم تبدیل کنیم، سعی می‌کنیم نام بلاکچین را از رشته استخراج کنیم
        if "-" in chain:
            # تلاش برای استخراج فقط نام بلاکچین از فرمت‌هایی مانند "xxx-mainnet"
            chain_parts = chain.split("-")
            if chain_parts[0].upper() in ["ETH", "BTC", "MATIC", "BSC", "AVAX", "SOL", "TRX", "XRP", "ARB"]:
                logger.info(f"بلاکچین '{chain_parts[0].upper()}' از '{chain}' استخراج شد")
                return chain_parts[0].upper()
            
            # رسیدگی به موارد خاص
            if chain_parts[0].lower() == "ethereum":
                return "ETH"
            elif chain_parts[0].lower() == "bitcoin":
                return "BTC"
            elif chain_parts[0].lower() == "polygon":
                return "MATIC"
            elif chain_parts[0].lower() == "bsc":
                return "BSC"
            elif chain_parts[0].lower() == "avax":
                return "AVAX"
            elif chain_parts[0].lower() == "solana":
                return "SOL"
            elif chain_parts[0].lower() == "tron":
                return "TRX"
            elif chain_parts[0].lower() == "ripple":
                return "XRP"
            elif chain_parts[0].lower() == "arb":
                return "ARB"
        
        # بررسی انواع BSC
        if chain.lower() in [v.lower() for v in self.BSC_VARIANTS]:
            logger.info(f"بلاکچین '{chain}' با انواع BSC تطبیق یافت")
            return "BSC"
        
        # بررسی انواع ETH
        if chain.lower() in [v.lower() for v in self.ETH_VARIANTS]:
            logger.info(f"بلاکچین '{chain}' با انواع ETH تطبیق یافت")
            return "ETH"
        
        # بررسی انواع POLYGON
        if chain.lower() in [v.lower() for v in self.POLYGON_VARIANTS]:
            logger.info(f"بلاکچین '{chain}' با انواع POLYGON تطبیق یافت")
            return "MATIC"
        
        # اگر نتوانستیم آن را تبدیل کنیم، یک هشدار ثبت می‌کنیم و مقدار اصلی را برمی‌گردانیم
        logger.warning(f"تبدیل فرمت بلاکچین تاتوم '{chain}' به فرمت داخلی امکان‌پذیر نبود")
        return chain
    
    def is_address_in_log(self, address, log_data, topics):
        """
        بررسی می‌کند که آیا یک آدرس در داده‌های لاگ یا عناوین رویداد وجود دارد.
        
        Args:
            address (str): آدرس کیف پول
            log_data (str): داده‌های لاگ
            topics (list): لیست عناوین رویداد
            
        Returns:
            bool: True اگر آدرس یافت شود، در غیر این صورت False
        """
        if not address:
            return False
        
        # آدرس را به حروف کوچک تبدیل می‌کنیم
        normalized_address = address.lower()
        
        # حذف پیشوند 0x اگر وجود داشته باشد
        if normalized_address.startswith('0x'):
            clean_address = normalized_address[2:]
        else:
            clean_address = normalized_address
        
        # بررسی در داده‌های لاگ
        if log_data and isinstance(log_data, str):
            if normalized_address in log_data.lower() or clean_address in log_data.lower():
                logger.debug(f"آدرس {normalized_address} در داده‌های لاگ یافت شد")
                return True
        
        # بررسی در عناوین
        for topic in topics:
            if isinstance(topic, str) and (normalized_address in topic.lower() or clean_address in topic.lower()):
                logger.debug(f"آدرس {normalized_address} در عناوین یافت شد")
                return True
        
        return False
    
    def get_transaction_fee_from_tatum(self, transaction_id, blockchain):
        """
        دریافت کارمزد تراکنش از API تاتوم.
        
        Args:
            transaction_id (str): شناسه تراکنش
            blockchain (str): نماد بلاکچین
            
        Returns:
            str: مقدار کارمزد یا None در صورت بروز خطا
        """
        try:
            logger.info(f"درخواست اطلاعات کارمزد برای تراکنش {transaction_id} در بلاکچین {blockchain}")
            
            # تعیین نوع بلاکچین برای درخواست API مناسب
            if blockchain.upper() == "ETH":
                endpoint = f"{TATUM_API_BASE_URL}/ethereum/transaction/{transaction_id}"
            elif blockchain.upper() == "BSC":
                endpoint = f"{TATUM_API_BASE_URL}/bsc/transaction/{transaction_id}"
            elif blockchain.upper() == "MATIC":
                endpoint = f"{TATUM_API_BASE_URL}/polygon/transaction/{transaction_id}"
            elif blockchain.upper() == "TRX":
                endpoint = f"{TATUM_API_BASE_URL}/tron/transaction/{transaction_id}"
            else:
                logger.warning(f"بلاکچین پشتیبانی نشده برای درخواست کارمزد: {blockchain}")
                return None
            
            # درخواست به API تاتوم
            headers = {
                "x-api-key": os.getenv("TATUM_API_KEY", ""),
                "Content-Type": "application/json"
            }
            
            response = requests.get(endpoint, headers=headers)
            
            if response.status_code == 200:
                data = response.json()
                logger.info(f"پاسخ API تاتوم دریافت شد: {data}")
                
                # استخراج کارمزد بر اساس نوع بلاکچین
                if blockchain.upper() == "ETH":
                    gas_price = int(data.get('gasPrice', '0'), 16) / 1e9  # تبدیل از Wei به Gwei
                    gas_used = int(data.get('gasUsed', '0'), 16)
                    fee = (gas_price * gas_used) / 1e9  # تبدیل به ETH
                    return str(fee)
                elif blockchain.upper() == "BSC":
                    gas_price = int(data.get('gasPrice', '0'), 16) / 1e9
                    gas_used = int(data.get('gasUsed', '0'), 16)
                    fee = (gas_price * gas_used) / 1e9
                    return str(fee)
                elif blockchain.upper() == "MATIC":
                    gas_price = int(data.get('gasPrice', '0'), 16) / 1e9
                    gas_used = int(data.get('gasUsed', '0'), 16)
                    fee = (gas_price * gas_used) / 1e9
                    return str(fee)
                elif blockchain.upper() == "TRX":
                    # برای ترون، کارمزد در فیلد fee ذخیره می‌شود
                    fee = data.get('fee', 0) / 1e6  # تبدیل به TRX
                    return str(fee)
            else:
                logger.error(f"خطا در دریافت اطلاعات تراکنش: {response.status_code} - {response.text}")
                
        except Exception as e:
            logger.error(f"خطا در دریافت کارمزد تراکنش: {str(e)}", exc_info=True)
        
        return None
    
    def get_transaction_details(self, transaction_id, blockchain):
        """
        دریافت جزئیات تراکنش از API تاتوم.
        
        Args:
            transaction_id (str): شناسه تراکنش
            blockchain (str): نماد بلاکچین
            
        Returns:
            dict: جزئیات تراکنش یا None در صورت بروز خطا
        """
        try:
            logger.info(f"درخواست جزئیات تراکنش {transaction_id} در بلاکچین {blockchain}")
            
            # تعیین نوع بلاکچین برای درخواست API مناسب
            if blockchain.upper() == "ETH":
                endpoint = f"{TATUM_API_BASE_URL}/ethereum/transaction/{transaction_id}"
            elif blockchain.upper() == "BSC":
                endpoint = f"{TATUM_API_BASE_URL}/bsc/transaction/{transaction_id}"
            elif blockchain.upper() == "MATIC":
                endpoint = f"{TATUM_API_BASE_URL}/polygon/transaction/{transaction_id}"
            elif blockchain.upper() == "TRX":
                endpoint = f"{TATUM_API_BASE_URL}/tron/transaction/{transaction_id}"
            else:
                logger.warning(f"بلاکچین پشتیبانی نشده برای درخواست جزئیات: {blockchain}")
                return None
            
            # درخواست به API تاتوم
            headers = {
                "x-api-key": os.getenv("TATUM_API_KEY", ""),
                "Content-Type": "application/json"
            }
            
            response = requests.get(endpoint, headers=headers)
            
            if response.status_code == 200:
                data = response.json()
                logger.info(f"پاسخ API تاتوم دریافت شد")
                logger.debug(f"جزئیات تراکنش: {data}")
                return data
            else:
                logger.error(f"خطا در دریافت جزئیات تراکنش: {response.status_code} - {response.text}")
                
        except Exception as e:
            logger.error(f"خطا در دریافت جزئیات تراکنش: {str(e)}", exc_info=True)
        
        return None
        
    def get_address_balance(self, address, blockchain, token_contract=None):
        """
        دریافت موجودی یک آدرس در بلاکچین مشخص
        
        Args:
            address (str): آدرس کیف پول
            blockchain (str): نماد بلاکچین
            token_contract (str, optional): آدرس قرارداد توکن (برای دریافت موجودی توکن)
            
        Returns:
            float: موجودی آدرس یا None در صورت بروز خطا
        """
        try:
            logger.info(f"دریافت موجودی آدرس {address} در بلاکچین {blockchain}")
            
            # فرمت آدرس را استاندارد می‌کنیم
            if address.startswith('0x'):
                normalized_address = address.lower()
            else:
                # برای بلاکچین‌های EVM
                if blockchain.upper() in ["ETH", "BSC", "MATIC", "AVAX", "ARB"]:
                    normalized_address = f"0x{address.lower()}"
                else:
                    normalized_address = address
            
            # تعیین نوع بلاکچین برای درخواست API مناسب
            if blockchain.upper() == "ETH":
                # برای اتریوم اصلی
                if token_contract:
                    # برای توکن‌های ERC20
                    endpoint = f"{TATUM_API_BASE_URL}/ethereum/account/balance/erc20/{normalized_address}?contractAddress={token_contract}"
                else:
                    # برای اتر اصلی
                    endpoint = f"{TATUM_API_BASE_URL}/ethereum/account/balance/{normalized_address}"
            elif blockchain.upper() == "BSC":
                # برای بایننس اسمارت چین
                if token_contract:
                    # برای توکن‌های BEP20
                    endpoint = f"{TATUM_API_BASE_URL}/bsc/account/balance/bep20/{normalized_address}?contractAddress={token_contract}"
                else:
                    # برای BNB اصلی
                    endpoint = f"{TATUM_API_BASE_URL}/bsc/account/balance/{normalized_address}"
            elif blockchain.upper() == "MATIC":
                # برای پولیگان
                if token_contract:
                    endpoint = f"{TATUM_API_BASE_URL}/polygon/account/balance/erc20/{normalized_address}?contractAddress={token_contract}"
                else:
                    endpoint = f"{TATUM_API_BASE_URL}/polygon/account/balance/{normalized_address}"
            elif blockchain.upper() == "BTC":
                # برای بیت‌کوین
                endpoint = f"{TATUM_API_BASE_URL}/bitcoin/address/balance/{normalized_address}"
            elif blockchain.upper() == "TRX":
                # برای ترون
                if token_contract:
                    # اطلاعات بیشتر برای دیباگ
                    logger.info(f"درخواست موجودی توکن TRC20 برای آدرس {normalized_address} و قرارداد {token_contract}")
                    
                    # استفاده از API مسیر صحیح برای TRC20
                    endpoint = f"{TATUM_API_BASE_URL}/tron/account/balance/trc20/{normalized_address}?contractAddress={token_contract}"
                    
                    # بررسی یک مسیر جایگزین اگر API تغییر کرده باشد
                    alternative_endpoint = f"{TATUM_API_BASE_URL}/tron/account/balance/{normalized_address}/trc20"
                else:
                    endpoint = f"{TATUM_API_BASE_URL}/tron/account/balance/{normalized_address}"
            elif blockchain.upper() == "SOL":
                # برای سولانا
                if token_contract:
                    endpoint = f"{TATUM_API_BASE_URL}/solana/account/balance/spl/{normalized_address}?contractAddress={token_contract}"
                else:
                    endpoint = f"{TATUM_API_BASE_URL}/solana/account/balance/{normalized_address}"
            elif blockchain.upper() == "XRP":
                # برای ریپل
                endpoint = f"{TATUM_API_BASE_URL}/xrp/account/balance/{normalized_address}"
            else:
                logger.warning(f"بلاکچین پشتیبانی نشده برای درخواست موجودی: {blockchain}")
                # یک مقدار موجودی پیش‌فرض برمی‌گردانیم تا فرآیند ادامه پیدا کند
                return 0
            
            # درخواست به API تاتوم
            headers = {
                "x-api-key": os.getenv("TATUM_API_KEY", ""),
                "Content-Type": "application/json"
            }
            
            response = requests.get(endpoint, headers=headers)
            
            if response.status_code == 200:
                data = response.json()
                logger.info(f"پاسخ API تاتوم برای موجودی دریافت شد: {data}")
                
                # استخراج موجودی بر اساس نوع بلاکچین
                if blockchain.upper() in ["ETH", "BSC", "MATIC"]:
                    if token_contract:
                        # برای توکن‌های ERC20/BEP20
                        balance = float(data.get('balance', '0'))
                    else:
                        # برای ارز اصلی
                        balance = float(data.get('balance', '0'))
                elif blockchain.upper() == "BTC":
                    # برای بیت‌کوین
                    balance = float(data.get('incoming', '0')) - float(data.get('outgoing', '0'))
                elif blockchain.upper() == "TRX":
                    if token_contract:
                        # برای توکن‌های TRC20
                        # لاگ کامل پاسخ برای دیباگ
                        logger.debug(f"پاسخ TRC20 کامل: {data}")
                        
                        # ساختار جدید تاتوم برای توکن‌های TRC20 ترون
                        if 'trc20' in data:
                            # قالب جدید API V3
                            for token in data.get('trc20', []):
                                if token.get('tokenAddress', '').lower() == token_contract.lower():
                                    raw_balance = token.get('balance', '0')
                                    decimals = token.get('decimals', 18)
                                    try:
                                        decimals = int(decimals)
                                        balance = float(raw_balance) / (10 ** decimals)
                                        logger.info(f"موجودی توکن TRC20 (قالب جدید): {balance}")
                                        return balance
                                    except (ValueError, TypeError) as e:
                                        logger.error(f"خطا در تبدیل موجودی TRC20: {str(e)}")
                        
                        # ساختار قدیمی
                        if 'balance' in data:
                            # قالب ساده
                            try:
                                raw_balance = data.get('balance', '0')
                                # تلاش برای دریافت decimals از پاسخ
                                decimals = data.get('decimals', 18)
                                try:
                                    decimals = int(decimals)
                                except (ValueError, TypeError):
                                    decimals = 18  # مقدار پیش‌فرض
                                
                                balance = float(raw_balance) / (10 ** decimals)
                                logger.info(f"موجودی توکن TRC20 (قالب ساده): {balance}")
                                return balance
                            except (ValueError, TypeError) as e:
                                logger.error(f"خطا در تبدیل موجودی TRC20: {str(e)}")
                        
                        # ساختار جایگزین
                        token_data = data.get('tokens', [])
                        if token_data:
                            for token in token_data:
                                token_id = token.get('tokenId', '')
                                token_address = token.get('address', '')
                                
                                # بررسی تطابق آدرس قرارداد
                                if token_address.lower() == token_contract.lower() or token_id.lower() == token_contract.lower():
                                    raw_balance = token.get('balance', '0')
                                    decimals = token.get('decimals', 18)
                                    try:
                                        decimals = int(decimals)
                                        balance = float(raw_balance) / (10 ** decimals)
                                        logger.info(f"موجودی توکن TRC20 (قالب جایگزین): {balance}")
                                        return balance
                                    except (ValueError, TypeError) as e:
                                        logger.error(f"خطا در تبدیل موجودی TRC20: {str(e)}")
                                        
                        # اگر هیچ‌کدام از ساختارها یافت نشد، لاگ هشدار
                        logger.warning(f"ساختار داده TRC20 ناشناخته: {data}")
                        # موجودی صفر برگردانده می‌شود
                        return 0
                    else:
                        # برای ارز اصلی ترون (TRX)
                        balance = float(data.get('balance', '0')) / 1e6  # تبدیل به TRX
                elif blockchain.upper() == "SOL":
                    # برای سولانا
                    balance = float(data.get('balance', '0'))
                elif blockchain.upper() == "XRP":
                    # برای ریپل
                    balance = float(data.get('balance', '0'))
                else:
                    balance = 0
                
                logger.info(f"موجودی آدرس {address}: {balance} {blockchain}")
                return balance
            else:
                logger.error(f"خطا در دریافت موجودی: {response.status_code} - {response.text}")
                # بررسی خطای 404 برای ترون
                if blockchain.upper() == "TRX" and token_contract and response.status_code == 404:
                    # تلاش با استفاده از API جایگزین برای ترون
                    logger.info(f"تلاش با مسیر API جایگزین برای توکن TRC20: {alternative_endpoint}")
                    
                    try:
                        response_alt = requests.get(alternative_endpoint, headers=headers)
                        if response_alt.status_code == 200:
                            data_alt = response_alt.json()
                            logger.info(f"پاسخ API جایگزین دریافت شد: {data_alt}")
                            
                            # بررسی آیا توکن در لیست موجود است
                            if isinstance(data_alt, list):
                                for token in data_alt:
                                    if token.get('tokenAddress', '').lower() == token_contract.lower() or token.get('address', '').lower() == token_contract.lower():
                                        balance_raw = token.get('balance', 0)
                                        decimals = token.get('decimals', 18)
                                        balance = float(balance_raw) / (10 ** int(decimals))
                                        logger.info(f"موجودی توکن TRC20 با روش جایگزین: {balance}")
                                        return balance
                            elif isinstance(data_alt, dict) and 'tokens' in data_alt:
                                for token in data_alt['tokens']:
                                    if token.get('tokenAddress', '').lower() == token_contract.lower() or token.get('address', '').lower() == token_contract.lower():
                                        balance_raw = token.get('balance', 0)
                                        decimals = token.get('decimals', 18)
                                        balance = float(balance_raw) / (10 ** int(decimals))
                                        logger.info(f"موجودی توکن TRC20 با روش جایگزین: {balance}")
                                        return balance
                        else:
                            logger.error(f"خطا در API جایگزین: {response_alt.status_code} - {response_alt.text}")
                    except Exception as alt_e:
                        logger.error(f"خطا در استفاده از API جایگزین: {str(alt_e)}")
                
                # یک مقدار موجودی پیش‌فرض برمی‌گردانیم تا فرآیند ادامه پیدا کند
                return 0
                
        except Exception as e:
            logger.error(f"خطا در دریافت موجودی آدرس: {str(e)}", exc_info=True)
            # یک مقدار موجودی پیش‌فرض برمی‌گردانیم تا فرآیند ادامه پیدا کند
            return 0 