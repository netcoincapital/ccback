from CC.webhook.transaction_processor import TransactionProcessor
from CC.utils.logging_config import get_logger
from CC.webhook.chains.trx.utils import parse_tron_contract_data
import requests
from decimal import Decimal
from sqlalchemy import text
from sqlalchemy.orm import Session
import os
import json
import time
import base58
import datetime
import binascii

logger = get_logger(__name__)

class TronProcessor(TransactionProcessor):
    """پردازشگر وب‌هوک‌های مخصوص ترون"""
    
    def __init__(self):
        super().__init__()
        logger.info("پردازشگر ترون راه‌اندازی شد")
    
    def process_webhook(self, webhook_data):
        """
        Process tronscan webhook
        
        Args:
            webhook_data (dict): Webhook data
        """
        transaction_data = webhook_data
        
        # Extract transaction fields
        transaction_hash = transaction_data['hash']
        sender = transaction_data.get('from')
        recipient = transaction_data.get('to')
        
        # Default to TRX as token symbol with 6 decimals
        token_symbol = 'TRX'
        token_decimals = 6
        token_contract = None
        
        # Get transaction amount and token info
        try:
            if 'tokenInfo' in transaction_data and transaction_data['tokenInfo'].get('tokenId') is not None:
                # This is a TRC10 token
                token_symbol = transaction_data['tokenInfo'].get('symbol')
                token_decimals = transaction_data['tokenInfo'].get('decimal', 6)
                token_contract = transaction_data['tokenInfo'].get('tokenId')
                value = Decimal(transaction_data.get('amount', 0))
                
            elif transaction_data.get('trigger_info', {}).get('contract_address') and \
                 transaction_data.get('trigger_info', {}).get('parameter', {}).get('_value') is not None:
                # This is a TRC20 token transfer
                token_contract = transaction_data['trigger_info']['contract_address']
                
                # Special handling for NCC token
                if token_contract == 'T9yYp7JUxypLk7GFhsLRj5jN6ZrNDcH2Cf' or token_contract == 'TCDgp5bwtixaShPifUm7HpZ71C1pe6zif1':
                    token_symbol = 'NCC'
                    token_decimals = 6
                    logger.info(f"Recognized NCC token from contract address {token_contract}")
                else:
                    # First try to get token symbol from contract address
                    token_symbol = self._get_token_symbol_from_contract(token_contract)
                    
                    # If still not found, get full token info
                    if token_symbol == 'UNKNOWN':
                        token_symbol, token_decimals = self._get_token_info_from_contract(token_contract)
                    else:
                        # Get just the decimals if we already have the symbol
                        _, token_decimals = self._get_token_info_from_contract(token_contract)
                
                value = Decimal(transaction_data['trigger_info']['parameter']['_value'])
                
            else:
                # Native TRX transfer
                token_symbol = 'TRX'
                token_decimals = 6
                value = Decimal(transaction_data.get('amount', 0))
                
        except Exception as e:
            logger.error(f"Error processing transaction {transaction_hash}: {str(e)}")
            raise
        
        # Normalize value based on decimals
        normalized_value = value / Decimal(10 ** token_decimals)
        
        # Make sure the token exists in our database
        self._ensure_token_exists_in_db(token_symbol, token_contract, token_decimals)
        
        # Get timestamp
        timestamp = transaction_data.get('timestamp', int(time.time() * 1000))
        if isinstance(timestamp, int) and timestamp > 1000000000000:  # if timestamp is in milliseconds
            timestamp = timestamp // 1000
            
        dt = datetime.datetime.fromtimestamp(timestamp)
        
        # Calculate transaction fee
        transaction_fee = self._get_tron_transaction_fee(transaction_hash)
        
        # Get token price
        token_price = self._get_tron_price() if token_symbol.upper() == 'TRX' else 0
        
        # Save transaction
        self.db_operations.save_transaction({
            'chain': 'TRX',
            'transaction_hash': transaction_hash,
            'sender': sender,
            'recipient': recipient,
            'token_symbol': token_symbol,
            'token_contract': token_contract,
            'amount': float(normalized_value),
            'timestamp': dt,
            'block_number': transaction_data.get('block', 0),
            'transaction_fee': transaction_fee,
            'token_price': token_price,
            'status': transaction_data.get('result', 'CONFIRMED'),
            'raw_data': json.dumps(transaction_data)
        })
        
        logger.info(f"Processed TRX transaction: {transaction_hash}")
    
    def _ensure_token_exists_in_db(self, token_symbol, token_contract, token_decimals):
        """
        Ensure that the token exists in the database
        
        Args:
            token_symbol (str): Token symbol
            token_contract (str): Token contract address
            token_decimals (int): Token decimal places
        """
        try:
            engine = self.db_operations._get_engine()
            with Session(engine) as db_session:
                # Check if token exists
                query = text("""
                    SELECT COUNT(*) FROM currencies 
                    WHERE Symbol = :symbol
                """)
                
                count = db_session.execute(query, {'symbol': token_symbol}).scalar()
                
                if count == 0:
                    logger.warning(f"Token {token_symbol} not found in database. Adding it...")
                    
                    # Get blockchain ID for TRX
                    blockchain_query = text("""
                        SELECT BlockchainID FROM blockchains 
                        WHERE Symbol = 'TRX' OR Symbol = 'TRON'
                        LIMIT 1
                    """)
                    
                    blockchain_id = db_session.execute(blockchain_query).scalar()
                    
                    if not blockchain_id:
                        logger.warning("TRX blockchain ID not found, using default value 2")
                        blockchain_id = 2  # Default ID for TRX based on data sample
                    
                    # Insert new token record
                    insert_query = text("""
                        INSERT INTO currencies (
                            CurrencyName, Symbol, BlockchainID, DecimalPlaces, IsToken, 
                            SmartContractAddress, CreatedAt, UpdatedAt
                        ) VALUES (
                            :name, :symbol, :blockchain_id, :decimals, 1,
                            :contract, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                        )
                    """)
                    
                    db_session.execute(insert_query, {
                        'name': token_symbol,
                        'symbol': token_symbol,
                        'blockchain_id': blockchain_id,
                        'decimals': token_decimals,
                        'contract': token_contract
                    })
                    
                    db_session.commit()
                    logger.info(f"Added token {token_symbol} to database")
                else:
                    # Update token info if necessary
                    update_query = text("""
                        UPDATE currencies 
                        SET SmartContractAddress = COALESCE(SmartContractAddress, :contract),
                            DecimalPlaces = COALESCE(DecimalPlaces, :decimals),
                            UpdatedAt = CURRENT_TIMESTAMP
                        WHERE Symbol = :symbol AND (SmartContractAddress IS NULL OR DecimalPlaces IS NULL)
                    """)
                    
                    db_session.execute(update_query, {
                        'symbol': token_symbol,
                        'contract': token_contract,
                        'decimals': token_decimals
                    })
                    
                    db_session.commit()
                    
        except Exception as e:
            logger.error(f"Error ensuring token {token_symbol} exists in database: {str(e)}")
            # Don't raise exception here to allow transaction processing to continue
    
    def _get_tron_transaction_fee(self, tx_hash):
        """
        Get transaction fee for Tron transaction using official FullNode API.
        
        Args:
            tx_hash (str): Transaction hash
            
        Returns:
            float: Transaction fee in TRX
        """
        TRONGRID_BASE = "https://api.trongrid.io"
        try:
            # 1. Primary: POST /wallet/gettransactioninfobyid — official FullNode API
            url = f"{TRONGRID_BASE}/wallet/gettransactioninfobyid"
            headers = {"Content-Type": "application/json"}
            api_key = os.getenv("TRONGRID_API_KEY", "")
            if api_key:
                headers["TRON-PRO-API-KEY"] = api_key
            
            payload = {"value": tx_hash}
            response = requests.post(url, json=payload, headers=headers, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                # fee is in SUN (1 TRX = 1,000,000 SUN)
                fee_sun = int(data.get('fee', 0))
                fee_trx = fee_sun / 1_000_000.0
                if fee_trx > 0:
                    logger.info(f"Retrieved fee from FullNode API for {tx_hash}: {fee_trx} TRX")
                    return fee_trx
            
            # 2. Fallback: Try TronScan API
            tronscan_url = f"https://apilist.tronscanapi.com/api/transaction-info?hash={tx_hash}"
            response = requests.get(tronscan_url, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                fee_sun = int(data.get('cost', {}).get('fee', 0))
                fee_trx = fee_sun / 1_000_000.0
                if fee_trx > 0:
                    logger.info(f"Retrieved fee from TronScan API for {tx_hash}: {fee_trx} TRX")
                    return fee_trx
            
            # If both APIs fail, return a default fee
            logger.warning(f"Could not retrieve fee for transaction {tx_hash}, using default")
            return 0.01  # Default fee: 0.01 TRX
            
        except Exception as e:
            logger.error(f"Error retrieving fee for transaction {tx_hash}: {str(e)}")
            return 0.01  # Default fee: 0.01 TRX
    
    def _get_tron_price(self):
        """
        Get current TRX price in USD
        
        Returns:
            float: Current TRX price in USD
        """
        try:
            # First try to get price from CoinGecko API
            coingecko_url = "https://api.coingecko.com/api/v3/simple/price?ids=tron&vs_currencies=usd"
            response = requests.get(coingecko_url, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if 'tron' in data and 'usd' in data['tron']:
                    price = data['tron']['usd']
                    logger.info(f"Retrieved TRX price from CoinGecko: ${price}")
                    return price
            
            # Fallback to Binance API
            binance_url = "https://api.binance.com/api/v3/ticker/price?symbol=TRXUSDT"
            response = requests.get(binance_url, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                price = float(data.get('price', 0))
                logger.info(f"Retrieved TRX price from Binance: ${price}")
                return price
                
            # Second fallback to CoinMarketCap API
            cmc_url = "https://pro-api.coinmarketcap.com/v1/cryptocurrency/quotes/latest"
            headers = {
                'X-CMC_PRO_API_KEY': os.getenv("CMC_API_KEY", ""),
            }
            params = {
                'symbol': 'TRX',
                'convert': 'USD'
            }
            
            # Only try CMC if API key exists
            if headers['X-CMC_PRO_API_KEY']:
                response = requests.get(cmc_url, headers=headers, params=params, timeout=10)
                if response.status_code == 200:
                    data = response.json()
                    price = data['data']['TRX']['quote']['USD']['price']
                    logger.info(f"Retrieved TRX price from CoinMarketCap: ${price}")
                    return price
            
            # If all APIs fail, return a cached price or default
            logger.warning("Could not retrieve TRX price from any API, using default value")
            return 0.1  # Default placeholder price
            
        except Exception as e:
            logger.error(f"Error retrieving TRX price: {str(e)}")
            return 0.1  # Default placeholder price
    
    def update_transaction(self, blockchain, tx_hash):
        """
        به‌روزرسانی تراکنش ترون
        
        Args:
            blockchain (str): نام بلاکچین
            tx_hash (str): هش تراکنش
            
        Returns:
            dict: نتیجه به‌روزرسانی
        """
        logger.info(f"به‌روزرسانی تراکنش ترون: {tx_hash}")
        
        # استاندارد کردن نام بلاکچین
        if blockchain.upper() in ['TRON', 'TRX']:
            blockchain = 'TRX'
            
        # فراخوانی متد اصلی
        return super().update_transaction(blockchain, tx_hash)
    
    def _get_token_info_from_contract(self, contract_address):
        """
        Get token info from contract address
        
        Args:
            contract_address (str): Contract address
            
        Returns:
            tuple: (token_symbol, token_decimals)
        """
        logger.info(f"Getting token info for TRX contract: {contract_address}")
        
        # Dictionary of known tokens for instant lookup
        known_tokens = {
            'T9yYp7JUxypLk7GFhsLRj5jN6ZrNDcH2Cf': ('NCC', 6),
            'TCDgp5bwtixaShPifUm7HpZ71C1pe6zif1': ('NCC', 6),
            'TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t': ('USDT', 6),
            'TEkxiTehnzSmSe2XqrBj4w32RUN966rdz8': ('USDC', 6),
            # Add more known tokens as needed
        }
        
        # Check if token is in our known tokens dictionary
        if contract_address in known_tokens:
            logger.info(f"Using predefined token info for {contract_address}: {known_tokens[contract_address]}")
            return known_tokens[contract_address]
        
        # Check if we have this token info in database
        try:
            with Session(self.db_operations._get_engine()) as db_session:
                # Try exact match first
                token_query = text("""
                    SELECT Symbol, DecimalPlaces FROM currencies 
                    WHERE LOWER(SmartContractAddress) = LOWER(:contract_address)
                    LIMIT 1
                """)
                
                result = db_session.execute(token_query, {'contract_address': contract_address}).fetchone()
                
                if result:
                    logger.info(f"Found token in database: {result[0]} with {result[1]} decimals")
                    return result[0], result[1] or 6
                
                # If not found, try fuzzy search
                fuzzy_query = text("""
                    SELECT Symbol, DecimalPlaces FROM currencies 
                    WHERE SmartContractAddress LIKE :contract_pattern
                    LIMIT 1
                """)
                
                contract_pattern = f"%{contract_address}%"
                fuzzy_result = db_session.execute(fuzzy_query, {'contract_pattern': contract_pattern}).fetchone()
                
                if fuzzy_result:
                    logger.info(f"Found token with fuzzy match: {fuzzy_result[0]} with {fuzzy_result[1]} decimals")
                    return fuzzy_result[0], fuzzy_result[1] or 6
                    
        except Exception as e:
            logger.error(f"Error querying token from database: {str(e)}")
        
        # API sources to try in order
        api_sources = [
            # Tronscan API
            {
                "name": "Tronscan",
                "url": f"https://apilist.tronscan.org/api/token_trc20?contract={contract_address}",
                "parser": lambda data: (
                    data.get('trc20_tokens', [])[0].get('symbol', ''),
                    int(data.get('trc20_tokens', [])[0].get('decimals', 6))
                ) if data.get('trc20_tokens') and len(data['trc20_tokens']) > 0 else None
            },
            # TronGrid API
            {
                "name": "TronGrid",
                "url": f"https://api.trongrid.io/v1/contracts/{contract_address}",
                "parser": lambda data: (
                    data.get('data', [])[0].get('symbol', data.get('data', [])[0].get('name', 'UNKNOWN')),
                    int(data.get('data', [])[0].get('decimals', 6))
                ) if data.get('data') and len(data['data']) > 0 else None
            },
            # TronStation API
            {
                "name": "TronStation",
                "url": f"https://api.tronstation.io/v1/tokens/{contract_address}",
                "parser": lambda data: (
                    data.get('symbol', ''),
                    int(data.get('decimals', 6))
                ) if data and 'symbol' in data else None
            }
        ]
        
        # Try each API source
        for api in api_sources:
            try:
                logger.info(f"Attempting to get token info from {api['name']} API")
                response = requests.get(api["url"], timeout=10)
                
                if response.status_code == 200:
                    data = response.json()
                    result = api["parser"](data)
                    
                    if result and result[0]:
                        token_symbol, token_decimals = result
                        logger.info(f"Retrieved token info from {api['name']}: Symbol={token_symbol}, Decimals={token_decimals}")
                        
                        # Store in database for future lookups if we have a valid symbol
                        if token_symbol != 'UNKNOWN' and self._ensure_token_exists_in_db:
                            try:
                                self._ensure_token_exists_in_db(token_symbol, contract_address, token_decimals)
                                logger.info(f"Saved {token_symbol} token info to database")
                            except Exception as e:
                                logger.warning(f"Failed to save token info to database: {str(e)}")
                        
                        return token_symbol, token_decimals
            
            except Exception as e:
                logger.warning(f"Error getting token info from {api['name']} API: {str(e)}")
                continue
        
        # Final fallback - Force recognition of special tokens
        if contract_address.lower() in [addr.lower() for addr in ['T9yYp7JUxypLk7GFhsLRj5jN6ZrNDcH2Cf', 'TCDgp5bwtixaShPifUm7HpZ71C1pe6zif1']]:
            logger.info(f"Forced recognition of NCC token for contract {contract_address}")
            return 'NCC', 6
        
        # If all methods fail, return unknown symbol with default decimals
        logger.warning(f"Could not determine token info for contract {contract_address}, using UNKNOWN")
        return 'UNKNOWN', 6

    def _get_token_symbol_from_contract(self, contract_address):
        """
        Get token symbol for a given contract address
        
        Args:
            contract_address (str): Contract address
            
        Returns:
            str: Token symbol
        """
        # First, try to get from known tokens dictionary
        known_tokens = {
            'T9yYp7JUxypLk7GFhsLRj5jN6ZrNDcH2Cf': 'NCC',
            'TCDgp5bwtixaShPifUm7HpZ71C1pe6zif1': 'NCC',
            'TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t': 'USDT',
            'TEkxiTehnzSmSe2XqrBj4w32RUN966rdz8': 'USDC',
        }
        
        if contract_address in known_tokens:
            return known_tokens[contract_address]
            
        # Try to get from database
        try:
            with Session(self.db_operations._get_engine()) as db_session:
                # Look up by exact SmartContractAddress match
                query = text("""
                    SELECT Symbol FROM currencies 
                    WHERE LOWER(SmartContractAddress) = LOWER(:contract_address)
                    LIMIT 1
                """)
                
                result = db_session.execute(query, {'contract_address': contract_address}).fetchone()
                
                if result:
                    return result[0]
                    
                # Try fuzzy match
                fuzzy_query = text("""
                    SELECT Symbol FROM currencies 
                    WHERE SmartContractAddress LIKE :contract_pattern
                    LIMIT 1
                """)
                
                contract_pattern = f"%{contract_address}%"
                fuzzy_result = db_session.execute(fuzzy_query, {'contract_pattern': contract_pattern}).fetchone()
                
                if fuzzy_result:
                    return fuzzy_result[0]
                    
                # If not found in DB, try API calls
                token_info = self._get_token_info_from_contract(contract_address)
                if token_info and token_info[0] != 'UNKNOWN':
                    return token_info[0]
                    
                # Return UNKNOWN if all else fails
                return 'UNKNOWN'
                
        except Exception as e:
            logger.error(f"Error retrieving token symbol for contract {contract_address}: {str(e)}")
            return 'UNKNOWN' 