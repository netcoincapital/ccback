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
                
            logger.debug(f"دریافت قیمت برای ارز {token_symbol} در بلاکچین {blockchain}")
            
            # ابتدا از جدول currencies مقدار CurrencyID را دریافت می‌کنیم
            currency_query = text("""
                SELECT c.CurrencyID
                FROM currencies c
                JOIN blockchains b ON c.BlockchainID = b.BlockchainID
                WHERE c.Symbol = :symbol AND b.Symbol = :blockchain
                LIMIT 1
            """)
            
            result = session.execute(currency_query, {'symbol': token_symbol, 'blockchain': blockchain})
            currency_row = result.fetchone()
            
            if not currency_row:
                logger.warning(f"هیچ رکوردی در جدول currencies برای {token_symbol} در بلاکچین {blockchain} یافت نشد")
                
                # تلاش برای یافتن با نماد دقیق بدون در نظر گرفتن بلاکچین
                fallback_query = text("""
                    SELECT CurrencyID
                    FROM currencies
                    WHERE Symbol = :symbol
                    LIMIT 1
                """)
                
                result = session.execute(fallback_query, {'symbol': token_symbol})
                currency_row = result.fetchone()
                
                if not currency_row:
                    logger.warning(f"هیچ رکوردی در جدول currencies برای {token_symbol} یافت نشد")
                    return None
            
            currency_id = currency_row[0]
            logger.debug(f"CurrencyID برای {token_symbol}: {currency_id}")
            
            # حالا با استفاده از CurrencyID به جدول prices مراجعه می‌کنیم
            price_query = text("""
                SELECT price 
                FROM prices 
                WHERE crypto_id = :crypto_id AND currency = 'USD' 
                ORDER BY last_updated DESC 
                LIMIT 1
            """)
            
            result = session.execute(price_query, {'crypto_id': currency_id})
            price_row = result.fetchone()
            
            if price_row:
                price = float(price_row[0])
                logger.info(f"قیمت فعلی {token_symbol} ({currency_id}): ${price:,.2f}")
                return price
            else:
                logger.warning(f"هیچ قیمتی برای {token_symbol} (CurrencyID: {currency_id}) در جدول prices یافت نشد")
                return None
                
        except Exception as e:
            logger.error(f"خطا در دریافت قیمت ارز {token_symbol}: {str(e)}")
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

    def save_transaction(self, blockchain, transaction_id, relevant_addresses, webhook_data, block_number=None, timestamp=None, from_address=None, to_address=None, token_contract=None):
        """
        ذخیره اطلاعات تراکنش در دیتابیس
        
        Args:
            blockchain (str): نام بلاکچین
            transaction_id (str): شناسه تراکنش
            relevant_addresses (list): لیست آدرس‌های مرتبط
            webhook_data (dict): داده‌های وبهوک
            block_number (int, optional): شماره بلاک
            timestamp (int, optional): زمان تراکنش
            from_address (str, optional): آدرس فرستنده
            to_address (str, optional): آدرس گیرنده
            token_contract (str, optional): آدرس قرارداد توکن
            
        Returns:
            bool: نتیجه عملیات ذخیره
        """
        if not transaction_id:
            logger.error("شناسه تراکنش خالی است")
            return False
                
        logger.info(f"ذخیره تراکنش {transaction_id} برای بلاکچین {blockchain}")
        logger.debug(f"اطلاعات وبهوک: {webhook_data}")
        
        # تبدیل BSC به BNB برای همخوانی با دیتابیس
        if blockchain and blockchain.upper() == 'BSC':
            blockchain = 'BNB'
            logger.info(f"تبدیل بلاکچین BSC به BNB برای همخوانی با دیتابیس")
            
        # بررسی می‌کنیم که آیا این تراکنش قبلاً ذخیره شده است
        if self.check_transaction_already_processed(transaction_id, blockchain):
            logger.warning(f"تراکنش {transaction_id} قبلاً ذخیره شده است")
            return False
            
        with self._get_engine().begin() as connection:
            with Session(connection) as session:
                try:
                    # دریافت شناسه بلاکچین
                    blockchain_id = self._get_blockchain_id(session, blockchain)
                    
                    if not blockchain_id:
                        logger.error(f"شناسه بلاکچین برای {blockchain} یافت نشد")
                        return False
                    
                    # استخراج اطلاعات تراکنش از داده‌های وبهوک
                    try:
                        amount = float(webhook_data.get('amount', 0))
                    except (ValueError, TypeError):
                        amount = 0
                        logger.warning(f"خطا در تبدیل مقدار: {webhook_data.get('amount')} به عدد")
                        
                    # استخراج کارمزد از وبهوک یا محاسبه آن
                    fee = self._extract_fee_from_webhook(webhook_data)
                    
                    # اگر کارمزد از وب‌هوک استخراج نشد، سعی می‌کنیم از API تاتوم دریافت کنیم
                    if fee is None:
                        logger.info(f"تلاش برای دریافت کارمزد تراکنش {transaction_id} از API تاتوم")
                        fee = self._get_transaction_fee(transaction_id, blockchain)
                        
                        if fee is not None:
                            logger.info(f"کارمزد تراکنش {transaction_id} از API تاتوم دریافت شد: {fee}")
                        else:
                            logger.warning(f"دریافت کارمزد تراکنش {transaction_id} از API تاتوم ناموفق بود")
                    
                    # زمان تراکنش - استفاده از پارامتر timestamp اگر داده شده باشد
                    transaction_time = None
                    if timestamp:
                        try:
                            if isinstance(timestamp, (int, float)):
                                # تبدیل timestamp به datetime
                                transaction_time = datetime.fromtimestamp(timestamp)
                            else:
                                # تلاش برای تجزیه timestamp به عنوان رشته
                                transaction_time = datetime.strptime(timestamp, "%Y-%m-%dT%H:%M:%S.%fZ")
                        except Exception as e:
                            logger.warning(f"خطا در تبدیل timestamp ارسالی: {e}")
                    
                    # اگر هنوز transaction_time تنظیم نشده، از webhook_data استفاده می‌کنیم
                    if not transaction_time:
                        try:
                            webhook_timestamp = webhook_data.get('timestamp', None)
                            if webhook_timestamp:
                                if isinstance(webhook_timestamp, (int, float)):
                                    transaction_time = datetime.fromtimestamp(webhook_timestamp)
                                else:
                                    transaction_time = datetime.strptime(webhook_timestamp, "%Y-%m-%dT%H:%M:%S.%fZ")
                            else:
                                transaction_time = datetime.now()
                        except Exception as e:
                            logger.warning(f"خطا در تبدیل timestamp از webhook: {e}")
                            transaction_time = datetime.now()
                    
                    # آدرس‌های فرستنده و گیرنده - اولویت با پارامترهای ارسالی
                    sender_address = from_address or webhook_data.get('from', '')
                    receiver_address = to_address or webhook_data.get('to', '')
                    
                    # نماد توکن (برای تراکنش‌های توکن)
                    token_symbol = webhook_data.get('tokenSymbol') or webhook_data.get('token_symbol') or webhook_data.get('asset')
                    
                    # برای توکن‌های اتریوم یا سایر بلاکچین‌ها، اگر آدرس قرارداد شروع با 0x داریم، سیمبل واقعی را از جدول currencies بخوانیم
                    if token_symbol and (token_symbol.startswith('0x') or token_symbol.startswith('0X')) and len(token_symbol) >= 40:
                        logger.info(f"آدرس قرارداد هوشمند به عنوان نماد توکن دریافت شده: {token_symbol}")
                        # آدرس قرارداد را در token_contract ذخیره می‌کنیم
                        token_contract = token_symbol
                        # سپس نماد واقعی توکن را از جدول currencies می‌خوانیم
                        real_token_symbol = self.get_token_symbol_from_contract(session, token_contract, blockchain)
                        if real_token_symbol:
                            token_symbol = real_token_symbol
                            logger.info(f"نماد توکن از جدول currencies: {token_symbol}")
                    
                    # اگر هنوز token_contract تنظیم نشده و در webhook_data داریم، آن را استخراج می‌کنیم
                    if not token_contract:
                        token_contract = webhook_data.get('tokenAddress') or webhook_data.get('contractAddress') or webhook_data.get('asset')
                        
                        # اگر token_contract هم اکنون تنظیم شده و آدرس قرارداد است، نماد واقعی را پیدا می‌کنیم
                        if token_contract and (token_contract.startswith('0x') or token_contract.startswith('0X')) and len(token_contract) >= 40:
                            real_token_symbol = self.get_token_symbol_from_contract(session, token_contract, blockchain)
                            if real_token_symbol and (not token_symbol or token_symbol.startswith('0x')):
                                token_symbol = real_token_symbol
                                logger.info(f"نماد توکن از آدرس قرارداد {token_contract}: {token_symbol}")
                    
                    if not token_symbol and blockchain.upper() in ['BNB']:
                        # برای BNB، اگر نماد توکن مشخص نشده باشد، BNB در نظر می‌گیریم
                        token_symbol = 'BNB'
                    elif not token_symbol:
                        # برای سایر بلاکچین‌ها، نماد اصلی بلاکچین را استفاده می‌کنیم
                        token_symbol = blockchain
                        
                    # اگر نماد توکن BSC است، آن را به BNB تبدیل می‌کنیم
                    if token_symbol and token_symbol.upper() == 'BSC':
                        token_symbol = 'BNB'
                        logger.info(f"تبدیل نماد توکن BSC به BNB برای همخوانی با دیتابیس")
                    
                    # تعیین نوع دارایی (native یا token)
                    asset_type = "native"
                    if token_contract or webhook_data.get('tokenAddress') or webhook_data.get('contractAddress'):
                        asset_type = "token"
                        if not token_contract:
                            token_contract = webhook_data.get('tokenAddress') or webhook_data.get('contractAddress')
                    
                    # تعیین نوع تراکنش و وضعیت آن
                    transaction_type = webhook_data.get('type') or webhook_data.get('transaction_type', 'Transfer')
                    status = webhook_data.get('status', 'Confirmed')
                    
                    # تعیین جهت تراکنش از اولین آدرس مرتبط
                    direction = "unknown"
                    if relevant_addresses and 'direction' in relevant_addresses[0]:
                        direction = relevant_addresses[0]['direction']
                    
                    # شناسه آدرس و کیف پول از اولین آدرس مرتبط
                    address_id = None
                    wallet_id = None
                    if relevant_addresses:
                        address_id = relevant_addresses[0].get('address_id')
                        wallet_id = relevant_addresses[0].get('wallet_id')
                    
                    # شماره بلاک - اولویت با پارامتر ارسالی
                    block_num = block_number or webhook_data.get('blockNumber') or webhook_data.get('blockHeight')
                    
                    # دریافت URL اکسپلورر برای این تراکنش
                    explorer_url = self._get_explorer_url(session, blockchain_id, transaction_id)
                    
                    # دریافت قیمت فعلی توکن
                    price = self._get_current_price(session, token_symbol, blockchain)
                    
                    # محاسبه ارزش کل تراکنش (مقدار * قیمت)
                    transaction_value = None
                    if price is not None and amount is not None:
                        transaction_value = float(amount) * float(price)
                        logger.info(f"ارزش تراکنش: ${transaction_value:,.2f} USD (مقدار: {amount} {token_symbol}, قیمت: ${price:,.2f})")
                    else:
                        logger.warning(f"قیمت یا مقدار برای محاسبه ارزش تراکنش در دسترس نیست. قیمت: {price}, مقدار: {amount}")
                    
                    # تعیین موفقیت تراکنش
                    is_successful = True
                    if webhook_data.get('status') == 'failed' or webhook_data.get('failed') is True:
                        is_successful = False
                    
                    # ذخیره تراکنش در جدول transfers
                    insert_query = text("""
                        INSERT INTO transfers (
                            BlockchainID, AddressID, WalletID, TxHash, BlockNumber, 
                            Timestamp, FromAddress, ToAddress, Amount, Price, 
                            TokenSymbol, TokenContract, AssetType, Fee, Direction, 
                            Status, IsSuccessful, ExplorerUrl, CreatedAt, UpdatedAt
                        ) VALUES (
                            :blockchain_id, :address_id, :wallet_id, :tx_hash, :block_number,
                            :timestamp, :from_address, :to_address, :amount, :price,
                            :token_symbol, :token_contract, :asset_type, :fee, :direction,
                            :status, :is_successful, :explorer_url, NOW(), NOW()
                        )
                    """)
                    
                    # اجرای کوئری درج
                    session.execute(insert_query, {
                        'blockchain_id': blockchain_id,
                        'address_id': address_id,
                        'wallet_id': wallet_id,
                        'tx_hash': transaction_id,
                        'block_number': block_num,
                        'timestamp': transaction_time,
                        'from_address': sender_address,
                        'to_address': receiver_address,
                        'amount': amount,
                        'price': transaction_value,  # ارزش کل تراکنش به دلار (مقدار * قیمت واحد)
                        'token_symbol': token_symbol,
                        'token_contract': token_contract,
                        'asset_type': asset_type,
                        'fee': fee,
                        'direction': direction,
                        'status': status,
                        'is_successful': is_successful,
                        'explorer_url': explorer_url
                    })
                    
                    # ذخیره اطلاعات تراکنش در جدول balance_update_log
                    self._save_transaction_log(session, blockchain_id, transaction_id, wallet_id, direction, amount, token_symbol)
                    
                    # بروزرسانی موجودی کیف پول‌ها
                    for address in relevant_addresses:
                        self.update_wallet_balance(
                            address_info=address, 
                            blockchain=blockchain, 
                            token_contract=token_contract,
                            token_symbol=token_symbol
                        )
                    
                    session.commit()
                    logger.info(f"تراکنش {transaction_id} با موفقیت ذخیره شد")
                    return True
                    
                except Exception as e:
                    logger.error(f"خطا در ذخیره تراکنش {transaction_id}: {str(e)}")
                    logger.exception(e)
                    session.rollback()
                    return False
    
    def _save_transaction_log(self, session, blockchain_id, transaction_id, wallet_id=None, direction=None, amount=None, token_symbol=None):
        """
        ذخیره اطلاعات پردازش تراکنش در جدول لاگ
        """
        try:
            # گرفتن اطلاعات تراکنش از first_address موجود در relevant_addresses اگر در دسترس باشد
            # اصلاح کوئری مطابق با ساختار جدول
            
            # محدود کردن تعداد ارقام اعشار به 18 رقم برای جلوگیری از خطای Data too long
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
            # بررسی وجود تراکنش در لاگ با هر جهتی (بدون در نظر گرفتن direction)
            check_query = text("""
                SELECT COUNT(*) FROM balance_update_log 
                WHERE transaction_id = :transaction_id
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
        به‌روزرسانی موجودی کیف پول
        
        Args:
            address_info (dict): اطلاعات آدرس کیف پول
            blockchain (str): نام بلاکچین
            token_contract (str, optional): آدرس قرارداد توکن
            token_symbol (str, optional): نماد توکن
            
        Returns:
            bool: نتیجه به‌روزرسانی
        """
        if not address_info or not blockchain:
            logger.error("اطلاعات آدرس یا بلاکچین خالی است")
            return False
            
        # تبدیل BSC به BNB برای همخوانی با دیتابیس
        if blockchain and blockchain.upper() == 'BSC':
            blockchain = 'BNB'
            logger.info(f"تبدیل بلاکچین BSC به BNB برای همخوانی با دیتابیس")
            
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
            
            # حذف تبدیل BSC به BNB - این کار اکنون توسط پردازشگر اختصاصی انجام می‌شود
            
            # تعیین نماد توکن
            currency_symbol = token_symbol or blockchain
            
            logger.info(f"به‌روزرسانی موجودی {currency_symbol} برای کیف پول {wallet_id} (آدرس {public_address})")
            
            # دریافت موجودی از بلاکچین
            balance = self.blockchain_utils.get_address_balance(public_address, blockchain, token_contract)
            
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
                
                # بررسی وجود رکورد موجودی در جدول userholding
                check_query = text("""
                    SELECT HoldingID, Balance FROM userholding
                    WHERE UserID = :user_id
                    AND (Blockchain = :blockchain OR Blockchain = 'BNB' OR Blockchain = 'BSC')
                    AND (
                        (:token_symbol IS NULL AND Symbol = :blockchain) OR
                        (Symbol = :token_symbol) OR 
                        (Symbol = :token_contract)
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
                    current_balance = result[1]
                    
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
                    # ایجاد رکورد موجودی جدید
                    logger.info(f"ایجاد رکورد موجودی جدید برای {currency_symbol} با مقدار {balance}")
                    
                    # ابتدا بلاکچین را پیدا کنیم
                    blockchain_id = self._get_blockchain_id(session, blockchain)
                    
                    if not blockchain_id:
                        logger.error(f"بلاکچین {blockchain} در پایگاه داده یافت نشد")
                        return False
                    
                    # دریافت شناسه ارز
                    currency_query = text("""
                        SELECT CurrencyID FROM currencies 
                        WHERE Symbol = :symbol 
                        AND BlockchainID = :blockchain_id
                    """)
                    currency_result = session.execute(currency_query, {
                        'symbol': currency_symbol, 
                        'blockchain_id': blockchain_id
                    }).fetchone()
                    
                    if not currency_result:
                        logger.error(f"ارز {currency_symbol} برای بلاکچین {blockchain} یافت نشد")
                        return False
                    
                    currency_id = currency_result[0]
                    
                    # بررسی وجود رکورد مشابه برای جلوگیری از خطای Duplicate entry
                    duplicate_check_query = text("""
                        SELECT COUNT(*) FROM userholding
                        WHERE UserID = :user_id AND CurrencyID = :currency_id
                    """)
                    duplicate_count = session.execute(duplicate_check_query, {
                        'user_id': user_id,
                        'currency_id': currency_id
                    }).scalar()
                    
                    if duplicate_count > 0:
                        # اگر رکورد وجود دارد، آن را به‌روزرسانی می‌کنیم
                        logger.info(f"رکورد موجودی برای کاربر {user_id} و ارز {currency_id} قبلاً وجود دارد، به‌روزرسانی می‌شود")
                        update_existing_query = text("""
                            UPDATE userholding 
                            SET Balance = :balance, UpdatedAt = NOW()
                            WHERE UserID = :user_id AND CurrencyID = :currency_id
                        """)
                        
                        # محدود کردن تعداد ارقام اعشار به 18 رقم
                        from decimal import Decimal, getcontext, ROUND_DOWN
                        getcontext().prec = 38  # کل ارقام معنی‌دار
                        balance_decimal = Decimal(str(balance))
                        # محدود کردن به 18 رقم اعشار
                        balance_formatted = balance_decimal.quantize(Decimal('0.000000000000000001'), rounding=ROUND_DOWN)
                        
                        session.execute(update_existing_query, {
                            'user_id': user_id,
                            'currency_id': currency_id,
                            'balance': balance_formatted
                        })
                    else:
                        # افزودن رکورد جدید
                        # محدود کردن تعداد ارقام اعشار به 18 رقم
                        from decimal import Decimal, getcontext, ROUND_DOWN
                        getcontext().prec = 38  # کل ارقام معنی‌دار
                        balance_decimal = Decimal(str(balance))
                        # محدود کردن به 18 رقم اعشار
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
            
        except Exception as e:
            logger.error(f"خطا در به‌روزرسانی موجودی کیف پول: {str(e)}")
            return False
    
    def get_token_symbol_from_contract(self, session, contract_address, blockchain):
        """
        استخراج نام توکن از آدرس قرارداد هوشمند
        
        Args:
            session: نشست دیتابیس
            contract_address (str): آدرس قرارداد هوشمند
            blockchain (str): نام بلاکچین
            
        Returns:
            str: نماد توکن
        """
        if not contract_address:
            return None
            
        logger.info(f"دریافت نماد توکن برای قرارداد {contract_address} در بلاکچین {blockchain}")
        
        try:
            # ابتدا تبدیل شکل آدرس به lowercase
            contract_address = contract_address.lower()
            
            # حذف تبدیل BSC به BNB در این قسمت - این کار اکنون توسط پردازشگر اختصاصی انجام می‌شود
            
            # ساخت کوئری جستجوی توکن
            query = text("""
                SELECT c.Symbol
                FROM currencies c
                JOIN blockchains b ON c.BlockchainID = b.BlockchainID
                WHERE LOWER(c.SmartContractAddress) = :contract_address
                AND (
                    b.Symbol = :blockchain
                    OR b.BlockchainName = :blockchain
                    OR ((:blockchain = 'BNB' OR :blockchain = 'BSC')
                    AND (b.BlockchainName LIKE '%Binance%' OR b.BlockchainName LIKE '%BSC%' OR b.Symbol = 'BNB')))
                LIMIT 1
            """)
            
            result = session.execute(query, {
                'contract_address': contract_address,
                'blockchain': blockchain
            }).fetchone()
            
            if result:
                symbol = result[0]
                logger.info(f"نماد توکن {symbol} برای قرارداد {contract_address} یافت شد")
                return symbol
            
            # اگر توکن پیدا نشد، بخشی از آدرس قرارداد را به عنوان نماد استفاده می‌کنیم
            symbol = "TKN_" + contract_address[-6:]
            logger.warning(f"نماد توکن برای قرارداد {contract_address} یافت نشد، از {symbol} به عنوان نماد استفاده می‌شود")
            return symbol
            
        except Exception as e:
            logger.error(f"خطا در دریافت نماد توکن: {str(e)}")
            # در صورت خطا، به صورت پیش‌فرض آخرین کاراکترهای آدرس قرارداد را استفاده می‌کنیم
            symbol = "TKN_" + contract_address[-6:]
            return symbol
    
    def update_user_holding_balance(self, wallet_id, blockchain, token_symbol, direction, amount, tx_id, contract_address=None):
        """
        Update the balance of a user's holdings based on a transaction.
        
        Args:
            wallet_id (str): The wallet ID
            blockchain (str): The blockchain name
            token_symbol (str): The token symbol
            direction (str): The transaction direction (inbound/outbound)
            amount: The transaction amount
            tx_id: The transaction ID
            contract_address: The contract address for token transactions
            
        Returns:
            bool: Success or failure
        """
        from decimal import Decimal, getcontext, ROUND_DOWN
        import datetime
        
        # محدود کردن تعداد ارقام اعشار به 18 رقم
        getcontext().prec = 38  # کل ارقام معنی‌دار
        amount_decimal = Decimal(str(amount))
        # محدود کردن به 18 رقم اعشار
        amount_formatted = amount_decimal.quantize(Decimal('0.000000000000000001'), rounding=ROUND_DOWN)
        
        # تبدیل BSC به BNB برای همخوانی با دیتابیس
        if blockchain and blockchain.upper() == 'BSC':
            blockchain = 'BNB'
            logger.info(f"تبدیل بلاکچین BSC به BNB برای همخوانی با دیتابیس")
            
        # اگر نماد توکن BSC است، آن را به BNB تبدیل می‌کنیم
        if token_symbol and token_symbol.upper() == 'BSC':
            token_symbol = 'BNB'
            logger.info(f"تبدیل نماد توکن BSC به BNB برای همخوانی با دیتابیس")
        
        logger.info(f"Starting update_user_holding_balance for tx_id: {tx_id}, direction: {direction}, amount: {amount_formatted}")
        
        engine = self._get_engine()
        try:
            with Session(engine) as session:
                # Get user ID from wallet ID
                wallet_query = text("""
                    SELECT UserID FROM wallets WHERE WalletID = :wallet_id
                """)
                result = session.execute(wallet_query, {'wallet_id': wallet_id}).fetchone()
                
                if not result:
                    logger.error(f"Wallet {wallet_id} not found in database")
                    return False
                    
                user_id = result[0]
                logger.info(f"Found user ID {user_id} for wallet {wallet_id}")
                
                # If this is a token with contract address, get the proper symbol from currencies table
                if contract_address and (token_symbol.startswith('0x') or token_symbol.startswith('0X')) and len(token_symbol) >= 40:
                    token_symbol = self.get_token_symbol_from_contract(session, contract_address, blockchain)
                
                # Check if the currency exists
                # For tokens, first check by contract address
                if contract_address:
                    currency_query = text("""
                        SELECT c.CurrencyID 
                        FROM currencies c
                        WHERE LOWER(c.SmartContractAddress) = LOWER(:contract_address)
                        LIMIT 1
                    """)
                    result = session.execute(currency_query, {
                        'contract_address': contract_address
                    }).fetchone()
                    
                    if result:
                        currency_id = result[0]
                        logger.info(f"Found currency by contract address: {contract_address}")
                    else:
                        logger.info(f"No currency found by contract address: {contract_address}, trying symbol")

                # If no result by contract address or it's a native token, try by symbol and blockchain
                if not result or not contract_address:
                    currency_query = text("""
                        SELECT c.CurrencyID 
                        FROM currencies c
                        JOIN blockchains b ON c.BlockchainID = b.BlockchainID
                        WHERE UPPER(c.Symbol) = UPPER(:symbol) AND (b.BlockchainName = :blockchain 
                            OR b.Symbol = :blockchain_symbol
                            OR ((:blockchain = 'BNB' OR :blockchain = 'BSC') 
                                AND (b.BlockchainName LIKE '%Binance%' OR b.BlockchainName LIKE '%BSC%' OR b.Symbol = 'BNB')))
                    """)
                    result = session.execute(currency_query, {
                        'symbol': token_symbol,
                        'blockchain': blockchain,
                        'blockchain_symbol': blockchain.upper()
                    }).fetchone()
                
                currency_id = None
                if result:
                    currency_id = result[0]
                else:
                    # Instead of creating a new currency, log an error and return
                    logger.error(f"Currency {token_symbol} on {blockchain} not found in the database. Please add it manually.")
                    return False
                
                # Check if user holding exists
                holding_query = text("""
                    SELECT HoldingID, Balance FROM userholding 
                    WHERE UserID = :user_id AND Symbol = :symbol AND 
                    (Blockchain = :blockchain OR 
                     (:blockchain IN ('BNB', 'BSC') AND Blockchain IN ('BNB', 'BSC')))
                """)
                
                holding_result = session.execute(holding_query, {
                    'user_id': user_id,
                    'symbol': token_symbol,
                    'blockchain': blockchain
                }).fetchone()
                
                # Record this transaction in balance_update_log BEFORE updating balance
                # This prevents double counting if the process is interrupted
                
                # بررسی وجود رکورد قبلی در balance_update_log برای جلوگیری از Duplicate entry
                check_log_query = text("""
                    SELECT COUNT(*) FROM balance_update_log 
                    WHERE wallet_id = :wallet_id AND tx_id = :tx_id AND direction = :direction
                """)
                
                log_exists = session.execute(check_log_query, {
                    'wallet_id': wallet_id,
                    'tx_id': tx_id,
                    'direction': direction
                }).scalar() > 0
                
                if not log_exists:
                    log_query = text("""
                        INSERT INTO balance_update_log 
                        (wallet_id, tx_id, direction, amount, token_symbol, blockchain, created_at) 
                        VALUES 
                        (:wallet_id, :tx_id, :direction, :amount, :token_symbol, :blockchain, NOW())
                    """)
                    
                    try:
                        session.execute(log_query, {
                            'wallet_id': wallet_id,
                            'tx_id': tx_id,
                            'direction': direction,
                            'amount': str(amount_formatted),
                            'token_symbol': token_symbol,
                            'blockchain': blockchain
                        })
                        session.commit()
                        logger.debug(f"Transaction {tx_id} logged to balance_update_log")
                    except Exception as e:
                        logger.warning(f"Error logging transaction to balance_update_log: {str(e)}")
                        session.rollback()
                else:
                    logger.info(f"تراکنش {tx_id} قبلاً در balance_update_log ثبت شده است")
                
                # Update user holding
                new_balance = Decimal('0')
                
                if holding_result:
                    # Holding exists, update it
                    holding_id = holding_result[0]
                    current_balance = holding_result[1] or Decimal('0')
                    
                    # Convert to Decimal for precise arithmetic
                    current_balance = Decimal(str(current_balance))
                    
                    # Calculate new balance based on direction
                    if direction == 'inbound':
                        new_balance = current_balance + amount_formatted
                    elif direction == 'outbound':
                        new_balance = current_balance - amount_formatted
                        # Prevent negative balance
                        if new_balance < 0:
                            logger.warning(f"Negative balance detected for {token_symbol}. Setting to 0.")
                            new_balance = Decimal('0')
                    
                    # Update the holding
                    update_query = text("""
                        UPDATE userholding
                        SET Balance = :balance, LastUpdated = NOW(), UpdatedAt = NOW(),
                        RawData = JSON_OBJECT(
                            'previous_balance', :previous_balance,
                            'new_balance', :new_balance,
                            'last_tx_id', :tx_id,
                            'last_tx_direction', :direction,
                            'last_tx_amount', :amount
                        )
                        WHERE HoldingID = :holding_id
                    """)
                    
                    try:
                        session.execute(update_query, {
                            'balance': str(new_balance),
                            'previous_balance': str(current_balance),
                            'new_balance': str(new_balance),
                            'tx_id': tx_id,
                            'direction': direction,
                            'amount': str(amount_formatted),
                            'holding_id': holding_id
                        })
                        session.commit()
                        logger.info(f"Updated user holding for {user_id}, {token_symbol} on {blockchain}. Balance changed from {current_balance} to {new_balance} ({direction})")
                    except Exception as e:
                        logger.error(f"Error updating user holding balance: {str(e)}")
                        session.rollback()
                        return False
                else:
                    # Holding doesn't exist, create a new one
                    
                    # If first transaction is outbound, set initial balance to 0
                    if direction == 'outbound':
                        logger.warning(f"First transaction for {token_symbol} is outbound. Setting balance to 0.")
                        new_balance = Decimal('0')
                    else:
                        new_balance = amount_formatted
                        
                    # بررسی وجود رکورد در جدول userholding قبل از درج رکورد جدید
                    check_holding_query = text("""
                        SELECT COUNT(*) FROM userholding 
                        WHERE UserID = :user_id AND CurrencyID = :currency_id
                    """)
                    
                    holding_exists = session.execute(check_holding_query, {
                        'user_id': user_id,
                        'currency_id': currency_id
                    }).scalar() > 0
                    
                    if holding_exists:
                        # اگر رکورد موجودی قبلا وجود دارد، آن را بروزرسانی می‌کنیم
                        update_existing_query = text("""
                            UPDATE userholding
                            SET Balance = :balance, LastUpdated = NOW(), UpdatedAt = NOW(),
                            RawData = JSON_OBJECT(
                                'new_balance', :new_balance,
                                'last_tx_id', :tx_id,
                                'last_tx_direction', :direction,
                                'last_tx_amount', :amount
                            )
                            WHERE UserID = :user_id AND CurrencyID = :currency_id
                        """)
                        
                        try:
                            session.execute(update_existing_query, {
                                'balance': str(new_balance),
                                'new_balance': str(new_balance),
                                'tx_id': tx_id,
                                'direction': direction,
                                'amount': str(amount_formatted),
                                'user_id': user_id,
                                'currency_id': currency_id
                            })
                            session.commit()
                            logger.info(f"Updated existing user holding for {user_id}, {token_symbol} on {blockchain} with balance {new_balance}")
                        except Exception as e:
                            logger.error(f"Error updating existing user holding: {str(e)}")
                            session.rollback()
                            return False
                    else:
                        # Create a new holding
                        insert_query = text("""
                            INSERT INTO userholding
                            (UserID, CurrencyID, Balance, Symbol, Blockchain, IsToken, LastUpdated, RawData, CreatedAt, UpdatedAt)
                            VALUES
                            (:user_id, :currency_id, :balance, :symbol, :blockchain, :is_token, NOW(), JSON_OBJECT('original_balance', :balance), NOW(), NOW())
                        """)
                        
                        # Determine if token
                        is_token = 0
                        if token_symbol != blockchain:
                            is_token = 1
                            
                        try:
                            session.execute(insert_query, {
                                'user_id': user_id,
                                'currency_id': currency_id,
                                'balance': str(new_balance),
                                'symbol': token_symbol,
                                'blockchain': blockchain,
                                'is_token': is_token
                            })
                            session.commit()
                            logger.info(f"Created new user holding for {user_id}, {token_symbol} on {blockchain} with initial balance {new_balance}")
                        except Exception as e:
                            logger.error(f"Error creating new user holding: {str(e)}")
                            session.rollback()
                            return False
                
                # Commit the changes
                session.commit()
                logger.info(f"Successfully completed update_user_holding_balance for tx_id: {tx_id}")
                return True
                
        except Exception as e:
            logger.error(f"Error updating user holding balance: {str(e)}", exc_info=True)
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