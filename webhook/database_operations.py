import logging
from sqlalchemy import create_engine, text, select, and_, or_, exists, not_, func
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from datetime import datetime, timedelta
import os
import json
from utils.logging_config import get_logger
import uuid
from decimal import Decimal
import time

# تنظیم لاگر
logger = get_logger(__file__)

# واردسازی تنظیمات پایگاه داده
from config import DATABASE_URL

# Import the BlockchainUtils class
from webhook.blockchain_utils import BlockchainUtils

class DatabaseOperations:
    """
    کلاس عملیات پایگاه داده برای کار با داده‌های مربوط به تراکنش‌های بلاکچین
    """
    
    def __init__(self):
        """
        مقداردهی اولیه کلاس عملیات پایگاه داده
        """
        # ایجاد موتور دیتابیس به صورت تنبل (lazy) - فقط در زمان نیاز متصل می‌شود
        self.engine = None
        self.user_addresses = []
        self.blockchain_utils = BlockchainUtils()  # Initialize the blockchain_utils
    
    def _get_engine(self):
        """
        ایجاد یا بازیابی موتور دیتابیس
        
        Returns:
            Engine: موتور SQLAlchemy
        """
        if self.engine is None:
            try:
                self.engine = create_engine(DATABASE_URL)
                logger.info("موتور دیتابیس ایجاد شد")
            except Exception as e:
                logger.error(f"خطا در ایجاد موتور دیتابیس: {str(e)}", exc_info=True)
                raise
        return self.engine
    
    def get_user_addresses(self):
        """
        دریافت لیست آدرس‌های کیف پول کاربران از پایگاه داده
        
        Returns:
            list: لیست آدرس‌های کیف پول
        """
        try:
            engine = self._get_engine()
            
            with Session(engine) as session:
                logger.info("در حال دریافت آدرس‌های کاربران از دیتابیس...")
                
                # استفاده از موتور پرس‌و‌جو برای دریافت آدرس‌ها از جدول address
                query = text("""
                    SELECT 
                        a.AddressID, 
                        a.WalletID, 
                        a.PublicAddress, 
                        w.UserID,
                        b.Symbol
                    FROM address a
                    JOIN wallets w ON a.WalletID = w.WalletID
                    JOIN blockchains b ON a.BlockchainID = b.BlockchainID
                """)
                
                logger.debug(f"اجرای کوئری SQL برای دریافت آدرس‌ها: {query}")
                result = session.execute(query)
                
                # تبدیل نتیجه به لیست دیکشنری‌ها
                addresses = []
                for row in result:
                    address_data = {
                        'address_id': row[0],
                        'wallet_id': row[1],
                        'public_address': row[2],
                        'user_id': row[3],
                        'currency_symbol': row[4],
                        'wallet_name': 'Wallet'  # مقدار پیش‌فرض
                    }
                    addresses.append(address_data)
                    logger.debug(f"آدرس یافت شد: {address_data['public_address']} برای کیف پول {address_data['wallet_id']}")
                
                logger.info(f"تعداد {len(addresses)} آدرس کیف پول از دیتابیس دریافت شد")
                
                # اگر هیچ آدرسی پیدا نشد، فقط لاگ بنویسیم
                if len(addresses) == 0:
                    logger.warning("هیچ آدرسی از دیتابیس دریافت نشد.")
                    
                    # کوئری ساده‌تر برای بررسی وجود جدول و رکوردها
                    check_query = text("SELECT COUNT(*) FROM address")
                    try:
                        count_result = session.execute(check_query).scalar()
                        logger.warning(f"تعداد کل رکوردهای جدول address: {count_result}")
                    except Exception as e:
                        logger.error(f"خطا در بررسی تعداد رکوردهای جدول address: {str(e)}")
                
                return addresses
                
        except Exception as e:
            logger.error(f"خطا در دریافت آدرس‌های کاربران: {str(e)}", exc_info=True)
            return []
    
    def check_transaction_exists(self, session, transaction_id, address_id=None, wallet_id=None, blockchain_id=None):
        """
        بررسی وجود تراکنش در جدول Transfers
        
        Args:
            session (Session): جلسه فعال دیتابیس
            transaction_id (str): شناسه تراکنش
            address_id (int, optional): شناسه آدرس
            wallet_id (str, optional): شناسه کیف پول
            blockchain_id (int, optional): شناسه بلاکچین
            
        Returns:
            bool: آیا تراکنش قبلاً در Transfers ثبت شده است
        """
        try:
            query = text("""
                SELECT COUNT(*) FROM Transfers 
                WHERE TxHash = :tx_hash
            """)
            
            params = {'tx_hash': str(transaction_id)}
            
            # اضافه کردن شرط بلاکچین اگر موجود باشد
            if blockchain_id is not None:
                query = text("""
                    SELECT COUNT(*) FROM Transfers 
                    WHERE TxHash = :tx_hash AND BlockchainID = :blockchain_id
                """)
                params['blockchain_id'] = blockchain_id
            
            # اضافه کردن شروط اضافی اگر وجود داشته باشند
            if address_id is not None and wallet_id is not None:
                if blockchain_id is not None:
                    query = text("""
                        SELECT COUNT(*) FROM Transfers 
                        WHERE TxHash = :tx_hash AND AddressID = :address_id AND WalletID = :wallet_id AND BlockchainID = :blockchain_id
                    """)
                else:
                    query = text("""
                        SELECT COUNT(*) FROM Transfers 
                        WHERE TxHash = :tx_hash AND AddressID = :address_id AND WalletID = :wallet_id
                    """)
                params['address_id'] = address_id
                params['wallet_id'] = wallet_id
            
            count = session.execute(query, params).scalar()
            return count > 0
            
        except Exception as e:
            logger.error(f"خطا در بررسی وجود تراکنش در Transfers: {str(e)}", exc_info=True)
            return False

    def _get_current_price(self, session, token_symbol, blockchain):
        """
        دریافت قیمت فعلی یک ارز یا توکن از جدول prices
        
        Args:
            session (Session): جلسه فعال دیتابیس
            token_symbol (str): نماد ارز یا توکن
            blockchain (str): نام بلاکچین
            
        Returns:
            float: قیمت ارز به دلار آمریکا یا None در صورت عدم وجود
        """
        try:
            if not token_symbol:
                logger.warning("نماد توکن برای دریافت قیمت خالی است")
                return None
                
            # نرمال‌سازی نماد توکن و بلاکچین
            token_symbol = token_symbol.upper()
            blockchain = blockchain.upper()
            
            # تبدیل BSC به BNB برای همخوانی با دیتابیس
            if blockchain == 'BSC':
                blockchain = 'BNB'
                
            # اگر نماد توکن BSC است، آن را به BNB تبدیل می‌کنیم
            if token_symbol == 'BSC':
                token_symbol = 'BNB'
                
            # تبدیل TRON به TRX برای همخوانی با دیتابیس
            if token_symbol == 'TRON':
                token_symbol = 'TRX'
                
            logger.debug(f"دریافت قیمت برای ارز {token_symbol} در بلاکچین {blockchain}")
            
            # برای BNB، مستقیماً از crypto_id=3 استفاده می‌کنیم
            if token_symbol == 'BNB':
                direct_query = text("""
                    SELECT price FROM prices 
                    WHERE crypto_id = 3 AND currency = 'USD'
                    ORDER BY id DESC LIMIT 1
                """)
                
                direct_result = session.execute(direct_query).fetchone()
                if direct_result:
                    price = float(direct_result[0])
                    logger.info(f"قیمت BNB از جستجوی مستقیم با ID=3: ${price}")
                    return price
            
            # روش اول: استفاده از crypto_id از جدول currencies
            currency_query = text("""
                SELECT c.CurrencyID, c.Symbol, c.cmc_id 
                FROM currencies c
                WHERE LOWER(c.Symbol) = LOWER(:token_symbol) OR LOWER(c.SmartContractAddress) = LOWER(:token_symbol) 
                LIMIT 1
            """)
            
            currency_result = session.execute(currency_query, {
                'token_symbol': token_symbol
            }).fetchone()
            
            if currency_result:
                currency_id = currency_result[0]
                actual_symbol = currency_result[1]
                cmc_id = currency_result[2]
                
                logger.info(f"ارز {token_symbol} با شناسه {currency_id} و CMC ID {cmc_id} یافت شد")
                
                # اگر cmc_id داریم، از آن برای جستجو در جدول prices استفاده می‌کنیم
                if cmc_id:
                    price_query = text("""
                        SELECT price FROM prices 
                        WHERE crypto_id = :cmc_id AND currency = 'USD'
                        ORDER BY id DESC LIMIT 1
                    """)
                    
                    price_result = session.execute(price_query, {'cmc_id': cmc_id}).fetchone()
                    
                    if price_result:
                        price = float(price_result[0])
                        logger.info(f"قیمت {token_symbol} از CMC ID {cmc_id}: ${price}")
                        return price
            
            # روش دوم: جستجوی مستقیم با استفاده از CurrencyID
            if token_symbol == 'TRX' or token_symbol == 'TRON':
                # جستجوی مستقیم برای TRX
                trx_query = text("""
                    SELECT p.price FROM prices p
                    JOIN currencies c ON p.crypto_id = c.cmc_id
                    WHERE c.Symbol = 'TRX' AND p.currency = 'USD'
                    ORDER BY p.id DESC LIMIT 1
                """)
                
                trx_result = session.execute(trx_query).fetchone()
                if trx_result:
                    price = float(trx_result[0])
                    logger.info(f"قیمت TRX از جستجوی مستقیم: ${price}")
                    return price
                    
                # اگر هنوز پیدا نشد، با ID=18 (ID توکن TRX) جستجو کنیم
                direct_query = text("""
                    SELECT price FROM prices 
                    WHERE crypto_id = 18 AND currency = 'USD'
                    ORDER BY id DESC LIMIT 1
                """)
                
                direct_result = session.execute(direct_query).fetchone()
                if direct_result:
                    price = float(direct_result[0])
                    logger.info(f"قیمت TRX با ID=18: ${price}")
                    return price
            
            # روش سوم: جستجوی کلی برای همه ارزها
            fallback_query = text("""
                SELECT p.price 
                FROM prices p
                JOIN currencies c ON p.crypto_id = c.cmc_id
                WHERE c.Symbol = :token_symbol AND p.currency = 'USD'
                ORDER BY p.id DESC LIMIT 1
            """)
            
            fallback_result = session.execute(fallback_query, {'token_symbol': token_symbol}).fetchone()
            
            if fallback_result:
                price = float(fallback_result[0])
                logger.info(f"قیمت {token_symbol} از جستجوی کلی: ${price}")
                return price
            
            # اگر هیچ نتیجه‌ای یافت نشد
            logger.warning(f"هیچ رکوردی در جدول currencies برای {token_symbol} در بلاکچین {blockchain} یافت نشد")
            
            # قیمت‌های پیش‌فرض برای توکن‌های محبوب
            default_prices = {
                'TRX': 0.24,
                'BNB': 606.18,
                'ETH': 1633.33
            }
            
            if token_symbol in default_prices:
                default_price = default_prices[token_symbol]
                logger.info(f"استفاده از قیمت پیش‌فرض برای {token_symbol}: ${default_price}")
                return default_price
                
            return None
            
        except Exception as e:
            logger.error(f"خطا در دریافت قیمت ارز: {str(e)}", exc_info=True)
            
            # مقادیر پیش‌فرض در صورت خطا
            default_prices = {
                'TRX': 0.24,
                'BNB': 606.18,
                'ETH': 1633.33
            }
            
            if token_symbol in default_prices:
                default_price = default_prices[token_symbol]
                logger.info(f"استفاده از قیمت پیش‌فرض برای {token_symbol} بعد از خطا: ${default_price}")
                return default_price
                
            return None

    def _get_transaction_fee(self, tx_hash, blockchain):
        """
        دریافت مقدار کارمزد (fee) تراکنش با استفاده از API تاتوم
        
        Args:
            tx_hash (str): هش تراکنش
            blockchain (str): نام بلاکچین
            
        Returns:
            float: مقدار کارمزد یا None در صورت خطا
        """
        try:
            # بررسی وجود داده‌های ورودی
            if not tx_hash or not blockchain:
                logger.warning("هش تراکنش یا نام بلاکچین برای دریافت کارمزد خالی است")
                return None
                
            # تبدیل فرمت بلاکچین به فرمت مورد نیاز API تاتوم
            blockchain_format = blockchain.lower()
            
            # تهیه فرمت‌های بلاکچین برای API تاتوم
            blockchain_formats = {
                'bnb': 'bsc-mainnet',
                'bsc': 'bsc-mainnet',
                'eth': 'ethereum-mainnet',
                'ethereum': 'ethereum-mainnet',
                'btc': 'bitcoin-mainnet',
                'bitcoin': 'bitcoin-mainnet',
                'ltc': 'litecoin-mainnet',
                'doge': 'dogecoin-mainnet',
                'matic': 'polygon-mainnet',
                'polygon': 'polygon-mainnet',
                'tron': 'tron-mainnet',
                'trx': 'tron-mainnet',
                'xrp': 'xrp-mainnet',
                'ripple': 'xrp-mainnet',
                'sol': 'solana-mainnet',
                'solana': 'solana-mainnet',
                'ada': 'cardano-mainnet',
                'cardano': 'cardano-mainnet',
                'dot': 'polkadot-mainnet',
                'polkadot': 'polkadot-mainnet',
                'avax': 'avalanche-mainnet',
                'avalanche': 'avalanche-mainnet',
            }
            
            blockchain_format = blockchain_formats.get(blockchain_format, blockchain_format + '-mainnet')
                
            logger.info(f"دریافت کارمزد تراکنش {tx_hash} از API تاتوم برای بلاکچین {blockchain_format}")
            
            # استفاده از requests برای فراخوانی API تاتوم
            import requests
            import os
            
            # دریافت API Key از متغیرهای محیطی
            api_key = os.environ.get('TATUM_API_KEY')
            if not api_key:
                logger.error("TATUM_API_KEY در متغیرهای محیطی تنظیم نشده است")
                return None
                
            # ساخت URL بر اساس بلاکچین و هش تراکنش
            base_url = "https://api.tatum.io/v3"
            
            # تعیین URL درست بر اساس نوع بلاکچین
            url_paths = {
                'bsc-mainnet': f"bsc/transaction/{tx_hash}",
                'ethereum-mainnet': f"ethereum/transaction/{tx_hash}",
                'bitcoin-mainnet': f"bitcoin/transaction/{tx_hash}",
                'litecoin-mainnet': f"litecoin/transaction/{tx_hash}",
                'dogecoin-mainnet': f"dogecoin/transaction/{tx_hash}",
                'polygon-mainnet': f"polygon/transaction/{tx_hash}",
                'tron-mainnet': f"tron/transaction/{tx_hash}",
                'xrp-mainnet': f"xrp/transaction/{tx_hash}",
                'solana-mainnet': f"solana/transaction/{tx_hash}",
                'cardano-mainnet': f"cardano/transaction/{tx_hash}",
                'polkadot-mainnet': f"polkadot/transaction/{tx_hash}",
                'avalanche-mainnet': f"avalanche/transaction/{tx_hash}",
            }
            
            url_path = url_paths.get(blockchain_format)
            if not url_path:
                logger.error(f"بلاکچین {blockchain_format} برای دریافت کارمزد پشتیبانی نمی‌شود")
                return None
                
            url = f"{base_url}/{url_path}"
            
            headers = {
                'x-api-key': api_key
            }
            
            # فراخوانی API
            response = requests.get(url, headers=headers)
            
            if response.status_code == 200:
                data = response.json()
                logger.debug(f"پاسخ API تاتوم برای تراکنش {tx_hash}: {data}")
                
                # استخراج fee بر اساس نوع بلاکچین
                fee = None
                
                # استخراج کارمزد بر اساس نوع بلاکچین
                if 'bsc-mainnet' in blockchain_format or 'ethereum-mainnet' in blockchain_format or 'polygon-mainnet' in blockchain_format:
                    # در اتریوم و BSC و پالیگان، کارمزد برابر با gasPrice * gasUsed است
                    if 'gasPrice' in data and 'gasUsed' in data:
                        try:
                            # تبدیل از رشته hex به int، و سپس به float
                            if isinstance(data.get('gasPrice'), str) and data.get('gasPrice').startswith('0x'):
                                gas_price = int(data.get('gasPrice', '0'), 16) / 1e18
                            else:
                                # اگر عدد است یا رشته عادی، به float تبدیل می‌کنیم
                                gas_price = float(data.get('gasPrice', '0')) / 1e18
                                
                            if isinstance(data.get('gasUsed'), str) and data.get('gasUsed').startswith('0x'):
                                gas_used = int(data.get('gasUsed', '0'), 16)
                            else:
                                # اگر effectiveGasPrice وجود دارد و hex است
                                if 'effectiveGasPrice' in data and isinstance(data.get('effectiveGasPrice'), str) and data.get('effectiveGasPrice').startswith('0x'):
                                    gas_price = int(data.get('effectiveGasPrice', '0'), 16) / 1e18
                                
                                gas_used = int(float(data.get('gasUsed', '0')))
                                
                            fee = gas_price * gas_used
                            logger.info(f"کارمزد تراکنش محاسبه شده: {fee} {blockchain.upper()} (gasPrice: {gas_price}, gasUsed: {gas_used})")
                        except (ValueError, TypeError) as e:
                            logger.error(f"خطا در تبدیل gasPrice یا gasUsed: {str(e)} - gasPrice: {data.get('gasPrice')}, gasUsed: {data.get('gasUsed')}")
                            # سعی می‌کنیم از مقادیر خام استفاده کنیم
                            try:
                                gas_price = float(str(data.get('gasPrice', '0')).replace('0x', '')) / 1e18
                                gas_used = float(str(data.get('gasUsed', '0')).replace('0x', ''))
                                fee = gas_price * gas_used
                                logger.info(f"کارمزد تراکنش با استفاده از مقادیر خام: {fee}")
                            except Exception as inner_e:
                                logger.error(f"خطا در محاسبه کارمزد با مقادیر خام: {str(inner_e)}")
                                return None
                    elif 'fee' in data:
                        # برخی API‌ها fee را مستقیماً برمی‌گردانند
                        fee = float(data['fee'])
                        logger.info(f"کارمزد تراکنش مستقیم از API: {fee} {blockchain.upper()}")
                    
                elif 'bitcoin-mainnet' in blockchain_format or 'litecoin-mainnet' in blockchain_format or 'dogecoin-mainnet' in blockchain_format:
                    # در بیت‌کوین و لایت‌کوین و دوج‌کوین، کارمزد را از اختلاف ورودی و خروجی محاسبه می‌کنیم
                    if 'inputs' in data and 'outputs' in data:
                        inputs_total = sum(float(inp.get('value', 0)) for inp in data.get('inputs', []))
                        outputs_total = sum(float(out.get('value', 0)) for out in data.get('outputs', []))
                        fee = inputs_total - outputs_total
                        logger.info(f"کارمزد تراکنش محاسبه شده: {fee} {blockchain.upper()} (inputs: {inputs_total}, outputs: {outputs_total})")
                    elif 'fee' in data:
                        fee = float(data['fee'])
                        logger.info(f"کارمزد تراکنش مستقیم از API: {fee} {blockchain.upper()}")
                    
                else:
                    # برای سایر بلاکچین‌ها، به دنبال یک فیلد fee مستقیم می‌گردیم
                    if 'fee' in data:
                        fee = float(data['fee'])
                        logger.info(f"کارمزد تراکنش مستقیم از API: {fee} {blockchain.upper()}")
                    else:
                        logger.warning(f"فرمت پاسخ API برای بلاکچین {blockchain_format} شناخته شده نیست")
                
                return fee
                    
            else:
                logger.error(f"خطا در دریافت اطلاعات تراکنش از API تاتوم: {response.status_code} - {response.text}")
                return None
                
        except Exception as e:
            logger.error(f"خطا در دریافت کارمزد تراکنش {tx_hash}: {str(e)}")
            return None

    def _extract_fee_from_webhook(self, webhook_data):
        """
        استخراج مقدار کارمزد از داده‌های وب‌هوک
        
        Args:
            webhook_data (dict): داده‌های وب‌هوک
            
        Returns:
            float: مقدار کارمزد یا None در صورت عدم وجود
        """
        try:
            # تلاش برای یافتن کارمزد در داده‌های وب‌هوک
            
            # روش 1: بررسی وجود فیلد مستقیم fee
            if 'fee' in webhook_data:
                fee = float(webhook_data['fee'])
                logger.info(f"کارمزد از فیلد fee استخراج شد: {fee}")
                return fee
                
            # روش 2: پیدا کردن تراکنش نوع fee مرتبط
            if webhook_data.get('type') == 'fee':
                amount = webhook_data.get('amount')
                if amount:
                    # مقدار کارمزد معمولاً منفی است، پس قدر مطلق آن را می‌گیریم
                    fee = abs(float(amount))
                    logger.info(f"کارمزد از تراکنش نوع fee استخراج شد: {fee}")
                    return fee
                    
            # روش 3: محاسبه بر اساس gasPrice و gasUsed
            if 'gasPrice' in webhook_data and 'gasUsed' in webhook_data:
                gas_price = float(webhook_data['gasPrice'])
                gas_used = float(webhook_data['gasUsed'])
                fee = gas_price * gas_used
                logger.info(f"کارمزد از gasPrice و gasUsed محاسبه شد: {fee}")
                return fee
                
            logger.warning("هیچ اطلاعات کارمزدی در داده‌های وب‌هوک یافت نشد")
            return None
            
        except Exception as e:
            logger.error(f"خطا در استخراج کارمزد از داده‌های وب‌هوک: {str(e)}")
            return None

    def _get_explorer_url(self, session, blockchain_id, tx_hash):
        """
        ساخت آدرس explorer برای تراکنش بر اساس نوع بلاکچین
        
        Args:
            session (Session): جلسه فعال دیتابیس
            blockchain_id (int): شناسه بلاکچین در دیتابیس
            tx_hash (str): هش تراکنش
            
        Returns:
            str: آدرس کامل explorer یا None در صورت خطا
        """
        try:
            if not blockchain_id or not tx_hash:
                logger.warning("شناسه بلاکچین یا هش تراکنش برای ساخت آدرس explorer خالی است")
                return None
            
            # دریافت اطلاعات بلاکچین از دیتابیس
            query = text("""
                SELECT Symbol, BlockchainName FROM Blockchains 
                WHERE BlockchainID = :blockchain_id
            """)
            
            result = session.execute(query, {'blockchain_id': blockchain_id})
            blockchain_data = result.fetchone()
            
            if not blockchain_data:
                logger.warning(f"اطلاعات بلاکچین با شناسه {blockchain_id} یافت نشد")
                return None
            
            # استخراج نماد و نام بلاکچین
            symbol = blockchain_data[0]
            blockchain_name = blockchain_data[1]
            
            # تبدیل به حروف بزرگ برای مقایسه راحت‌تر
            found_blockchain = symbol.upper() if symbol else ''
            blockchain_name_upper = blockchain_name.upper() if blockchain_name else ''
            
            logger.info(f"بلاکچین یافت شده: {found_blockchain} (نام: {blockchain_name})")
            
            # ساخت آدرس explorer بر اساس بلاکچین
            explorer_url = None
            
            # اتریوم و شبکه‌های مرتبط
            if found_blockchain in ['ETH', 'ETHEREUM'] or 'ETHEREUM' in blockchain_name_upper:
                explorer_url = f"https://etherscan.io/tx/{tx_hash}"
            
            # بایننس اسمارت چین
            elif found_blockchain in ['BSC', 'BNB', 'BINANCE'] or 'BINANCE' in blockchain_name_upper:
                explorer_url = f"https://bscscan.com/tx/{tx_hash}"
            
            # پالیگان (ماتیک)
            elif found_blockchain in ['MATIC', 'POLYGON'] or 'POLYGON' in blockchain_name_upper:
                explorer_url = f"https://polygonscan.com/tx/{tx_hash}"
            
            # ترون
            elif found_blockchain in ['TRX', 'TRON'] or 'TRON' in blockchain_name_upper:
                explorer_url = f"https://tronscan.org/#/transaction/{tx_hash}"
            
            # بیت‌کوین
            elif found_blockchain in ['BTC', 'BITCOIN'] or 'BITCOIN' in blockchain_name_upper:
                explorer_url = f"https://www.blockchain.com/explorer/transactions/btc/{tx_hash}"
            
            # لایت‌کوین
            elif found_blockchain in ['LTC', 'LITECOIN'] or 'LITECOIN' in blockchain_name_upper:
                explorer_url = f"https://blockchair.com/litecoin/transaction/{tx_hash}"
            
            # دوج‌کوین
            elif found_blockchain in ['DOGE', 'DOGECOIN'] or 'DOGECOIN' in blockchain_name_upper:
                explorer_url = f"https://blockchair.com/dogecoin/transaction/{tx_hash}"
            
            # سولانا
            elif found_blockchain in ['SOL', 'SOLANA'] or 'SOLANA' in blockchain_name_upper:
                explorer_url = f"https://solscan.io/tx/{tx_hash}"
            
            # کاردانو
            elif found_blockchain in ['ADA', 'CARDANO'] or 'CARDANO' in blockchain_name_upper:
                explorer_url = f"https://cardanoscan.io/transaction/{tx_hash}"
            
            # آوالانچ
            elif found_blockchain in ['AVAX', 'AVALANCHE'] or 'AVALANCHE' in blockchain_name_upper:
                explorer_url = f"https://snowtrace.io/tx/{tx_hash}"
            
            # فنتوم
            elif found_blockchain in ['FTM', 'FANTOM'] or 'FANTOM' in blockchain_name_upper:
                explorer_url = f"https://ftmscan.com/tx/{tx_hash}"
            
            # آربیتروم
            elif found_blockchain in ['ARB', 'ARBITRUM'] or 'ARBITRUM' in blockchain_name_upper:
                explorer_url = f"https://arbiscan.io/tx/{tx_hash}"
            
            # اپتیمیسم
            elif found_blockchain in ['OP', 'OPTIMISM'] or 'OPTIMISM' in blockchain_name_upper:
                explorer_url = f"https://optimistic.etherscan.io/tx/{tx_hash}"
            
            # سایر بلاکچین‌ها
            else:
                # برای سایر بلاکچین‌ها از blockchair استفاده می‌کنیم
                explorer_url = f"https://blockchair.com/search?q={tx_hash}"
                logger.warning(f"بلاکچین ناشناخته: {found_blockchain}, استفاده از آدرس عمومی explorer")
            
            logger.info(f"آدرس explorer ساخته شده برای {found_blockchain}: {explorer_url}")
            return explorer_url
            
        except Exception as e:
            logger.error(f"خطا در ساخت آدرس explorer: {str(e)}")
            return None

    def save_transaction(self, blockchain, transaction_id, relevant_addresses, webhook_data, block_number=None, timestamp=None, from_address=None, to_address=None, token_contract=None, price=None, fee=None):
        """
        Save transaction to database
        
        Args:
            blockchain (str): Blockchain symbol
            transaction_id (str): Transaction ID/hash
            relevant_addresses (list): List of relevant addresses
            webhook_data (dict): Webhook data
            block_number (int): Block number
            timestamp (datetime): Transaction timestamp
            from_address (str): Sender address
            to_address (str): Recipient address
            token_contract (str): Token contract address
            price (float): Token price
            fee (float): Transaction fee
            
        Returns:
            bool: True if transaction was saved successfully
        """
        try:
            engine = self._get_engine()
            logger.info(f"Saving transaction {transaction_id} to database")
            
            # Check if we have relevant addresses
            if not relevant_addresses or len(relevant_addresses) == 0:
                logger.error(f"No relevant addresses provided for transaction {transaction_id}")
                return False
                
            # Get the first address to use for the transfer record
            address_info = relevant_addresses[0]
            address_id = address_info.get('address_id')
            wallet_id = address_info.get('wallet_id')
            direction = address_info.get('direction', 'inbound')
            
            # Make sure we have the required address and wallet IDs
            if not address_id or not wallet_id:
                logger.error(f"Missing required address_id or wallet_id for transaction {transaction_id}")
                return False
                
            # Check if transaction already exists
            with Session(engine) as session:
                existing = self.check_transaction_exists(session, transaction_id, address_id, wallet_id)
                if existing:
                    logger.info(f"Transaction {transaction_id} already exists in database, skipping")
                    return True
                
                # Get transaction details from webhook data
                block = block_number or webhook_data.get('blockNumber') or webhook_data.get('blockHeight')
                tx_timestamp = timestamp
                
                if not tx_timestamp:
                    if 'timestamp' in webhook_data:
                        tx_ts = webhook_data['timestamp']
                        # Convert from milliseconds if needed
                        if isinstance(tx_ts, int) and tx_ts > 1000000000000:
                            tx_ts = tx_ts / 1000
                        tx_timestamp = datetime.fromtimestamp(tx_ts)
                    else:
                        tx_timestamp = datetime.now()
                
                # Extract token details from webhook
                token_symbol = webhook_data.get('tokenSymbol') or webhook_data.get('symbol') or webhook_data.get('asset')
                
                # Special handling for TRC20 token contract
                if token_contract and blockchain.upper() in ['TRX', 'TRON']:
                    # Check for NCC token
                    if token_contract == 'T9yYp7JUxypLk7GFhsLRj5jN6ZrNDcH2Cf' or token_contract == 'TCDgp5bwtixaShPifUm7HpZ71C1pe6zif1':
                        token_symbol = 'NCC'
                        logger.info(f"Mapped contract {token_contract} to token symbol NCC")
                
                # Extract value from webhook
                amount = webhook_data.get('amount') or webhook_data.get('value')
                if amount is None:
                    amount = 0
                    
                # Try to parse amount as float
                try:
                    amount = float(amount)
                except (ValueError, TypeError):
                    amount = 0
                
                # Determine asset type (native or token)
                asset_type = "native"
                if token_contract:
                    asset_type = "token"
                elif webhook_data.get('type') == 'token' or webhook_data.get('type') == 'trc20':
                    asset_type = "token"
                
                # Standardize TRX/TRON symbol
                if token_symbol and token_symbol.upper() in ['TRON', 'TRX']:
                    token_symbol = 'TRX'
                
                # Convert BSC to BNB for transfers table
                if token_symbol and token_symbol.upper() == 'BSC':
                    token_symbol = 'BNB'
                    logger.info(f"Converting token symbol from BSC to BNB for transfer {transaction_id}")
                
                # Insert transaction into database
                blockchain_id = self._get_blockchain_id(session, blockchain)
                if not blockchain_id:
                    logger.error(f"Could not find blockchain ID for {blockchain}")
                    return False
                
                # Get current token price if not provided
                if price is None:
                    price = self._get_current_price(session, token_symbol or blockchain, blockchain)
                
                # Calculate total price (amount * price)
                if price is not None and amount is not None:
                    total_price = float(amount) * float(price)
                else:
                    total_price = None
                
                # Get transaction fee if not provided
                if fee is None:
                    fee = self._get_transaction_fee(transaction_id, blockchain)
                
                # Get explorer URL
                explorer_url = self._get_explorer_url(session, blockchain_id, transaction_id)
                
                # Prepare base transaction data with the correct column names
                tx_data = {
                    'TxHash': str(transaction_id).strip()[:100],  # Ensure TxHash doesn't exceed 100 chars
                    'BlockchainID': blockchain_id,
                    'AddressID': address_id,
                    'WalletID': str(wallet_id).strip()[:50],  # Ensure WalletID doesn't exceed 50 chars
                    'BlockNumber': block,
                    'Timestamp': tx_timestamp,
                    'TokenContract': str(token_contract).strip()[:100] if token_contract else None,
                    'TokenSymbol': str(token_symbol or blockchain).strip()[:20],  # Ensure TokenSymbol doesn't exceed 20 chars
                    'FromAddress': str(from_address).strip()[:100] if from_address else None,
                    'ToAddress': str(to_address).strip()[:100] if to_address else None,
                    'Amount': amount,
                    'AssetType': str(asset_type).strip()[:20] if asset_type else 'native',  # Ensure AssetType doesn't exceed 20 chars
                    'Direction': str(direction).strip()[:10],  # Ensure Direction doesn't exceed 10 chars
                    'Fee': fee,
                    'Price': total_price,  # Store the calculated total price
                    'ExplorerUrl': explorer_url,
                    'CreatedAt': datetime.now(),
                    'UpdatedAt': datetime.now(),
                    'IsSuccessful': True,  # Default to True for incoming transactions
                    'Status': 'confirmed'  # Use 'confirmed' instead of 'completed' and ensure it doesn't exceed 20 chars
                }
                
                # Insert transaction with the correct column names from the transfers table
                insert_tx_query = text("""
                    INSERT INTO transfers (
                        TxHash, BlockchainID, AddressID, WalletID, BlockNumber, 
                        Timestamp, TokenContract, TokenSymbol, AssetType, Direction,
                        FromAddress, ToAddress, Amount, Fee,
                        Price, ExplorerUrl, CreatedAt, UpdatedAt,
                        IsSuccessful, Status
                    ) VALUES (
                        :TxHash, :BlockchainID, :AddressID, :WalletID, :BlockNumber,
                        :Timestamp, :TokenContract, :TokenSymbol, :AssetType, :Direction,
                        :FromAddress, :ToAddress, :Amount, :Fee,
                        :Price, :ExplorerUrl, :CreatedAt, :UpdatedAt,
                        :IsSuccessful, :Status
                    )
                """)
                
                # Remove RawData from tx_data if it exists
                if 'RawData' in tx_data:
                    del tx_data['RawData']
                
                session.execute(insert_tx_query, tx_data)
                
                # Process relevant addresses
                for address_info in relevant_addresses:
                    # Save transaction log
                    self._save_transaction_log(
                        session,
                        blockchain_id=blockchain_id,
                        transaction_id=transaction_id,
                        wallet_id=address_info.get('wallet_id'),
                        direction=address_info.get('direction'),
                        amount=webhook_data.get('amount') or webhook_data.get('value'),
                        token_symbol=token_symbol or blockchain
                    )
                
                # Commit changes
                session.commit()
                logger.info(f"Transaction {transaction_id} saved successfully")
                return True
                
        except Exception as e:
            logger.error(f"Error saving transaction {transaction_id}: {str(e)}")
            logger.exception(e)
            return False

    def _save_transaction_log(self, session, blockchain_id, transaction_id, wallet_id=None, direction=None, amount=None, token_symbol=None):
        """
        ذخیره اطلاعات پردازش تراکنش در جدول لاگ
        """
        try:
            # قبل از درج، بررسی وجود رکورد مشابه (صرف‌نظر از token_symbol)
            check_query = text("""
                SELECT COUNT(*) FROM balance_update_log
                WHERE wallet_id = :wallet_id AND tx_id = :tx_id
            """)
            exists_count = session.execute(check_query, {
                'wallet_id': wallet_id,
                'tx_id': transaction_id
            }).scalar()
            if exists_count > 0:
                logger.warning(f"[LOG] رکورد لاگ برای wallet_id={wallet_id} و tx_id={transaction_id} قبلاً وجود دارد، درج مجدد انجام نمی‌شود.")
                return True

            # گرفتن اطلاعات تراکنش از first_address موجود در relevant_addresses اگر در دسترس باشد
            # اصلاح کوئری مطابق با ساختار جدول
            if amount:
                from decimal import Decimal, getcontext, ROUND_DOWN
                getcontext().prec = 38  # کل ارقام معنی‌دار
                amount_decimal = Decimal(str(amount))
                # محدود کردن به 18 رقم اعشار
                amount_formatted = str(amount_decimal.quantize(Decimal('0.000000000000000001'), rounding=ROUND_DOWN))
            else:
                amount_formatted = '0'
                
            insert_log = text("""
                    INSERT INTO balance_update_log (
                        wallet_id, tx_id, direction, amount, token_symbol, blockchain, created_at
                    ) VALUES (
                        :wallet_id, :tx_id, :direction, :amount, :token_symbol, :blockchain, NOW()
                    )
                """)
            
            session.execute(insert_log, {
                'wallet_id': wallet_id or 'unknown',  # مقدار پیش‌فرض برای wallet_id
                'tx_id': transaction_id,
                'direction': direction or 'unknown',  # مقدار پیش‌فرض برای direction
                'amount': amount_formatted,            # مقدار محدود شده برای amount
                'token_symbol': token_symbol or 'unknown',  # مقدار پیش‌فرض برای token_symbol
                'blockchain': blockchain_id
            })
            session.commit()
            logger.debug(f"Transaction {transaction_id} logged to balance_update_log")
            return True
        except Exception as e:
            logger.error(f"خطا در ذخیره اطلاعات تراکنش {transaction_id} در جدول لاگ: {str(e)}")
            return False
    
    def check_transaction_already_processed(self, transaction_id, blockchain):
        """
        بررسی اینکه آیا یک تراکنش (با هر جهتی) قبلاً پردازش شده است یا خیر
        
        Args:
            transaction_id (str): شناسه تراکنش
            blockchain (str): نام بلاکچین
            
        Returns:
            bool: True اگر تراکنش قبلاً با هر جهتی پردازش شده باشد، در غیر این صورت False
        """
        try:
            # ایجاد یک session جدید برای جستجو
            with self._get_engine().connect() as connection:
                with Session(connection) as session:
                    # بررسی وجود تراکنش در لاگ با هر جهتی (بدون در نظر گرفتن direction)
                    check_query = text("""
                        SELECT COUNT(*) FROM balance_update_log 
                        WHERE tx_id = :transaction_id
                    """)
                    
                    count = session.execute(check_query, {
                        'transaction_id': transaction_id
                    }).scalar()
                    
                    if count > 0:
                        logger.warning(f"تراکنش {transaction_id} قبلاً برای بلاکچین {blockchain} (با هر جهتی) پردازش شده است")
                        return True
                        
                    return False
            
        except Exception as e:
            logger.warning(f"خطا در بررسی پردازش قبلی تراکنش: {str(e)}")
            # در صورت خطا، بهتر است ادامه دهیم و تراکنش را پردازش کنیم
            return False
    
    def update_wallet_balance(self, address_info, blockchain, token_contract=None, token_symbol=None):
        """
        به‌روزرسانی موجودی کیف پول از بلاکچین
        
        Args:
            address_info (dict): اطلاعات آدرس کیف پول
            blockchain (str): نام بلاکچین
            token_contract (str, optional): آدرس قرارداد هوشمند برای توکن‌ها
            token_symbol (str, optional): نماد توکن
            
        Returns:
            bool: نتیجه عملیات
        """
        # استاندارد‌سازی نام‌های ارز و بلاکچین
        if blockchain and blockchain.upper() in ['TRON', 'TRX']:
            blockchain = 'Tron'  # استفاده از فرمت استاندارد "Tron" در دیتابیس
        
        # تبدیل TRON به TRX برای همخوانی با دیتابیس
        if token_symbol and token_symbol.upper() == 'TRON':
            token_symbol = 'TRX'
            logger.info(f"تبدیل نماد توکن TRON به TRX برای همخوانی با دیتابیس")
            
        # تبدیل BSC به BNB برای همخوانی با دیتابیس
        if blockchain and blockchain.upper() == 'BSC':
            blockchain = 'Binance Smart Chain'
            logger.info(f"تبدیل بلاکچین BSC به Binance Smart Chain برای همخوانی با دیتابیس")
            
        # اگر نماد توکن BSC است، آن را به BNB تبدیل می‌کنیم
        if token_symbol and token_symbol.upper() == 'BSC':
            token_symbol = 'BNB'
            logger.info(f"تبدیل نماد توکن BSC به BNB برای همخوانی با دیتابیس")
            
        logger.info(f"به‌روزرسانی موجودی کیف پول برای آدرس {address_info.get('public_address')} در بلاکچین {blockchain}")
        
        try:
            address_id = address_info.get('address_id')
            wallet_id = address_info.get('wallet_id')
            public_address = address_info.get('public_address')
            
            if not address_id or not wallet_id or not public_address:
                logger.error("اطلاعات ناقص آدرس کیف پول")
                return False
            
            # تعیین نماد توکن
            currency_symbol = token_symbol or blockchain
            
            logger.info(f"به‌روزرسانی موجودی {currency_symbol} برای کیف پول {wallet_id} (آدرس {public_address})")
            
            # ایجاد قفل برای این آدرس
            lock_key = f"balance_update_{public_address}"
            if not self._acquire_lock(lock_key):
                logger.warning(f"قفل برای آدرس {public_address} در دسترس نیست")
                return False
                
            try:
                # انتظار برای تأیید تراکنش در بلاکچین
                time.sleep(5)  # انتظار 5 ثانیه‌ای
                
                # دریافت موجودی از بلاکچین با مکانیزم تلاش مجدد
                max_retries = 3
                balance = None
                
                for attempt in range(max_retries):
                    try:
                        balance = self.blockchain_utils.get_address_balance(public_address, blockchain, token_contract)
                        if balance is not None:
                            break
                        time.sleep(2)  # انتظار قبل از تلاش مجدد
                    except Exception as e:
                        if attempt == max_retries - 1:
                            logger.error(f"خطا در دریافت موجودی بعد از {max_retries} تلاش: {str(e)}")
                            return False
                        time.sleep(2)
                
                if balance is None:
                    logger.error(f"خطا در دریافت موجودی برای آدرس {public_address}")
                    return False
                    
                logger.info(f"موجودی دریافت شده: {balance} {currency_symbol}")
                
                with Session(self._get_engine()) as session:
                    # دریافت شناسه کاربر از کیف پول
                    user_query = text("""
                        SELECT UserID FROM wallets WHERE WalletID = :wallet_id
                    """)
                    user_result = session.execute(user_query, {'wallet_id': wallet_id}).fetchone()
                    if not user_result:
                        logger.error(f"کاربری با کیف پول {wallet_id} یافت نشد")
                        return False
                    
                    user_id = user_result[0]
                    
                    # ابتدا شناسه بلاکچین را پیدا می‌کنیم
                    blockchain_id = self._get_blockchain_id(session, blockchain)
                    if not blockchain_id:
                        logger.error(f"بلاکچین {blockchain} در پایگاه داده یافت نشد")
                        return False
                    
                    # بررسی وجود رکورد موجودی در جدول userholding
                    if currency_symbol and currency_symbol.upper() in ['TRX', 'TRON']:
                        check_query = text("""
                            SELECT h.HoldingID, h.Balance 
                            FROM userholding h
                            JOIN currencies c ON h.CurrencyID = c.CurrencyID
                            JOIN blockchains b ON c.BlockchainID = b.BlockchainID
                            WHERE h.UserID = :user_id
                            AND (c.Symbol = 'TRX' OR c.CurrencyName = 'Tron')
                            AND b.BlockchainID = 2
                            LIMIT 1
                        """)
                        
                        result = session.execute(check_query, {
                            'user_id': user_id
                        }).fetchone()
                    else:
                        check_query = text("""
                            SELECT h.HoldingID, h.Balance 
                            FROM userholding h
                            WHERE h.UserID = :user_id
                            AND (h.Blockchain = :blockchain)
                            AND (
                                (:token_symbol IS NULL AND h.Symbol = :blockchain) OR
                                (h.Symbol = :token_symbol) OR 
                                (h.Symbol = :token_contract)
                            )
                            LIMIT 1
                        """)
                        
                        result = session.execute(check_query, {
                            'user_id': user_id,
                            'blockchain': blockchain,
                            'token_symbol': token_symbol,
                            'token_contract': token_contract
                        }).fetchone()
                    
                    if result:
                        # به‌روزرسانی رکورد موجودی موجود
                        holding_id = result[0]
                        current_balance = float(result[1])
                        
                        # بررسی تغییرات غیرمنطقی در موجودی
                        if balance == 0 and current_balance > 0:
                            logger.warning(f"موجودی جدید صفر است در حالی که موجودی قبلی {current_balance} بوده است")
                            # بررسی تاریخچه تراکنش‌ها
                            tx_history_query = text("""
                                SELECT SUM(CASE WHEN Direction = 'inbound' THEN Amount ELSE -Amount END) as net_amount
                                FROM transfers 
                                WHERE WalletID = :wallet_id 
                                AND TokenSymbol = :token_symbol
                                AND BlockchainID = :blockchain_id
                                AND IsSuccessful = 1
                            """)
                            
                            tx_result = session.execute(tx_history_query, {
                                'wallet_id': wallet_id,
                                'token_symbol': currency_symbol,
                                'blockchain_id': blockchain_id
                            }).fetchone()
                            
                            if tx_result and tx_result[0] is not None:
                                calculated_balance = float(tx_result[0])
                                if calculated_balance > 0:
                                    logger.warning(f"موجودی محاسبه شده از تاریخچه: {calculated_balance}")
                                    balance = calculated_balance
                        
                        logger.info(f"به‌روزرسانی موجودی {currency_symbol} از {current_balance} به {balance}")
                        
                        update_query = text("""
                            UPDATE userholding 
                            SET Balance = :balance, UpdatedAt = NOW()
                            WHERE HoldingID = :holding_id
                        """)
                        
                        # محدود کردن تعداد ارقام اعشار به 18 رقم
                        from decimal import Decimal, getcontext, ROUND_DOWN
                        getcontext().prec = 38  # کل ارقام معنی‌دار
                        balance_decimal = Decimal(str(balance))
                        # محدود کردن به 18 رقم اعشار
                        balance_formatted = balance_decimal.quantize(Decimal('0.000000000000000001'), rounding=ROUND_DOWN)
                        
                        session.execute(update_query, {
                            'balance': balance_formatted,
                            'holding_id': holding_id
                        })
                    else:
                        # ایجاد رکورد جدید
                        logger.info(f"ایجاد رکورد موجودی جدید برای {currency_symbol} با مقدار {balance}")
                        
                        # دریافت شناسه ارز با جستجوی بهتر
                        if currency_symbol and currency_symbol.upper() in ['TRX', 'TRON']:
                            currency_query = text("""
                                SELECT c.CurrencyID 
                                FROM currencies c
                                JOIN blockchains b ON c.BlockchainID = b.BlockchainID
                                WHERE (c.Symbol = 'TRX' OR c.CurrencyName = 'Tron')
                                AND b.BlockchainID = 2
                                LIMIT 1
                            """)
                            
                            currency_result = session.execute(currency_query).fetchone()
                        else:
                            currency_query = text("""
                                SELECT c.CurrencyID 
                                FROM currencies c
                                JOIN blockchains b ON c.BlockchainID = b.BlockchainID
                                WHERE c.Symbol = :symbol 
                                AND b.BlockchainID = :blockchain_id
                                LIMIT 1
                            """)
                            
                            currency_result = session.execute(currency_query, {
                                'symbol': currency_symbol, 
                                'blockchain_id': blockchain_id
                            }).fetchone()
                        
                        if not currency_result:
                            logger.error(f"ارز {currency_symbol} برای بلاکچین {blockchain} یافت نشد")
                            return False
                        
                        currency_id = currency_result[0]
                        
                        # محدود کردن تعداد ارقام اعشار به 18 رقم
                        from decimal import Decimal, getcontext, ROUND_DOWN
                        getcontext().prec = 38
                        balance_decimal = Decimal(str(balance))
                        balance_formatted = balance_decimal.quantize(Decimal('0.000000000000000001'), rounding=ROUND_DOWN)
                        
                        insert_query = text("""
                            INSERT INTO userholding (
                                UserID, CurrencyID, Balance, Symbol, Blockchain, IsToken, 
                                CreatedAt, UpdatedAt
                            ) VALUES (
                                :user_id, :currency_id, :balance, :symbol, :blockchain, 
                                :is_token, NOW(), NOW()
                            )
                        """)
                        
                        session.execute(insert_query, {
                            'user_id': user_id,
                            'currency_id': currency_id,
                            'balance': balance_formatted,
                            'symbol': currency_symbol,
                            'blockchain': blockchain,
                            'is_token': 1 if token_contract else 0
                        })
                    
                    session.commit()
                    logger.info(f"موجودی کیف پول با موفقیت به‌روزرسانی شد")
                    return True
                    
            finally:
                # آزاد کردن قفل
                self._release_lock(lock_key)
            
        except Exception as e:
            logger.error(f"خطا در به‌روزرسانی موجودی کیف پول: {str(e)}")
            return False

    def update_user_holding_balance(self, wallet_id, blockchain, token_symbol, direction, amount, tx_id, contract_address=None):
        """
        به‌روزرسانی موجودی کیف پول کاربر پس از انجام تراکنش
        
        Args:
            wallet_id (str): شناسه کیف پول
            blockchain (str): نام بلاکچین
            token_symbol (str): نماد توکن
            direction (str): جهت تراکنش (inbound/outbound)
            amount (float): مقدار تراکنش
            tx_id (str): شناسه تراکنش
            contract_address (str, optional): آدرس قرارداد هوشمند
            
        Returns:
            bool: نتیجه عملیات
        """
        logger.info(f"به‌روزرسانی موجودی کیف پول {wallet_id} برای ارز {token_symbol} در بلاکچین {blockchain}")
        
        try:
            # استانداردسازی نام بلاکچین و توکن
            standardized_blockchain = blockchain
            standardized_token = token_symbol
            
            # تبدیل BSC به BNB برای همخوانی با دیتابیس
            if blockchain and blockchain.upper() == 'BSC':
                standardized_blockchain = 'Binance Smart Chain'
                logger.info(f"تبدیل نام بلاکچین از BSC به Binance Smart Chain")
            
            # تبدیل TRON به TRX برای همخوانی با دیتابیس
            if blockchain and blockchain.upper() in ['TRON', 'TRX']:
                standardized_blockchain = 'Tron'
                logger.info(f"تبدیل نام بلاکچین از {blockchain} به Tron")
            
            # اگر توکن TRX/TRON است، استانداردسازی
            if token_symbol and token_symbol.upper() in ['TRON', 'TRX']:
                standardized_token = 'TRX'
                logger.info(f"تبدیل نماد توکن از {token_symbol} به TRX")
            
            # تبدیل BSC به BNB
            if token_symbol and token_symbol.upper() == 'BSC':
                standardized_token = 'BNB'
                logger.info(f"تبدیل نماد توکن از {token_symbol} به BNB")
            
            # تبدیل مقدار به فرمت صحیح
            try:
                if amount is None:
                    logger.error("مقدار تراکنش خالی است")
                    return False
                amount_value = float(amount)
            except (ValueError, TypeError):
                logger.error(f"خطا در تبدیل مقدار '{amount}' به عدد")
                return False
            
            with Session(self._get_engine()) as session:
                # بررسی وجود کیف پول
                wallet_query = text("""
                    SELECT UserID FROM wallets 
                    WHERE WalletID = :wallet_id
                """)
                
                wallet_result = session.execute(wallet_query, {'wallet_id': wallet_id}).fetchone()
                if not wallet_result:
                    logger.error(f"کیف پول {wallet_id} یافت نشد")
                    return False
                
                user_id = wallet_result[0]
                
                # دریافت شناسه بلاکچین
                blockchain_id = self._get_blockchain_id(session, standardized_blockchain)
                if not blockchain_id:
                    logger.error(f"بلاکچین {standardized_blockchain} در دیتابیس یافت نشد")
                    return False
                
                # دریافت مشخصات ارز
                currency_query = text("""
                    SELECT c.CurrencyID, c.Symbol
                    FROM currencies c
                    JOIN blockchains b ON c.BlockchainID = b.BlockchainID
                    WHERE b.BlockchainID = :blockchain_id AND 
                        (c.Symbol = :token_symbol OR c.Symbol = 'BSC' OR c.Symbol = 'BNB')
                    LIMIT 1
                """)
                
                params = {
                    'blockchain_id': blockchain_id,
                    'token_symbol': standardized_token,
                    'contract_address': contract_address if contract_address else ''
                }
                
                currency_result = session.execute(currency_query, params).fetchone()
                
                if not currency_result:
                    # تلاش دوم - جستجوی فازی
                    like_symbol = f"%{standardized_token}%"
                    fuzzy_query = text("""
                        SELECT c.CurrencyID, c.Symbol
                        FROM currencies c
                        JOIN blockchains b ON c.BlockchainID = b.BlockchainID
                        WHERE b.BlockchainID = :blockchain_id AND 
                            (c.Symbol LIKE :token_symbol_like OR c.CurrencyName LIKE :token_symbol_like)
                        LIMIT 1
                    """)
                    
                    currency_result = session.execute(fuzzy_query, {
                        'blockchain_id': blockchain_id,
                        'token_symbol_like': like_symbol
                    }).fetchone()
                    
                    # برای TRX جستجوی ویژه
                    if not currency_result and standardized_token.upper() == 'TRX':
                        special_trx_query = text("""
                            SELECT c.CurrencyID, c.Symbol
                            FROM currencies c
                            JOIN blockchains b ON c.BlockchainID = b.BlockchainID
                            WHERE b.BlockchainID = 2  # شناسه بلاکچین ترون
                            AND (c.Symbol = 'TRX' OR c.CurrencyName = 'Tron')
                            LIMIT 1
                        """)
                        
                        currency_result = session.execute(special_trx_query).fetchone()
                        
                        if currency_result:
                            logger.info(f"ارز TRX با جستجوی ویژه پیدا شد")
                    
                    # برای BSC/BNB جستجوی ویژه
                    if not currency_result and standardized_token.upper() == 'BNB':
                        special_bnb_query = text("""
                            SELECT c.CurrencyID, c.Symbol
                            FROM currencies c
                            JOIN blockchains b ON c.BlockchainID = b.BlockchainID
                            WHERE b.BlockchainID = :blockchain_id
                            AND (c.Symbol = 'BNB' OR c.CurrencyName = 'Binance Coin')
                            LIMIT 1
                        """)
                        
                        currency_result = session.execute(special_bnb_query, {
                            'blockchain_id': blockchain_id
                        }).fetchone()
                        
                        if currency_result:
                            logger.info(f"ارز BNB با جستجوی ویژه پیدا شد")
                
                if not currency_result:
                    # اگر ارز پیدا نشد، جستجوی کلی‌تر
                    final_fallback_query = text("""
                        SELECT c.CurrencyID, c.Symbol
                        FROM currencies c
                        JOIN blockchains b ON c.BlockchainID = b.BlockchainID
                        WHERE (b.Symbol LIKE :token_symbol_like OR
                            c.Symbol LIKE :token_symbol_like OR 
                            c.CurrencyName LIKE :token_symbol_like OR 
                            b.BlockchainName LIKE :token_symbol_like)
                        LIMIT 1
                    """)
                    
                    final_result = session.execute(final_fallback_query, {
                        'token_symbol_like': f"%{standardized_token}%"
                    }).fetchone()
                    
                    if final_result:
                        currency_id = final_result[0]
                        currency_symbol = final_result[1]
                        logger.info(f"ارز {currency_symbol} با جستجوی کلی پیدا شد")
                    else:
                        # اگر همچنان نیافتیم، لاگ را ثبت می‌کنیم تا از پردازش مجدد جلوگیری شود
                        self._save_transaction_log(session, blockchain_id, tx_id, wallet_id, direction, amount, standardized_token)
                        logger.error(f"ارز {standardized_token} در بلاکچین {standardized_blockchain} یافت نشد")
                        return False
                else:
                    currency_id = currency_result[0]
                    currency_symbol = currency_result[1]
                
                logger.info(f"شناسه ارز {currency_symbol}: {currency_id}")
                
                # بررسی وجود رکورد موجودی و به‌روزرسانی آن
                holding_query = text("""
                    SELECT h.HoldingID, h.Balance 
                    FROM userholding h
                    WHERE h.UserID = :user_id AND h.CurrencyID = :currency_id
                    LIMIT 1
                """)
                
                holding_result = session.execute(holding_query, {
                    'user_id': user_id,
                    'currency_id': currency_id
                }).fetchone()
                
                # تعیین مقدار جدید موجودی بسته به جهت تراکنش
                if holding_result:
                    holding_id = holding_result[0]
                    current_balance = float(holding_result[1])
                    
                    if direction == 'inbound':
                        new_balance = current_balance + amount_value
                    elif direction == 'outbound':
                        new_balance = current_balance - amount_value
                        if new_balance < 0:
                            new_balance = 0
                            logger.warning(f"تراکنش باعث منفی شدن موجودی می‌شد، موجودی به صفر تنظیم شد")
                    else:
                        logger.error(f"جهت تراکنش نامعتبر: {direction}")
                        return False
                    
                    # به‌روزرسانی موجودی
                    update_query = text("""
                        UPDATE userholding 
                        SET Balance = :balance, UpdatedAt = NOW()
                        WHERE HoldingID = :holding_id
                    """)
                    
                    # محدود کردن تعداد ارقام اعشار
                    from decimal import Decimal, getcontext, ROUND_DOWN
                    getcontext().prec = 38
                    balance_decimal = Decimal(str(new_balance))
                    balance_formatted = balance_decimal.quantize(Decimal('0.000000000000000001'), rounding=ROUND_DOWN)
                    
                    logger.info(f"به‌روزرسانی موجودی {currency_symbol} از {current_balance} به {balance_formatted}")
                    
                    session.execute(update_query, {
                        'balance': balance_formatted,
                        'holding_id': holding_id
                    })
                else:
                    # ایجاد رکورد جدید
                    # موجودی اولیه باید مثبت باشد
                    initial_balance = amount_value if direction == 'inbound' else 0
                    
                    # محدود کردن تعداد ارقام اعشار
                    from decimal import Decimal, getcontext, ROUND_DOWN
                    getcontext().prec = 38
                    balance_decimal = Decimal(str(initial_balance))
                    balance_formatted = balance_decimal.quantize(Decimal('0.000000000000000001'), rounding=ROUND_DOWN)
                    
                    logger.info(f"ایجاد رکورد جدید با موجودی اولیه {balance_formatted} {currency_symbol}")
                    
                    insert_query = text("""
                        INSERT INTO userholding (
                            UserID, CurrencyID, Balance, Symbol, Blockchain, IsToken, 
                            CreatedAt, UpdatedAt
                        ) VALUES (
                            :user_id, :currency_id, :balance, :symbol, :blockchain, 
                            :is_token, NOW(), NOW()
                        )
                    """)
                    
                    # تعیین نوع دارایی (توکن یا ارز بومی)
                    is_token = 1 if contract_address else 0
                    
                    session.execute(insert_query, {
                        'user_id': user_id,
                        'currency_id': currency_id,
                        'balance': balance_formatted,
                        'symbol': currency_symbol,
                        'blockchain': standardized_blockchain,
                        'is_token': is_token
                    })
                
                # ثبت تراکنش در جدول لاگ
                self._save_transaction_log(session, blockchain_id, tx_id, wallet_id, direction, amount_value, standardized_token)
                
                session.commit()
                logger.info(f"موجودی کیف پول با موفقیت به‌روزرسانی شد")
                return True
        
        except Exception as e:
            logger.error(f"خطا در به‌روزرسانی موجودی کیف پول: {str(e)}", exc_info=True)
            return False

    def update_transaction_status(self, tx_hash, blockchain, tx_details):
        """
        به‌روزرسانی وضعیت تراکنش در جدول Transfers
        
        Args:
            tx_hash (str): هش تراکنش
            blockchain (str): نام بلاکچین
            tx_details (dict): جزئیات تراکنش
            
        Returns:
            dict: نتیجه به‌روزرسانی
        """
        try:
            logger.info(f"به‌روزرسانی وضعیت تراکنش {tx_hash} در بلاکچین {blockchain}")
            
            # استخراج وضعیت تراکنش
            status = tx_details.get('status')
            if not status:
                logger.warning(f"هیچ وضعیتی برای تراکنش {tx_hash} یافت نشد")
                return {"success": False, "error": "وضعیت تراکنش یافت نشد"}
                
            logger.info(f"وضعیت تراکنش {tx_hash}: {status}")
            
            # استفاده از اتصال به دیتابیس
            engine = self._get_engine()
            with Session(engine) as session:
                # به‌روزرسانی در جدول Transfers
                update_query = text("""
                    UPDATE transfers 
                    SET Status = :status, UpdatedAt = NOW() 
                    WHERE TxHash = :tx_hash
                """)
                result = session.execute(update_query, {"status": status, "tx_hash": tx_hash})
                
                affected_rows = result.rowcount
                session.commit()
                
                if affected_rows > 0:
                    logger.info(f"وضعیت تراکنش {tx_hash} با موفقیت به {status} در جدول Transfers به‌روزرسانی شد")
                    return {"success": True, "status": status, "affected_rows": affected_rows}
                else:
                    logger.warning(f"هیچ تراکنشی با هش {tx_hash} در جدول Transfers برای به‌روزرسانی یافت نشد")
                    
                    # بررسی وجود جدول Transfers
                    check_table = text("SHOW TABLES LIKE 'transfers'")
                    table_exists = session.execute(check_table).fetchone() is not None
                    
                    if not table_exists:
                        logger.error("جدول Transfers در دیتابیس وجود ندارد")
                        return {"success": False, "error": "جدول Transfers وجود ندارد"}
                    
                    return {"success": False, "error": "تراکنش یافت نشد"}
                
        except Exception as e:
            logger.error(f"خطا در به‌روزرسانی وضعیت تراکنش: {str(e)}", exc_info=True)
            return {"success": False, "error": str(e)}

    def verify_user_holding_balances(self, user_id=None, fix_discrepancies=False):
        """
        Verify that all user holding balances match the expected balance from transfers history
        
        Args:
            user_id (str, optional): ID of specific user to check, or None for all users
            fix_discrepancies (bool): Whether to fix balance discrepancies automatically
            
        Returns:
            dict: Results of the verification
        """
        try:
            from decimal import Decimal
            import datetime
            
            engine = self._get_engine()
            results = {
                "verified_count": 0,
                "discrepancy_count": 0,
                "fixed_count": 0,
                "details": []
            }
            
            with Session(engine) as session:
                # Query for getting user holdings
                if user_id:
                    logger.info(f"Verifying holdings for user {user_id}")
                    holdings_query = text("""
                        SELECT h.HoldingID, h.UserID, h.Symbol, h.Blockchain, h.Balance, h.IsToken 
                        FROM userholding h
                        WHERE h.UserID = :user_id
                    """)
                    holdings = session.execute(holdings_query, {"user_id": user_id}).fetchall()
                else:
                    logger.info("Verifying holdings for all users")
                    holdings_query = text("""
                        SELECT h.HoldingID, h.UserID, h.Symbol, h.Blockchain, h.Balance, h.IsToken 
                        FROM userholding h
                    """)
                    holdings = session.execute(holdings_query).fetchall()
                
                logger.info(f"Found {len(holdings)} holdings to verify")
                
                # Verify each holding
                for holding in holdings:
                    holding_id = holding[0]
                    user_id = holding[1]
                    symbol = holding[2]
                    blockchain = holding[3]
                    current_balance = Decimal(str(holding[4]))
                    is_token = holding[5]
                    
                    # Get user's wallets
                    wallets_query = text("""
                        SELECT WalletID FROM wallets 
                        WHERE UserID = :user_id
                    """)
                    wallets = session.execute(wallets_query, {"user_id": user_id}).fetchall()
                    wallet_ids = [w[0] for w in wallets]
                    
                    if not wallet_ids:
                        logger.warning(f"No wallets found for user {user_id}")
                        continue
                    
                    # Get blockchain ID
                    blockchain_query = text("""
                        SELECT BlockchainID FROM blockchains 
                        WHERE BlockchainName = :blockchain
                    """)
                    blockchain_result = session.execute(blockchain_query, {"blockchain": blockchain}).fetchone()
                    
                    if not blockchain_result:
                        logger.warning(f"Blockchain {blockchain} not found")
                        continue
                    
                    blockchain_id = blockchain_result[0]
                    
                    # Calculate expected balance from transfers
                    inbound_sum_query = text("""
                        SELECT COALESCE(SUM(Amount), 0) FROM transfers 
                        WHERE WalletID IN :wallet_ids
                        AND TokenSymbol = :symbol
                        AND BlockchainID = :blockchain_id
                        AND Direction = 'inbound'
                        AND IsSuccessful = 1
                    """)
                    
                    outbound_sum_query = text("""
                        SELECT COALESCE(SUM(Amount), 0) FROM transfers 
                        WHERE WalletID IN :wallet_ids
                        AND TokenSymbol = :symbol
                        AND BlockchainID = :blockchain_id
                        AND Direction = 'outbound'
                        AND IsSuccessful = 1
                    """)
                    
                    try:
                        inbound_sum = Decimal(str(session.execute(inbound_sum_query, {
                            "wallet_ids": tuple(wallet_ids),
                            "symbol": symbol,
                            "blockchain_id": blockchain_id
                        }).scalar() or 0))
                        
                        outbound_sum = Decimal(str(session.execute(outbound_sum_query, {
                            "wallet_ids": tuple(wallet_ids),
                            "symbol": symbol,
                            "blockchain_id": blockchain_id
                        }).scalar() or 0))
                        
                        # Calculate expected balance, ensuring it's never negative
                        expected_balance = max(inbound_sum - outbound_sum, Decimal('0'))
                        
                        # Compare with current balance
                        if abs(expected_balance - current_balance) < Decimal('0.000000001'):
                            # Balance is correct (allowing for very small rounding differences)
                            results["verified_count"] += 1
                            logger.info(f"Holding {holding_id} for {symbol} has correct balance: {current_balance}")
                        else:
                            # Balance discrepancy found
                            results["discrepancy_count"] += 1
                            discrepancy = abs(expected_balance - current_balance)
                            logger.warning(f"Balance discrepancy for holding {holding_id}, {symbol}: "
                                          f"Current={current_balance}, Expected={expected_balance}, "
                                          f"Difference={discrepancy}")
                            
                            # Add details to results
                            discrepancy_info = {
                                "holding_id": holding_id,
                                "user_id": user_id,
                                "symbol": symbol,
                                "blockchain": blockchain,
                                "current_balance": str(current_balance),
                                "expected_balance": str(expected_balance),
                                "difference": str(discrepancy),
                                "fixed": False
                            }
                            
                            # Fix the discrepancy if requested
                            if fix_discrepancies:
                                update_query = text("""
                                    UPDATE userholding 
                                    SET Balance = :balance, 
                                        LastUpdated = NOW(), 
                                        UpdatedAt = NOW(), 
                                        RawData = JSON_OBJECT('original_balance', :original_balance, 'corrected_balance', :balance, 'correction_date', :correction_date)
                                    WHERE HoldingID = :holding_id
                                """)
                                
                                session.execute(update_query, {
                                    "balance": str(expected_balance),
                                    "original_balance": str(current_balance),
                                    "correction_date": datetime.datetime.now().isoformat(),
                                    "holding_id": holding_id
                                })
                                
                                session.commit()
                                results["fixed_count"] += 1
                                discrepancy_info["fixed"] = True
                                logger.info(f"Fixed balance for holding {holding_id} to {expected_balance}")
                            
                            results["details"].append(discrepancy_info)
                    
                    except Exception as e:
                        logger.error(f"Error verifying balance for holding {holding_id}: {str(e)}", exc_info=True)
                        results["details"].append({
                            "holding_id": holding_id,
                            "user_id": user_id,
                            "symbol": symbol,
                            "blockchain": blockchain,
                            "error": str(e),
                            "fixed": False
                        })
            
            # Summarize results
            total_checked = results["verified_count"] + results["discrepancy_count"]
            if total_checked > 0:
                accuracy_percentage = (results["verified_count"] / total_checked) * 100
            else:
                accuracy_percentage = 0
                
            results["summary"] = {
                "total_checked": total_checked,
                "accuracy_percentage": round(accuracy_percentage, 2),
                "fixed_percentage": round((results["fixed_count"] / results["discrepancy_count"]) * 100, 2) if results["discrepancy_count"] > 0 else 0
            }
            
            logger.info(f"Verification completed: {results['verified_count']} correct, "
                      f"{results['discrepancy_count']} discrepancies, "
                      f"{results['fixed_count']} fixed. "
                      f"Accuracy: {accuracy_percentage:.2f}%")
            
            return results
            
        except Exception as e:
            logger.error(f"Error in verify_user_holding_balances: {str(e)}", exc_info=True)
            return {
                "success": False,
                "error": str(e)
            } 

    def _get_blockchain_id(self, session, blockchain_symbol):
        """
        دریافت شناسه بلاکچین از نماد آن
        
        Args:
            session: جلسه دیتابیس
            blockchain_symbol (str): نماد بلاکچین
            
        Returns:
            int: شناسه بلاکچین یا None در صورت عدم وجود
        """
        try:
            if not blockchain_symbol:
                logger.error("نماد بلاکچین خالی است")
                return None
                
            # تبدیل BSC به BNB برای همخوانی با دیتابیس
            if blockchain_symbol.upper() == 'BSC':
                blockchain_symbol = 'BNB'
                logger.info(f"تبدیل بلاکچین BSC به BNB برای همخوانی با دیتابیس")
                
            logger.info(f"دریافت شناسه بلاکچین برای نماد {blockchain_symbol}")
            
            # تبدیل نماد بلاکچین به حروف بزرگ
            blockchain_symbol_upper = blockchain_symbol.upper()
            
            # شناسایی مستقیم BSC/BNB
            if blockchain_symbol_upper in ['BSC', 'BNB']:
                # برای BSC و BNB، هر دو را بررسی می‌کنیم
                logger.info(f"جستجوی ویژه برای بلاکچین BSC/BNB")
                query = text("""
                    SELECT BlockchainID, Symbol, BlockchainName 
                    FROM blockchains
                    WHERE Symbol IN ('BSC', 'BNB') OR 
                          BlockchainName LIKE '%Binance%' OR 
                          BlockchainName LIKE '%BSC%'
                    LIMIT 1
                """)
                result = session.execute(query).fetchone()
                if result:
                    logger.info(f"شناسه بلاکچین BSC/BNB: {result[0]} یافت شد (نماد: {result[1]}, نام: {result[2]})")
                    return result[0]
            
            # ساخت لیست نمادهای احتمالی برای جستجو
            blockchain_variations = [blockchain_symbol, blockchain_symbol_upper, blockchain_symbol.lower()]
            
            # اضافه کردن نمادهای معادل برای برخی بلاکچین‌ها
            if blockchain_symbol_upper == 'ETH':
                blockchain_variations.extend(['ETHEREUM', 'ethereum'])
            elif blockchain_symbol_upper == 'BTC':
                blockchain_variations.extend(['BITCOIN', 'bitcoin'])
            elif blockchain_symbol_upper == 'LTC':
                blockchain_variations.extend(['LITECOIN', 'litecoin'])
            elif blockchain_symbol_upper == 'BSC':
                blockchain_variations.extend(['BNB', 'BINANCE', 'binance'])
            elif blockchain_symbol_upper == 'BNB':
                blockchain_variations.extend(['BSC', 'BINANCE', 'binance'])
            
            # ساخت شرط OR برای جستجوی نماد در فیلدهای مختلف
            symbols_placeholders = ':symbol_' + ', :symbol_'.join(str(i) for i in range(len(blockchain_variations)))
            symbols_params = {f'symbol_{i}': symbol for i, symbol in enumerate(blockchain_variations)}
            
            # کوئری جستجوی بلاکچین
            query = text(f"""
                SELECT BlockchainID, Symbol, BlockchainName 
                FROM blockchains
                WHERE Symbol IN ({symbols_placeholders})
                OR BlockchainName IN ({symbols_placeholders})
                LIMIT 1
            """)
            
            # اجرای کوئری با پارامترها
            result = session.execute(query, symbols_params).fetchone()
            
            if result:
                logger.info(f"شناسه بلاکچین {result[0]} برای نماد {blockchain_symbol} یافت شد (نماد: {result[1]}, نام: {result[2]})")
                return result[0]
                
            # اگر بلاکچین پیدا نشد، خطای مناسب را لاگ می‌کنیم
            logger.warning(f"بلاکچین با نماد {blockchain_symbol} یافت نشد")
            
            # موارد خاص - جستجوی نام‌های متناظر
            blockchain_name_upper = blockchain_symbol_upper
            if blockchain_symbol_upper == 'BNB' or blockchain_symbol_upper == 'BSC':
                # برای BNB باید به دنبال Binance بگردیم
                logger.info(f"جستجوی بلاکچین Binance Smart Chain برای نماد {blockchain_symbol}")
                
                query = text("""
                    SELECT BlockchainID, Symbol, BlockchainName 
                    FROM blockchains
                    WHERE BlockchainName LIKE '%Binance%' OR BlockchainName LIKE '%BSC%' OR Symbol = 'BNB' OR Symbol = 'BSC'
                    LIMIT 1
                """)
                
                result = session.execute(query).fetchone()
                
                if result:
                    logger.info(f"شناسه بلاکچین {result[0]} برای Binance Smart Chain یافت شد (نماد: {result[1]}, نام: {result[2]})")
                    return result[0]
            
            # اگر با روش‌های بالا پیدا نشد، تلاش می‌کنیم با LIKE جستجو کنیم
            logger.info(f"جستجوی بلاکچین با LIKE برای نماد {blockchain_symbol}")
            query = text("""
                SELECT BlockchainID, Symbol, BlockchainName 
                FROM blockchains
                WHERE Symbol LIKE :like_symbol
                OR BlockchainName LIKE :like_name
                LIMIT 1
            """)
            
            result = session.execute(query, {
                'like_symbol': f'%{blockchain_symbol}%',
                'like_name': f'%{blockchain_symbol}%'
            }).fetchone()
            
            if result:
                logger.info(f"شناسه بلاکچین {result[0]} با LIKE برای نماد {blockchain_symbol} یافت شد (نماد: {result[1]}, نام: {result[2]})")
                return result[0]
            
            # اگر هیچ بلاکچینی پیدا نشد
            logger.error(f"هیچ بلاکچینی برای نماد {blockchain_symbol} یافت نشد")
            return None
            
        except Exception as e:
            logger.error(f"خطا در دریافت شناسه بلاکچین: {str(e)}")
            return None 

    def _get_token_info(self, session, token_contract=None, token_symbol=None, blockchain=None):
        """
        Get token information from database
        
        Args:
            session (Session): Database session
            token_contract (str): Token contract address
            token_symbol (str): Token symbol
            blockchain (str): Blockchain symbol
            
        Returns:
            dict: Token information or None
        """
        try:
            # If we have a contract address, try to get token info from contract
            if token_contract:
                query = text("""
                    SELECT c.Symbol, c.DecimalPlaces, c.CurrencyID 
                    FROM currencies c
                    JOIN blockchains b ON c.BlockchainID = b.BlockchainID
                    WHERE LOWER(c.SmartContractAddress) = LOWER(:contract)
                    AND (b.Symbol = :blockchain OR b.BlockchainName = :blockchain)
                    LIMIT 1
                """)
                
                result = session.execute(query, {
                    'contract': token_contract,
                    'blockchain': blockchain
                }).fetchone()
                
                if result:
                    return {
                        'symbol': result[0],
                        'decimals': result[1],
                        'currency_id': result[2]
                    }
                
                # If not found with exact blockchain, try without blockchain constraint
                query = text("""
                    SELECT c.Symbol, c.DecimalPlaces, c.CurrencyID 
                    FROM currencies c
                    WHERE LOWER(c.SmartContractAddress) = LOWER(:contract)
                    LIMIT 1
                """)
                
                result = session.execute(query, {'contract': token_contract}).fetchone()
                
                if result:
                    return {
                        'symbol': result[0],
                        'decimals': result[1],
                        'currency_id': result[2]
                    }
            
            # If we have a token symbol, get info by symbol
            if token_symbol:
                query = text("""
                    SELECT c.Symbol, c.DecimalPlaces, c.CurrencyID 
                    FROM currencies c
                    JOIN blockchains b ON c.BlockchainID = b.BlockchainID
                    WHERE LOWER(c.Symbol) = LOWER(:symbol)
                    AND (b.Symbol = :blockchain OR b.BlockchainName = :blockchain)
                    LIMIT 1
                """)
                
                result = session.execute(query, {
                    'symbol': token_symbol,
                    'blockchain': blockchain
                }).fetchone()
                
                if result:
                    return {
                        'symbol': result[0],
                        'decimals': result[1],
                        'currency_id': result[2]
                    }
            
            # If still not found, return None
            return None
            
        except Exception as e:
            logger.error(f"Error getting token info: {str(e)}")
            return None