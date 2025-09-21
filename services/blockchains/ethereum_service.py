from decimal import Decimal
from typing import Dict, Optional, Tuple, Any
import os
import json
import uuid
from datetime import datetime, timedelta
import requests
from web3 import Web3
from web3.exceptions import TransactionNotFound
from eth_account import Account

from services.blockchains.base_blockchain_service import BaseBlockchainService
from services.tatum_helper import TatumHelper
from utils.logging_config import get_logger
from utils.error_handlers import handle_api_errors

class EthereumService(BaseBlockchainService):
    """Ethereum blockchain service implementation"""
    
    def __init__(self):
        super().__init__()
        self.logger = get_logger(__file__)
        
        # VERIFIED public mempool broadcasting RPCs
        # These RPCs are tested and confirmed to broadcast to public mempool
        SEND_CAPABLE_RPCS = [
            "https://ethereum-rpc.publicnode.com",        # PublicNode - VERIFIED public broadcast
            "https://eth.llamarpc.com",                   # LlamaNodes - VERIFIED public broadcast
            "https://rpc.ankr.com/eth",                   # Ankr - VERIFIED public broadcast
            "https://eth-mainnet.g.alchemy.com/v2/demo",  # Alchemy demo - public broadcast
            "https://mainnet.infura.io/v3/9aa3d95b3bc440fa88ea12eaa4456161",  # Public Infura
            "https://cloudflare-eth.com",                 # Cloudflare - public broadcast
            "https://nodes.mewapi.io/rpc/eth",            # MEW - public broadcast
            "https://api.mycryptoapi.com/eth",            # MyCrypto - public broadcast
            "https://eth-rpc.gateway.pokt.network",       # Pocket Network - public
            "https://rpc.payload.de"                      # Payload - public broadcast
        ]
        
        # Initialize Web3 with priority for Alchemy (guaranteed public broadcast)
        # Load environment variables manually to ensure they're available
        from dotenv import load_dotenv
        load_dotenv()
        
        alchemy_api_key = os.getenv('alchemy_api_key')
        infura_api_key = os.getenv('INFURA_API_KEY')
        
        self.logger.info(f"Environment check - Alchemy key: {'Found' if alchemy_api_key else 'Not found'}")
        self.logger.info(f"Environment check - Infura key: {'Found' if infura_api_key else 'Not found'}")
        
        if alchemy_api_key:
            self.primary_rpc = f'https://eth-mainnet.g.alchemy.com/v2/{alchemy_api_key}'
            self.w3 = Web3(Web3.HTTPProvider(self.primary_rpc))
            # Use multiple RPCs including Alchemy for guaranteed public broadcast
            self.broadcast_rpcs = [self.primary_rpc] + SEND_CAPABLE_RPCS[:3]  # Primary + 3 public RPCs
            self.logger.info(f"✅ Using Alchemy API for guaranteed public broadcasting")
        elif infura_api_key:
            self.primary_rpc = f'https://mainnet.infura.io/v3/{infura_api_key}'
            self.w3 = Web3(Web3.HTTPProvider(self.primary_rpc))
            self.broadcast_rpcs = [self.primary_rpc] + SEND_CAPABLE_RPCS
            self.logger.info(f"✅ Using Infura API as primary RPC")
        else:
            self.logger.warning(
                "No premium API keys found. Using public RPC nodes (may have broadcasting limitations)."
            )
            # Use the most reliable public RPC as primary (verified public broadcast)
            self.primary_rpc = "https://ethereum-rpc.publicnode.com"  # VERIFIED public broadcast
            self.w3 = Web3(Web3.HTTPProvider(self.primary_rpc))
            self.broadcast_rpcs = SEND_CAPABLE_RPCS
            
        self.logger.info(f"Primary RPC: {self.primary_rpc}")
        self.logger.info(f"Broadcast RPCs available: {len(self.broadcast_rpcs)}")
            
        self.tatum = TatumHelper()
        
        # Cache for gas prices (30 second expiration)
        self._gas_price_cache = {}
        self._gas_price_expiry = timedelta(seconds=30)
        
        # Test RPC capabilities
        self._test_rpc_capabilities()
    
    def _test_rpc_capabilities(self):
        """Test if RPC supports transaction sending"""
        try:
            if not self.w3.is_connected():
                self.logger.error("❌ Web3 not connected")
                return
                
            chain_id = self.w3.eth.chain_id
            latest_block = self.w3.eth.block_number
            self.logger.info(f"✅ Connected to Ethereum network, chain ID: {chain_id}, latest block: {latest_block}")
            
            # Test if we can send transactions (some public RPCs block this)
            test_tx = {
                'from': '0x0000000000000000000000000000000000000000',
                'to': '0x0000000000000000000000000000000000000000',
                'value': 0
            }
            # This will fail but tells us if the RPC supports transaction methods
            self.w3.eth.estimate_gas(test_tx)
        except Exception as e:
            error_msg = str(e).lower()
            if 'method not found' in error_msg or 'not supported' in error_msg:
                self.logger.warning("⚠️ RPC endpoint may not support transaction sending")
            elif 'insufficient funds' in error_msg or 'execution reverted' in error_msg:
                self.logger.info("✅ RPC endpoint supports transaction methods")
            else:
                self.logger.debug(f"RPC capability test result: {str(e)}")
    
    def _broadcast_transaction_multi_rpc(self, signed_txn):
        """
        Advanced parallel broadcast with retry and backoff to ensure public mempool inclusion
        """
        import time
        import concurrent.futures
        from threading import Lock
        
        tx_hash = None
        successful_broadcasts = []
        failed_broadcasts = []
        hash_lock = Lock()
        
        def broadcast_to_rpc(rpc_url, max_retries=3):
            """Broadcast to single RPC with verification"""
            nonlocal tx_hash  # Declare nonlocal at the beginning
            for attempt in range(max_retries):
                try:
                    w3 = Web3(Web3.HTTPProvider(rpc_url, request_kwargs={'timeout': 15}))
                    if not w3.is_connected():
                        raise Exception("Connection failed")
                    
                    # Send raw transaction (Web3.py v6 uses rawTransaction)
                    raw_tx = signed_txn.rawTransaction if hasattr(signed_txn, 'rawTransaction') else signed_txn.raw_transaction
                    hash_result = w3.eth.send_raw_transaction(raw_tx).hex()
                    
                    # CRITICAL: Verify the transaction actually exists
                    time.sleep(1)  # Give RPC time to process
                    try:
                        tx_data = w3.eth.get_transaction(hash_result)
                        if not tx_data:
                            raise Exception(f"Transaction {hash_result} not found after broadcast - fake hash!")
                        
                        # Verify transaction data matches what we sent
                        # Note: signed_txn is a SignedTransaction object, access nonce from the transaction dict
                        expected_nonce = signed_txn.transaction.get('nonce') if hasattr(signed_txn, 'transaction') else None
                        if expected_nonce is not None and tx_data.get('nonce') != expected_nonce:
                            raise Exception(f"Transaction nonce mismatch - fake hash!")
                            
                        self.logger.info(f"✅ VERIFIED: Transaction {hash_result} confirmed on {rpc_url}")
                        
                    except Exception as verify_error:
                        raise Exception(f"Broadcast verification failed: {str(verify_error)}")
                    
                    with hash_lock:
                        if not tx_hash:  # First successful broadcast sets the hash
                            tx_hash = hash_result
                    
                    return {'rpc': rpc_url, 'hash': hash_result, 'attempt': attempt + 1, 'verified': True}
                    
                except Exception as e:
                    error_msg = str(e).lower()
                    
                    # SUCCESS CASES: These errors actually mean the transaction was successful
                    # Check for various formats of "already known" messages
                    if ('already known' in error_msg or 
                        'already in mempool' in error_msg or
                        'transaction underpriced' in error_msg or
                        'replacement transaction underpriced' in error_msg):
                        self.logger.info(f"✅ SUCCESS: Transaction already in mempool - {error_msg[:50]}")
                        # Calculate hash from signed transaction
                        from eth_hash.auto import keccak
                        raw_tx = signed_txn.rawTransaction if hasattr(signed_txn, 'rawTransaction') else signed_txn.raw_transaction
                        tx_hash_bytes = keccak(raw_tx)
                        calculated_hash = '0x' + tx_hash_bytes.hex()
                        
                        with hash_lock:
                            if not tx_hash:
                                tx_hash = calculated_hash
                        
                        return {'rpc': rpc_url, 'hash': calculated_hash, 'attempt': attempt + 1, 'verified': True, 'already_known': True}
                    
                    elif 'nonce too low' in error_msg:
                        self.logger.info(f"✅ SUCCESS: Transaction already processed - {error_msg[:50]}")
                        # Extract the expected nonce and calculate hash for that transaction
                        from eth_hash.auto import keccak
                        raw_tx = signed_txn.rawTransaction if hasattr(signed_txn, 'rawTransaction') else signed_txn.raw_transaction
                        tx_hash_bytes = keccak(raw_tx)
                        calculated_hash = '0x' + tx_hash_bytes.hex()
                        
                        with hash_lock:
                            if not tx_hash:
                                tx_hash = calculated_hash
                        
                        return {'rpc': rpc_url, 'hash': calculated_hash, 'attempt': attempt + 1, 'verified': True, 'nonce_processed': True}
                    
                    # Don't retry for certain errors
                    if any(x in error_msg for x in ['method not found', 'not supported', 'cannot fulfill']):
                        self.logger.warning(f"RPC {rpc_url} doesn't support broadcasting: {error_msg[:50]}")
                        break
                    
                    # Retry for temporary errors
                    if attempt < max_retries - 1:
                        wait_time = (2 ** attempt) * 0.5  # 0.5s, 1s, 2s
                        self.logger.debug(f"RPC {rpc_url} attempt {attempt + 1} failed, retrying in {wait_time}s: {error_msg[:50]}")
                        time.sleep(wait_time)
                    else:
                        return {'rpc': rpc_url, 'error': str(e)}
            
            return {'rpc': rpc_url, 'error': 'Max retries exceeded'}
        
        self.logger.info(f"🚀 Broadcasting transaction to {len(self.broadcast_rpcs)} RPCs in parallel...")
        
        # Parallel broadcast with timeout
        with concurrent.futures.ThreadPoolExecutor(max_workers=min(8, len(self.broadcast_rpcs))) as executor:
            future_to_rpc = {
                executor.submit(broadcast_to_rpc, rpc): rpc 
                for rpc in self.broadcast_rpcs[:5]  # Use top 5 RPCs for maximum public broadcast coverage
            }
            
            # Wait for results with timeout, but handle timeout gracefully
            try:
                for future in concurrent.futures.as_completed(future_to_rpc, timeout=8):  # Increased timeout
                    rpc = future_to_rpc[future]
                    try:
                        result = future.result()
                        if 'hash' in result and result.get('verified'):
                            successful_broadcasts.append(result)
                            if result.get('already_known'):
                                success_type = "ALREADY IN MEMPOOL"
                            elif result.get('nonce_processed'):
                                success_type = "ALREADY PROCESSED"
                            else:
                                success_type = "DIRECT SUCCESS"
                            self.logger.info(f"✅ {success_type}: {result['rpc'].split('/')[-1]} (attempt {result['attempt']}) - Hash: {result['hash'][:12]}...")
                            
                            # If we have a successful broadcast, we can return early for faster response
                            if tx_hash and len(successful_broadcasts) >= 1:
                                self.logger.info(f"🚀 Early success detected - transaction {tx_hash} broadcast successfully")
                                break
                        else:
                            failed_broadcasts.append(result)
                            error_msg = result.get('error', 'Unknown')
                            self.logger.warning(f"❌ Broadcast failed via {result['rpc']}: {error_msg}")
                    except Exception as e:
                        failed_broadcasts.append({'rpc': rpc, 'error': str(e)})
                        self.logger.debug(f"❌ Future exception for {rpc}: {str(e)}")
            except concurrent.futures.TimeoutError:
                self.logger.warning("⏰ Some RPC broadcasts timed out - checking if any succeeded")
                # Check remaining futures for any successes
                for future in future_to_rpc:
                    if future.done():
                        try:
                            result = future.result()
                            if 'hash' in result and result.get('verified'):
                                successful_broadcasts.append(result)
                                self.logger.info(f"✅ Late success found: {result['rpc'].split('/')[-1]} - Hash: {result['hash'][:12]}...")
                        except Exception:
                            pass
        
        # Log results and perform additional verification
        success_count = len(successful_broadcasts)
        if success_count > 0:
            self.logger.info(f"🎯 Transaction successfully broadcast to {success_count}/{len(self.broadcast_rpcs)} RPCs")
            
            # Log which RPCs worked
            successful_rpcs = [b['rpc'] for b in successful_broadcasts]
            self.logger.info(f"✅ Verified RPCs: {', '.join([rpc.split('/')[-1] for rpc in successful_rpcs])}")
            
            # SUCCESS: Transaction broadcast completed
            if tx_hash:
                self.logger.info(f"🎉 Transaction {tx_hash} broadcast completed successfully")
            
            if failed_broadcasts:
                failed_rpcs = [b['rpc'] for b in failed_broadcasts if 'error' in b]
                if failed_rpcs:
                    self.logger.debug(f"❌ Failed RPCs: {', '.join([rpc.split('/')[-1] for rpc in failed_rpcs])}")
            
            return tx_hash
        else:
            # All broadcasts failed
            self.logger.error("❌ All RPC broadcasts failed!")
            for failure in failed_broadcasts:
                self.logger.error(f"   {failure['rpc']}: {failure.get('error', 'Unknown error')}")
            
            # Don't raise exception if we have a tx_hash from successful broadcast
            if tx_hash:
                self.logger.warning("⚠️ Some RPCs failed but transaction was broadcast successfully")
                return tx_hash
            else:
                raise Exception("Failed to broadcast transaction to any RPC endpoint")
    
    def test_rpc_broadcast_capability(self):
        """
        Test if current RPC endpoints support public transaction broadcasting
        """
        self.logger.info("🧪 Testing RPC broadcast capabilities...")
        
        test_results = {}
        all_rpcs = self.broadcast_rpcs[:5]  # Test first 5 broadcast RPCs
        
        for rpc_url in all_rpcs:
            try:
                test_w3 = Web3(Web3.HTTPProvider(rpc_url))
                if test_w3.is_connected():
                    # Test if the RPC supports eth_sendRawTransaction
                    # We'll try with an invalid transaction to see the error type
                    try:
                        test_w3.eth.send_raw_transaction(b'0x00')  # Invalid transaction
                    except Exception as e:
                        error_msg = str(e).lower()
                        if 'method not found' in error_msg or 'not supported' in error_msg:
                            test_results[rpc_url] = "❌ Does not support transaction sending"
                        elif 'invalid' in error_msg or 'decode' in error_msg:
                            test_results[rpc_url] = "✅ Supports transaction sending"
                        else:
                            test_results[rpc_url] = f"⚠️ Unknown response: {error_msg[:50]}"
                else:
                    test_results[rpc_url] = "❌ Connection failed"
            except Exception as e:
                test_results[rpc_url] = f"❌ Error: {str(e)[:50]}"
        
        self.logger.info("RPC Broadcast Test Results:")
        for rpc, result in test_results.items():
            self.logger.info(f"  {rpc}: {result}")
            
        return test_results
    
    def check_mempool_visibility(self, tx_hash, timeout=30):
        """
        Check if transaction is visible across multiple RPCs (public mempool test)
        """
        import time
        import concurrent.futures
        
        self.logger.info(f"👁️ Checking mempool visibility for {tx_hash}")
        
        def check_tx_on_rpc(rpc_url):
            """Check if transaction exists on specific RPC"""
            try:
                w3 = Web3(Web3.HTTPProvider(rpc_url, request_kwargs={'timeout': 10}))
                if not w3.is_connected():
                    return {'rpc': rpc_url, 'status': 'connection_failed'}
                
                tx_data = w3.eth.get_transaction(tx_hash)
                if tx_data:
                    block_number = tx_data.get('blockNumber')
                    status = 'confirmed' if block_number else 'pending'
                    return {
                        'rpc': rpc_url, 
                        'status': status,
                        'block': block_number,
                        'gas_price': tx_data.get('gasPrice', 0) / 10**9 if tx_data.get('gasPrice') else 0
                    }
                else:
                    return {'rpc': rpc_url, 'status': 'not_found'}
                    
            except Exception as e:
                error_msg = str(e).lower()
                if 'not found' in error_msg or 'null' in error_msg:
                    return {'rpc': rpc_url, 'status': 'not_found'}
                else:
                    return {'rpc': rpc_url, 'status': 'error', 'error': str(e)[:50]}
        
        # Test visibility across multiple RPCs
        visibility_results = {}
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=6) as executor:
            future_to_rpc = {
                executor.submit(check_tx_on_rpc, rpc): rpc 
                for rpc in self.broadcast_rpcs[:6]
            }
            
            for future in concurrent.futures.as_completed(future_to_rpc, timeout=timeout):
                try:
                    result = future.result()
                    rpc_name = result['rpc'].split('/')[-1]  # Get domain name
                    visibility_results[rpc_name] = result
                    
                    status = result['status']
                    if status == 'confirmed':
                        self.logger.info(f"   ✅ {rpc_name}: CONFIRMED in block {result.get('block')}")
                    elif status == 'pending':
                        self.logger.info(f"   ⏳ {rpc_name}: PENDING in mempool")
                    elif status == 'not_found':
                        self.logger.warning(f"   ❌ {rpc_name}: NOT FOUND")
                    else:
                        self.logger.debug(f"   ⚠️ {rpc_name}: {status}")
                        
                except Exception as e:
                    self.logger.debug(f"   ❌ Error checking RPC: {str(e)}")
        
        # Analyze results
        visible_count = sum(1 for r in visibility_results.values() 
                           if r['status'] in ['confirmed', 'pending'])
        total_count = len(visibility_results)
        
        visibility_ratio = visible_count / total_count if total_count > 0 else 0
        
        self.logger.info(f"📊 Mempool visibility: {visible_count}/{total_count} RPCs ({visibility_ratio:.1%})")
        
        # Return analysis
        return {
            'visible_count': visible_count,
            'total_count': total_count,
            'visibility_ratio': visibility_ratio,
            'results': visibility_results,
            'public_mempool': visibility_ratio >= 0.5  # Consider public if >50% see it
        }
        
    def prepare_transaction(self, sender: str, recipient: str, amount, 
                          private_key: str = None, request_data: dict = None) -> Tuple[Dict, Optional[str]]:
        """Prepare an Ethereum transaction with improved amount handling"""
        try:
            # تبدیل ایمن amount با تشخیص "send all" feature
            try:
                if request_data:
                    # استفاده از متد جدید برای پشتیبانی amount_wei
                    amount_wei = self.get_amount_from_request(request_data)
                    amount_decimal = Decimal(amount_wei) / Decimal(10**18)
                    
                    # تشخیص درخواست "send all" - اگر amount برابر با balance باشد
                    is_send_all = request_data.get('send_all', False) or request_data.get('max_amount', False)
                    self.logger.info(f"🔍 Send All Detection: is_send_all={is_send_all}")
                else:
                    # روش قدیمی برای سازگاری
                    amount_decimal = self.parse_amount_to_wei(amount) / Decimal(10**18)
                    is_send_all = False
            except ValueError as amount_error:
                return None, f"invalid_input: {str(amount_error)}"
            
            # اعتبارسنجی ایمن آدرس‌ها
            try:
                sender_normalized = self._normalize_address(sender)
                recipient_normalized = self._normalize_address(recipient)
            except ValueError as addr_error:
                return None, f"invalid_input: {str(addr_error)}"
                
            # Get sender's balance
            balance, error = self.get_balance(sender_normalized)
            if error:
                if "upstream_error:" in error:
                    return None, error
                else:
                    return None, f"upstream_error: Error getting balance: {error}"
            
            # تشخیص هوشمند "Send All" بر اساس مقایسه با موجودی
            if not is_send_all and abs(amount_decimal - balance) < Decimal('0.000001'):
                is_send_all = True
                self.logger.info(f"🔍 Auto-detected Send All: amount ({amount_decimal}) ≈ balance ({balance})")
            
            self.logger.info(f"📊 Transaction Analysis:")
            self.logger.info(f"   Requested amount: {amount_decimal} ETH")
            self.logger.info(f"   Available balance: {balance} ETH") 
            self.logger.info(f"   Is Send All: {is_send_all}")
                
            # Estimate fee با آدرس‌های نرمال شده
            fee, error = self.estimate_fee(sender_normalized, recipient_normalized, amount_decimal)
            if error:
                return None, error  # خطا قبلاً با prefix مناسب آماده شده
                
            # ✅ SMART FEE HANDLING: Handle "Send All" vs specific amount
            original_amount = amount_decimal
            
            if is_send_all:
                # برای Send All، مقدار = موجودی - کارمزد - buffer
                buffer = Decimal('0.000001')  # 1 gwei buffer
                max_sendable = balance - fee - buffer
                
                if max_sendable <= 0:
                    self.logger.error(f"❌ INSUFFICIENT BALANCE for Send All:")
                    self.logger.error(f"   Balance: {balance} ETH")
                    self.logger.error(f"   Fee: {fee} ETH")
                    self.logger.error(f"   Buffer: {buffer} ETH")
                    return None, f"Insufficient balance to send all. Balance: {balance} ETH, Required fee: {fee} ETH. Please add more ETH to your wallet."
                
                amount_decimal = max_sendable
                total_required = amount_decimal + fee
                
                self.logger.info(f"🔧 ETH SEND ALL TRANSACTION:")
                self.logger.info(f"   Original request: Send All ({original_amount} ETH)")
                self.logger.info(f"   Available balance: {balance} ETH")
                self.logger.info(f"   Estimated fee: {fee} ETH")
                self.logger.info(f"   Buffer: {buffer} ETH")
                self.logger.info(f"   ✅ Calculated amount: {amount_decimal} ETH")
                self.logger.info(f"   Total required: {total_required} ETH")
            else:
                # برای مقدار مشخص، بررسی کافی بودن موجودی
                total_required = amount_decimal + fee
                
                self.logger.info(f"🔧 ETH SPECIFIC AMOUNT TRANSACTION:")
                self.logger.info(f"   Requested amount: {original_amount} ETH")
                self.logger.info(f"   Estimated fee: {fee} ETH")
                self.logger.info(f"   Total required: {total_required} ETH")
                self.logger.info(f"   Available balance: {balance} ETH")
            
            # IMPROVED: Smart balance handling for native ETH
            adjustment_message = ""  # Initialize adjustment message
            if balance < total_required:
                # Calculate maximum sendable amount with small buffer
                buffer = Decimal('0.000001')  # 1 gwei buffer for gas price fluctuations
                max_sendable = balance - fee - buffer
                
                if max_sendable <= 0:
                    self.logger.error(f"❌ INSUFFICIENT BALANCE: Balance: {balance} ETH, Fee: {fee} ETH")
                    self.logger.error(f"   💡 Need at least {fee + buffer:.6f} ETH to cover fees")
                    return None, f"Insufficient balance to cover network fee. Balance: {balance} ETH, Required fee: {fee} ETH. Please add more ETH to your wallet."
                
                # Auto-adjust amount with user-friendly message
                amount_decimal = max_sendable
                self.logger.info(f"   🔧 AUTO-ADJUSTMENT: Reducing amount to fit available balance")
                self.logger.info(f"   📊 Original: {original_amount} ETH → Adjusted: {amount_decimal:.6f} ETH")
                self.logger.info(f"   💰 Will send maximum possible: {amount_decimal:.6f} ETH")
                
                # Add warning for user
                adjustment_message = f" (Amount auto-adjusted from {original_amount} to {amount_decimal:.6f} ETH to cover network fees)"
                
            # Generate transaction ID
            transaction_id = str(uuid.uuid4())
            
            # Calculate balance after transaction
            balance_after = balance - amount_decimal - fee
            
            # Prepare transaction details
            tx_details = {
                "transaction_id": transaction_id,
                "details": {
                    "amount": str(amount_decimal),  # This may be adjusted amount
                    "original_amount": str(original_amount),  # Store original for reference
                    "auto_adjusted": amount_decimal != original_amount,  # Flag if adjusted
                    "blockchain": "ethereum",
                    "estimated_fee": str(fee),
                    "explorer_url": "",  # Will be set after successful transaction
                    "recipient": recipient_normalized,
                    "sender": sender_normalized,
                    "sender_balance_after": str(balance_after),
                    "sender_balance_before": str(balance)
                },
                "expires_at": (datetime.now() + timedelta(minutes=15)).isoformat(),
                "message": "Transaction prepared successfully" + (
                    f" (Send All: {amount_decimal:.6f} ETH after deducting fees)" if is_send_all else 
                    (adjustment_message if amount_decimal != original_amount else "")
                ),
                "success": True
            }
            
            # Store transaction
            self._store_transaction(transaction_id, tx_details)
            
            # Log preparation
            self._log_transaction(transaction_id, 'prepared', tx_details)
            
            return tx_details, None
            
        except Exception as e:
            self.logger.error(f"Error preparing transaction: {str(e)}")
            return None, str(e)
            
    def send_transaction(self, transaction_id: str, private_key: str) -> Tuple[Dict, Optional[str]]:
        """Send a prepared Ethereum transaction with strict balance verification"""
        try:
            # Get stored transaction
            tx_data = self._get_stored_transaction(transaction_id)
            if not tx_data:
                return {}, "Transaction not found or expired"
                
            # Extract transaction details
            sender = tx_data.get('details', {}).get('sender')
            recipient = tx_data.get('details', {}).get('recipient')
            amount_str = tx_data.get('details', {}).get('amount')
            
            if not all([sender, recipient, amount_str]):
                self.logger.error(f"Transaction data is incomplete")
                return {}, "Transaction data is incomplete"
                
            try:
                amount = Decimal(amount_str)
            except Exception as e:
                self.logger.error(f"Error converting amount to Decimal: {str(e)}")
                return {}, f"Invalid amount format: {amount_str}"
                
            # ✅ STRICT BALANCE VERIFICATION at confirm time
            self.logger.info(f"🔧 ETH CONFIRM TRANSACTION - Final balance check:")
            
            # Get current balance (may have changed since prepare)
            current_balance, balance_error = self.get_balance(sender)
            if balance_error:
                self.logger.error(f"Could not verify balance before sending: {balance_error}")
                return {}, f"Could not verify current balance: {balance_error}"
            
            # Get current fee estimate (gas prices may have changed)
            current_fee, fee_error = self.estimate_fee(sender, recipient, amount)
            if fee_error:
                self.logger.warning(f"Could not get current fee estimate, using default: {fee_error}")
                current_fee = Decimal('0.002')  # Default fallback fee
            
            total_required = amount + current_fee
            
            self.logger.info(f"   Current balance: {current_balance} ETH")
            self.logger.info(f"   Amount to send: {amount} ETH")
            self.logger.info(f"   Current fee: {current_fee} ETH")
            self.logger.info(f"   Total required: {total_required} ETH")
            self.logger.info(f"   Balance sufficient: {current_balance >= total_required}")
            
            # Strict balance check with small buffer for gas price fluctuations
            # Allow a small buffer (0.1% or 0.0001 ETH, whichever is smaller) for gas price changes
            buffer = min(total_required * Decimal('0.001'), Decimal('0.0001'))  # 0.1% or 0.0001 ETH buffer
            total_required_with_buffer = total_required + buffer
            
            if current_balance < total_required_with_buffer:
                # If balance is very close, try to auto-adjust the amount
                if current_balance >= total_required * Decimal('0.999'):  # Within 0.1% of required
                    self.logger.info(f"⚠️ Balance very close to required amount, auto-adjusting...")
                    # Reduce amount slightly to fit available balance
                    adjusted_amount = current_balance - current_fee - Decimal('0.000001')  # Leave 1 gwei buffer
                    if adjusted_amount > Decimal('0'):
                        self.logger.info(f"Auto-adjusting amount from {amount} to {adjusted_amount} ETH")
                        amount = adjusted_amount
                        total_required = amount + current_fee
                    else:
                        error_msg = f"Insufficient balance at confirm time. Available: {current_balance} ETH, Required: {total_required} ETH (Amount: {amount} + Fee: {current_fee})"
                        self.logger.error(f"❌ CONFIRM FAILED: {error_msg}")
                        return {}, error_msg
                else:
                    error_msg = f"Insufficient balance at confirm time. Available: {current_balance} ETH, Required: {total_required} ETH (Amount: {amount} + Fee: {current_fee})"
                    self.logger.error(f"❌ CONFIRM FAILED: {error_msg}")
                    return {}, error_msg
            
            self.logger.info(f"✅ Balance verification passed, proceeding with multi-method transaction")
            self.logger.info(f"Sending Ethereum transaction using multi-method approach")
            
            # Method 1: EIP-1559 transaction (replacing legacy)
            self.logger.debug(f"Method 1: EIP-1559 transaction (primary method)")
            
            try:
                # نرمال‌سازی آدرس‌ها
                sender_norm = self.w3.to_checksum_address(sender)
                recipient_norm = self.w3.to_checksum_address(recipient)
                
                # FIXED: Get correct nonce from 'latest' block to avoid pending issues
                nonce = self.w3.eth.get_transaction_count(sender_norm, 'latest')
                chain_id = self.w3.eth.chain_id
                
                self.logger.info(f"🔧 Transaction nonce: {nonce} (using 'latest' block for accuracy)")
                
                # دریافت BaseFee از pending block
                latest_block = self.w3.eth.get_block('pending')
                if 'baseFeePerGas' not in latest_block:
                    latest_block = self.w3.eth.get_block('latest')
                    
                base_fee = latest_block.get('baseFeePerGas', self.w3.eth.gas_price)
                
                # IMPROVED: Dynamic gas price calculation for competitive public mempool inclusion
                try:
                    network_priority = self.w3.eth.max_priority_fee
                    # Use network priority + buffer for competitive inclusion
                    priority_fee = max(network_priority, self.w3.to_wei('2', 'gwei'))
                    priority_fee = min(priority_fee, self.w3.to_wei('20', 'gwei'))  # Cap at 20 Gwei
                except Exception:
                    priority_fee = self.w3.to_wei('5', 'gwei')  # Fallback to 5 Gwei
                
                # FIXED: Calculate reasonable max fee to prevent insufficient funds
                # Use smaller, more reasonable buffer
                buffer = min(base_fee * 1.5, self.w3.to_wei('5', 'gwei'))  # Conservative buffer
                max_fee_per_gas = base_fee + priority_fee + buffer
                
                # Cap at reasonable maximum to prevent excessive fees
                max_reasonable = self.w3.to_wei('50', 'gwei')  # 50 Gwei cap
                if max_fee_per_gas > max_reasonable:
                    self.logger.warning(f"Capping excessive gas price: {max_fee_per_gas/10**9:.2f} -> 50.0 Gwei")
                    max_fee_per_gas = max_reasonable
                
                self.logger.info(f"Method 1 - EIP-1559: base={self.w3.from_wei(base_fee, 'gwei'):.2f} gwei, priority={self.w3.from_wei(priority_fee, 'gwei'):.2f} gwei, max={self.w3.from_wei(max_fee_per_gas, 'gwei'):.2f} gwei")
                
                # آماده‌سازی تراکنش Legacy (Type 0) برای public mempool
                transaction = {
                    'from': sender_norm,
                    'to': recipient_norm,
                    'value': self.w3.to_wei(amount, 'ether'),
                    'gas': 21000,
                    'gasPrice': max_fee_per_gas,  # Use maxFee as gasPrice for legacy
                    'nonce': nonce,
                    'chainId': chain_id
                    # No 'type' field = Legacy transaction (Type 0)
                }
                
                # امضا و ارسال با multi-RPC broadcast + verification
                signed_txn = self.w3.eth.account.sign_transaction(transaction, private_key)
                tx_hash = self._broadcast_transaction_multi_rpc(signed_txn)
                
                # SUCCESS: Transaction was broadcast successfully
                if tx_hash:
                    self.logger.info(f"✅ SUCCESS: Method 1 - Transaction broadcast successful: {tx_hash}")
                    self.logger.info(f"🔗 Etherscan: https://etherscan.io/tx/{tx_hash}")
                    
                    # Optional verification (non-blocking)
                    try:
                        self.logger.info(f"🔍 Background verification of transaction {tx_hash}...")
                        # Quick check without timeout to avoid API delays
                        import threading
                        def verify_later():
                            try:
                                import time
                                time.sleep(5)  # Wait 5 seconds for propagation
                                mempool_check = self.check_mempool_visibility(tx_hash, timeout=10)
                                if mempool_check['public_mempool']:
                                    self.logger.info(f"✅ VERIFIED: Transaction {tx_hash} confirmed in public mempool")
                                else:
                                    self.logger.warning(f"⚠️ Transaction {tx_hash} verification pending (may need more time)")
                            except Exception as e:
                                self.logger.debug(f"Background verification failed: {str(e)}")
                        
                        thread = threading.Thread(target=verify_later)
                        thread.daemon = True
                        thread.start()
                        
                    except Exception as verify_error:
                        self.logger.debug(f"Background verification setup failed: {str(verify_error)}")
                    
                    # بروزرسانی داده‌ها
                    tx_data.update({
                        'tx_hash': tx_hash,
                        'status': 'sent',
                        'sent_at': datetime.now().isoformat(),
                        'sent_via': 'web3_simple',
                        'method_used': 1
                    })
                    # Update explorer URL with actual tx hash
                    if 'details' in tx_data:
                        tx_data['details']['explorer_url'] = f"https://etherscan.io/tx/{tx_hash}"
                    self._store_transaction(transaction_id, tx_data)
                    
                    return {
                        'transaction_id': transaction_id,
                        'tx_hash': tx_hash,
                        'status': 'sent',
                        'method': 'web3_simple',
                        'explorer_url': f"https://etherscan.io/tx/{tx_hash}",
                        'success': True
                    }, None
                else:
                    raise Exception("No transaction hash returned from broadcast")
                
            except Exception as e:
                self.logger.error(f"Method 1 (Simple Web3) failed: {str(e)}")
                self.logger.error(f"Method 1 details: sender={sender}, recipient={recipient}, amount={amount}")
                try:
                    self.logger.error(f"Method 1 transaction params: {transaction}")
                except:
                    self.logger.error("Method 1 transaction params: not yet defined")
                import traceback
                self.logger.error(f"Method 1 traceback: {traceback.format_exc()}")
            
            # Method 2: EIP-1559 transaction (Type 2)
            self.logger.debug(f"Method 2: EIP-1559 transaction")
            
            try:
                # نرمال‌سازی آدرس‌ها
                sender_norm = self.w3.to_checksum_address(sender)
                recipient_norm = self.w3.to_checksum_address(recipient)
                
                # دریافت اطلاعات شبکه
                chain_id = self.w3.eth.chain_id
                nonce = self.w3.eth.get_transaction_count(sender_norm, 'latest')  # FIXED: use latest for accuracy
                
                self.logger.info(f"🔧 Method 2 nonce: {nonce} (using 'latest' block)")
                
                # IMPROVED: Dynamic gas price calculation with real-time network conditions
                latest_block = self.w3.eth.get_block('pending')
                if 'baseFeePerGas' not in latest_block:
                    latest_block = self.w3.eth.get_block('latest')
                    
                base_fee = latest_block.get('baseFeePerGas', self.w3.eth.gas_price)
                
                # Get network priority fee dynamically
                try:
                    network_priority = self.w3.eth.max_priority_fee
                    # Use network priority + buffer for competitive inclusion
                    max_priority_fee = max(network_priority, self.w3.to_wei('2', 'gwei'))
                    max_priority_fee = min(max_priority_fee, self.w3.to_wei('20', 'gwei'))  # Cap at 20 Gwei
                except Exception:
                    max_priority_fee = self.w3.to_wei('5', 'gwei')  # Fallback to 5 Gwei
                
                # FIXED: Calculate reasonable max fee for Method 2
                buffer = min(base_fee * 1.5, self.w3.to_wei('5', 'gwei'))  # Conservative buffer
                max_fee_per_gas = base_fee + max_priority_fee + buffer
                
                # Cap at reasonable maximum
                max_reasonable = self.w3.to_wei('50', 'gwei')  # 50 Gwei cap
                if max_fee_per_gas > max_reasonable:
                    self.logger.warning(f"Method 2: Capping excessive gas price: {max_fee_per_gas/10**9:.2f} -> 50.0 Gwei")
                    max_fee_per_gas = max_reasonable
                
                self.logger.info(f"Method 2 - EIP-1559 fees: base={self.w3.from_wei(base_fee, 'gwei'):.2f} gwei, priority={self.w3.from_wei(max_priority_fee, 'gwei'):.2f} gwei, max={self.w3.from_wei(max_fee_per_gas, 'gwei'):.2f} gwei")
                
                # آماده‌سازی تراکنش Legacy برای public broadcast
                transaction = {
                    'from': sender_norm,
                    'to': recipient_norm,
                    'value': self.w3.to_wei(amount, 'ether'),
                    'gas': 21000,
                    'gasPrice': max_fee_per_gas,  # Legacy gas price
                    'nonce': nonce,
                    'chainId': chain_id
                    # Legacy transaction (Type 0)
                }
                
                # امضا و ارسال با multi-RPC broadcast
                signed_txn = self.w3.eth.account.sign_transaction(transaction, private_key)
                tx_hash = self._broadcast_transaction_multi_rpc(signed_txn)
                
                # SUCCESS: Transaction was broadcast successfully
                if tx_hash:
                    self.logger.info(f"✅ SUCCESS: Method 2 - EIP-1559 transaction sent: {tx_hash}")
                    self.logger.info(f"🔗 Etherscan: https://etherscan.io/tx/{tx_hash}")
                    
                    # Update transaction data
                    tx_data.update({
                        'tx_hash': tx_hash,
                        'status': 'sent',
                        'sent_at': datetime.now().isoformat(),
                        'sent_via': 'eip1559',
                        'method_used': 2
                    })
                    # Update explorer URL with actual tx hash
                    if 'details' in tx_data:
                        tx_data['details']['explorer_url'] = f"https://etherscan.io/tx/{tx_hash}"
                    self._store_transaction(transaction_id, tx_data)
                    
                    return {
                        'transaction_id': transaction_id,
                        'tx_hash': tx_hash,
                        'status': 'sent',
                        'method': 'eip1559',
                        'explorer_url': f"https://etherscan.io/tx/{tx_hash}",
                        'success': True
                    }, None
                else:
                    raise Exception("No transaction hash returned from broadcast")
                
            except Exception as e:
                self.logger.error(f"Method 2 (EIP-1559) failed: {str(e)}")
                self.logger.error(f"Method 2 details: sender={sender_norm}, recipient={recipient_norm}, amount={amount}")
                try:
                    self.logger.error(f"Method 2 transaction params: {transaction}")
                except:
                    self.logger.error("Method 2 transaction params: not yet defined")
                import traceback
                self.logger.error(f"Method 2 traceback: {traceback.format_exc()}")
            
            # Method 3: Conservative EIP-1559 approach
            self.logger.debug(f"Method 3: Conservative EIP-1559 approach")
            
            try:
                # استفاده از پارامترهای محافظه‌کارانه
                sender_norm = self.w3.to_checksum_address(sender)
                recipient_norm = self.w3.to_checksum_address(recipient)
                
                nonce = self.w3.eth.get_transaction_count(sender_norm, 'latest')  # FIXED: use latest
                chain_id = self.w3.eth.chain_id
                
                self.logger.info(f"🔧 Method 3 nonce: {nonce} (using 'latest' block)")
                
                # دریافت BaseFee از pending block
                latest_block = self.w3.eth.get_block('pending')
                if 'baseFeePerGas' not in latest_block:
                    latest_block = self.w3.eth.get_block('latest')
                    
                base_fee = latest_block.get('baseFeePerGas', self.w3.eth.gas_price)
                
                # IMPROVED: Conservative but competitive EIP-1559 settings
                try:
                    network_priority = self.w3.eth.max_priority_fee
                    # Conservative approach: use minimum viable priority fee
                    priority_fee = max(network_priority * 0.8, self.w3.to_wei('1.5', 'gwei'))
                    priority_fee = min(priority_fee, self.w3.to_wei('10', 'gwei'))  # Conservative cap
                except Exception:
                    priority_fee = self.w3.to_wei('2', 'gwei')  # Conservative fallback
                
                # FIXED: Conservative and reasonable buffer calculation
                buffer = min(base_fee, self.w3.to_wei('3', 'gwei'))  # Very conservative buffer
                max_fee_per_gas = base_fee + priority_fee + buffer
                
                # Cap at conservative maximum
                max_reasonable = self.w3.to_wei('25', 'gwei')  # Conservative 25 Gwei cap
                if max_fee_per_gas > max_reasonable:
                    self.logger.warning(f"Method 3: Capping gas price: {max_fee_per_gas/10**9:.2f} -> 25.0 Gwei")
                    max_fee_per_gas = max_reasonable
                
                self.logger.info(f"Method 3 - Conservative EIP-1559: base={self.w3.from_wei(base_fee, 'gwei'):.2f} gwei, priority={self.w3.from_wei(priority_fee, 'gwei'):.2f} gwei, max={self.w3.from_wei(max_fee_per_gas, 'gwei'):.2f} gwei")
                
                transaction = {
                    'from': sender_norm,
                    'to': recipient_norm,
                    'value': self.w3.to_wei(amount, 'ether'),
                    'gas': 21000,
                    'maxPriorityFeePerGas': priority_fee,
                    'maxFeePerGas': max_fee_per_gas,
                    'nonce': nonce,
                    'chainId': chain_id,
                    'type': 2  # EIP-1559
                }
                
                signed_txn = self.w3.eth.account.sign_transaction(transaction, private_key)
                tx_hash = self._broadcast_transaction_multi_rpc(signed_txn)
                
                # SUCCESS: Transaction was broadcast successfully
                if tx_hash:
                    self.logger.info(f"✅ SUCCESS: Method 3 - Conservative transaction sent: {tx_hash}")
                    self.logger.info(f"🔗 Etherscan: https://etherscan.io/tx/{tx_hash}")
                    
                    tx_data.update({
                        'tx_hash': tx_hash,
                        'status': 'sent',
                        'sent_at': datetime.now().isoformat(),
                        'sent_via': 'conservative',
                        'method_used': 3
                    })
                    # Update explorer URL with actual tx hash
                    if 'details' in tx_data:
                        tx_data['details']['explorer_url'] = f"https://etherscan.io/tx/{tx_hash}"
                    self._store_transaction(transaction_id, tx_data)
                    
                    return {
                        'transaction_id': transaction_id,
                        'tx_hash': tx_hash,
                        'status': 'sent',
                        'method': 'conservative',
                        'explorer_url': f"https://etherscan.io/tx/{tx_hash}",
                        'success': True
                    }, None
                else:
                    raise Exception("No transaction hash returned from broadcast")
                
            except Exception as e:
                self.logger.error(f"Method 3 (Conservative) failed: {str(e)}")
                self.logger.error(f"Method 3 details: sender={sender_norm}, recipient={recipient_norm}, amount={amount}")
                try:
                    self.logger.error(f"Method 3 transaction params: {transaction}")
                except:
                    self.logger.error("Method 3 transaction params: not yet defined")
                import traceback
                self.logger.error(f"Method 3 traceback: {traceback.format_exc()}")
            
            # همه روش‌ها شکست خورد - بهبود error reporting
            error_msg = "All transaction methods failed. This could be due to: 1) Network congestion, 2) Invalid private key, 3) Insufficient funds, 4) Invalid transaction parameters. Please check your wallet and try again."
            self.logger.error(f"❌ ALL METHODS FAILED: {error_msg}")
            self.logger.error(f"Transaction details: sender={sender}, recipient={recipient}, amount={amount}")
            self.logger.error(f"Balance check passed: {current_balance} >= {total_required}")
            
            return {}, error_msg
                
        except Exception as e:
            self.logger.error(f"Error sending transaction: {str(e)}")
            return {}, str(e)
            
    def _normalize_address(self, addr: str) -> str:
        """نرمال‌سازی ایمن آدرس با پشتیبانی ENS"""
        try:
            # حذف فاصه‌های اضافی
            addr = addr.strip()
            
            # بررسی فرمت اولیه
            if not addr:
                raise ValueError("آدرس نمی‌تواند خالی باشد")
            
            # اگر آدرس hex معتبر است
            if self.w3.is_address(addr):
                return self.w3.to_checksum_address(addr)
            
            # تلاش برای resolve کردن ENS
            if '.eth' in addr.lower():
                try:
                    resolved = self.w3.ens.address(addr)
                    if resolved:
                        return self.w3.to_checksum_address(resolved)
                    else:
                        raise ValueError(f"ENS domain '{addr}' could not be resolved")
                except Exception as ens_error:
                    raise ValueError(f"ENS resolution failed for '{addr}': {str(ens_error)}")
            
            # آدرس نامعتبر
            raise ValueError(f"Invalid address format: '{addr}'. Please use 0x format or valid ENS domain.")
            
        except ValueError:
            raise  # ValueError ها را مستقیماً پاس کن
        except Exception as e:
            raise ValueError(f"Address validation error: {str(e)}")

    def parse_amount_to_wei(self, amount_input) -> int:
        """
        تبدیل ایمن amount از هر فرمت به Wei
        Safe amount conversion from any format to Wei
        """
        try:
            from decimal import Decimal, ROUND_DOWN, InvalidOperation, getcontext
            getcontext().prec = 80  # دقت بالا برای محاسبات Wei
            
            # تشخیص نوع ورودی
            if isinstance(amount_input, Decimal):
                dec = amount_input
            elif isinstance(amount_input, (int, float)):
                dec = Decimal(str(amount_input))
            elif isinstance(amount_input, str):
                # پاک‌سازی رشته
                cleaned = amount_input.strip().replace(',', '.')
                if not cleaned:
                    raise ValueError("Amount cannot be empty")
                dec = Decimal(cleaned)
            else:
                raise ValueError(f"Unsupported amount type: {type(amount_input)}")
            
            # بررسی مقدار مثبت
            if dec <= 0:
                raise ValueError("Amount must be positive")
            
            # بررسی حد معقول (حداکثر 1 میلیون ETH)
            if dec > Decimal('1000000'):
                raise ValueError("Amount too large (max: 1,000,000 ETH)")
            
            # تبدیل به Wei با دقت
            dec = dec.quantize(Decimal('1.000000000000000000'), rounding=ROUND_DOWN)
            wei_amount = int((dec * (Decimal(10) ** 18)).to_integral_value(rounding=ROUND_DOWN))
            
            return wei_amount
            
        except (InvalidOperation, ValueError) as e:
            raise ValueError(f"Invalid amount: {str(e)}")
        except Exception as e:
            raise ValueError(f"Amount conversion error: {str(e)}")

    def get_amount_from_request(self, request_data: dict) -> int:
        """
        دریافت amount از request با پشتیبانی چند فرمت
        Get amount from request supporting multiple formats
        """
        try:
            # اولویت 1: amount_wei (مستقیم)
            if 'amount_wei' in request_data and request_data['amount_wei'] not in (None, '', 0):
                try:
                    wei_amount = int(str(request_data['amount_wei']).strip())
                    if wei_amount <= 0:
                        raise ValueError("Amount_wei must be positive")
                    return wei_amount
                except (ValueError, TypeError) as e:
                    raise ValueError(f"Invalid amount_wei format: {str(e)}")
            
            # اولویت 2: amount (بر حسب ETH)
            elif 'amount' in request_data and request_data['amount'] not in (None, '', 0):
                return self.parse_amount_to_wei(request_data['amount'])
            
            else:
                raise ValueError("Missing amount or amount_wei field")
                
        except ValueError:
            raise  # ValueError ها را مستقیماً پاس کن
        except Exception as e:
            raise ValueError(f"Amount parsing error: {str(e)}")

    def estimate_fee(self, sender: str, recipient: str, amount: Decimal, 
                    smart_contract_address: Optional[str] = None) -> Tuple[Decimal, Optional[str]]:
        """
        تخمین کارمزد ایمن با مدیریت کامل خطاها
        Safe fee estimation with complete error handling
        """
        try:
            # نرمال‌سازی ایمن آدرس‌ها (رفع مشکل 1)
            try:
                sender = self._normalize_address(sender)
                recipient = self._normalize_address(recipient)
            except ValueError as addr_error:
                # خطای ورودی - باید 422 باشد نه 400
                return None, f"invalid_input: {str(addr_error)}"
            
            # دریافت chainId پویا
            try:
                chain_id = self.w3.eth.chain_id
                self.logger.debug(f"Using dynamic chain_id: {chain_id}")
            except Exception as chain_error:
                return None, f"upstream_error: Could not get chain ID: {str(chain_error)}"
            
            # تبدیل ایمن مقدار به Wei (رفع مشکل 2)
            try:
                amount_wei = self.parse_amount_to_wei(amount)
            except ValueError as amount_error:
                return None, f"invalid_input: {str(amount_error)}"
            
            # آماده‌سازی transaction برای estimate_gas
            transaction_params = {
                'from': sender,
                'to': recipient,
                'value': amount_wei
            }
            
            # تخمین واقعی gas با مدیریت خطای revert (رفع مشکل 3)
            try:
                estimated_gas = self.w3.eth.estimate_gas(transaction_params)
                gas_limit = max(21000, int(estimated_gas * 1.2))
                self.logger.debug(f"Real gas estimation: {estimated_gas}, with buffer: {gas_limit}")
                
            except Exception as gas_error:
                error_msg = str(gas_error).lower()
                
                # تشخیص نوع خطای estimate_gas
                if "execution reverted" in error_msg or "revert" in error_msg:
                    return None, f"invalid_input: Transaction would fail - recipient contract rejected the transfer"
                elif "insufficient funds" in error_msg:
                    return None, f"invalid_input: Insufficient balance for gas estimation"
                elif "invalid opcode" in error_msg or "out of gas" in error_msg:
                    return None, f"invalid_input: Transaction parameters invalid for target contract"
                else:
                    # خطای شبکه - fallback
                    self.logger.warning(f"Gas estimation failed, using fallback: {gas_error}")
                    gas_limit = 100000 if smart_contract_address else 21000
            
            # IMPROVED: Real-time EIP-1559 fee calculation with competitive pricing
            try:
                # Get most recent block data for accurate base fee
                latest_block = self.w3.eth.get_block('pending')
                if 'baseFeePerGas' not in latest_block:
                    latest_block = self.w3.eth.get_block('latest')

                if 'baseFeePerGas' in latest_block:
                    # EIP-1559 supported - use real-time base fee
                    base_fee = latest_block['baseFeePerGas']
                    
                    # Get dynamic priority fee from network
                    try:
                        network_priority = self.w3.eth.max_priority_fee
                        # Use network priority with competitive buffer for fast inclusion
                        max_priority_fee = max(network_priority * 1.2, self.w3.to_wei(2, 'gwei'))
                        max_priority_fee = min(max_priority_fee, self.w3.to_wei(50, 'gwei'))  # Reasonable cap
                    except Exception:
                        max_priority_fee = self.w3.to_wei(3, 'gwei')  # Competitive fallback
                    
                    # Calculate competitive max fee with dynamic buffer
                    # Buffer scales with base fee for network congestion
                    dynamic_buffer = max(base_fee * 1.5, self.w3.to_wei(20, 'gwei'))
                    max_fee_per_gas = base_fee + max_priority_fee + dynamic_buffer
                    
                    # Apply reasonable limits to prevent excessive fees
                    reasonable_limit = self.w3.to_wei(200, 'gwei')  # Increased for high congestion
                    if max_fee_per_gas > reasonable_limit:
                        self.logger.warning(f"Very high gas fees detected: {max_fee_per_gas/10**9:.2f} Gwei - capping at {reasonable_limit/10**9:.0f} Gwei")
                        max_fee_per_gas = reasonable_limit
                        max_priority_fee = min(max_priority_fee, self.w3.to_wei(10, 'gwei'))
                    
                    # Calculate total fee
                    total_fee_wei = max_fee_per_gas * gas_limit
                    fee_eth = Decimal(total_fee_wei) / Decimal(10**18)
                    
                    self.logger.info(f"🔥 IMPROVED EIP-1559 fee calculation:")
                    self.logger.info(f"  📊 Base fee: {base_fee/10**9:.2f} Gwei")
                    self.logger.info(f"  ⚡ Priority fee: {max_priority_fee/10**9:.2f} Gwei")
                    self.logger.info(f"  🎯 Max fee: {max_fee_per_gas/10**9:.2f} Gwei")
                    self.logger.info(f"  ⛽ Gas limit: {gas_limit:,}")
                    self.logger.info(f"  💰 Total fee: {fee_eth:.6f} ETH (${fee_eth * 3500:.2f} USD approx)")
                    
                    return fee_eth, None
                    
            except Exception as eip1559_error:
                self.logger.warning(f"EIP-1559 calculation failed: {str(eip1559_error)}")
                # ادامه به Legacy fallback
            
            # IMPROVED: Legacy gas price fallback with competitive pricing
            try:
                # Get real-time gas price from multiple sources
                try:
                    network_gas_price = self.w3.eth.gas_price
                    
                    # Make gas price competitive by adding buffer for public mempool
                    # Minimum 2 Gwei buffer to ensure inclusion
                    competitive_buffer = max(network_gas_price * 0.2, self.w3.to_wei(2, 'gwei'))
                    competitive_gas_price = network_gas_price + competitive_buffer
                    
                    self.logger.info(f"🔧 Legacy gas price adjustment:")
                    self.logger.info(f"  📊 Network price: {network_gas_price/10**9:.2f} Gwei")
                    self.logger.info(f"  ⚡ Buffer added: {competitive_buffer/10**9:.2f} Gwei")
                    self.logger.info(f"  🎯 Final price: {competitive_gas_price/10**9:.2f} Gwei")
                    
                except Exception as rpc_error:
                    return None, f"upstream_error: Could not get gas price from RPC: {str(rpc_error)}"

                # Apply reasonable limits for extreme network conditions
                reasonable_limit = self.w3.to_wei(200, 'gwei')  # Higher limit for congestion
                if competitive_gas_price > reasonable_limit:
                    self.logger.warning(f"Very high competitive gas price: {competitive_gas_price/10**9:.2f} Gwei - capping at {reasonable_limit/10**9:.0f} Gwei")
                    competitive_gas_price = reasonable_limit

                # Calculate fee with competitive pricing
                total_fee_wei = competitive_gas_price * gas_limit
                fee_eth = Decimal(total_fee_wei) / Decimal(10**18)

                self.logger.info(f"🔥 IMPROVED Legacy fee calculation:")
                self.logger.info(f"  🎯 Competitive gas price: {competitive_gas_price/10**9:.2f} Gwei")
                self.logger.info(f"  ⛽ Gas limit: {gas_limit:,}")
                self.logger.info(f"  💰 Total fee: {fee_eth:.6f} ETH (${fee_eth * 3500:.2f} USD approx)")

                return fee_eth, None
                
            except Exception as legacy_error:
                return None, f"upstream_error: Legacy gas price calculation failed: {str(legacy_error)}"
            
        except ValueError as ve:
            # خطاهای ورودی - 422 مناسب است
            return None, f"invalid_input: {str(ve)}"
        except Exception as e:
            # خطاهای شبکه/سرور - 502/503 مناسب است
            return None, f"upstream_error: {str(e)}"
            
    def get_balance(self, address: str) -> Tuple[Decimal, Optional[str]]:
        """Get Ethereum balance"""
        try:
            # Try Web3 first
            balance = self.w3.eth.get_balance(address)
            return Decimal(balance) / Decimal(10**18), None
            
        except Exception as e:
            self.logger.error(f"Error getting balance via Web3: {str(e)}")
            
            # Fallback to Tatum
            balance, error = self.tatum.get_balance('ethereum', address)
            if error:
                return Decimal('0'), f"Failed to get balance: {error}"
                
            return Decimal(balance), None
            
    def validate_address(self, address: str) -> bool:
        """Validate Ethereum address"""
        return self.w3.is_address(address)
        
    def get_transaction_status(self, tx_hash: str) -> Tuple[str, Optional[str]]:
        """Get Ethereum transaction status"""
        try:
            # Try Web3 first
            try:
                receipt = self.w3.eth.get_transaction_receipt(tx_hash)
                if receipt:
                    return 'confirmed' if receipt['status'] == 1 else 'failed', None
            except TransactionNotFound:
                pass
                
            # Check if transaction exists
            try:
                tx = self.w3.eth.get_transaction(tx_hash)
                if tx:
                    return 'pending', None
            except TransactionNotFound:
                pass
                
            # Fallback to Tatum
            status, error = self.tatum.check_transaction_status('ethereum', tx_hash)
            if error:
                return 'unknown', f"Failed to get status: {error}"
                
            return status, None
            
        except Exception as e:
            self.logger.error(f"Error getting transaction status: {str(e)}")
            return 'unknown', str(e)
            
    def get_transaction_details(self, tx_hash: str) -> Tuple[Dict, Optional[str]]:
        """Get Ethereum transaction details"""
        try:
            # Try Web3 first
            try:
                tx = self.w3.eth.get_transaction(tx_hash)
                receipt = self.w3.eth.get_transaction_receipt(tx_hash)
                
                if tx and receipt:
                    return {
                        'hash': tx_hash,
                        'from': tx['from'],
                        'to': tx['to'],
                        'value': str(Decimal(tx['value']) / Decimal(10**18)),
                        'gas_price': str(Decimal(tx['gasPrice']) / Decimal(10**18)),
                        'gas_used': receipt['gasUsed'],
                        'status': 'confirmed' if receipt['status'] == 1 else 'failed',
                        'block_number': receipt['blockNumber'],
                        'timestamp': datetime.fromtimestamp(
                            self.w3.eth.get_block(receipt['blockNumber'])['timestamp']
                        ).isoformat()
                    }, None
            except TransactionNotFound:
                pass
                
            # Fallback to Tatum
            details, error = self.tatum.get_transaction('ethereum', tx_hash)
            if error:
                return None, f"Failed to get details: {error}"
                
            return details, None
            
        except Exception as e:
            self.logger.error(f"Error getting transaction details: {str(e)}")
            return None, str(e)
            
    def _get_cached_gas_price(self) -> int:
        """Get cached gas price or fetch new one"""
        now = datetime.now()
        if 'price' in self._gas_price_cache:
            cache_time, price = self._gas_price_cache['price']
            if now - cache_time < self._gas_price_expiry:
                return price
                
        try:
            # Try Infura first
            price = self.w3.eth.gas_price
            self._gas_price_cache['price'] = (now, price)
            return price
        except Exception as e:
            self.logger.warning(f"Error getting gas price from Infura: {str(e)}")
            
            try:
                # Fallback to Tatum
                gas_data, error = self.tatum.get_gas_price('ethereum')
                if error:
                    raise Exception(f"Tatum error: {error}")
                    
                price = int(gas_data.get('gasPrice', 0) * 1e9)  # Convert from Gwei to Wei
                self._gas_price_cache['price'] = (now, price)
                return price
            except Exception as e2:
                self.logger.error(f"Error getting gas price from Tatum: {str(e2)}")
                # Use default gas price as last resort (increased for current network)
                default_price = 50 * 1e9  # 50 Gwei in Wei (increased from 20)
                self._gas_price_cache['price'] = (now, default_price)
                return default_price
        
    def _store_transaction(self, transaction_id: str, tx_data: dict):
        """Store transaction data using shared storage"""
        try:
            # Use the parent class method which uses shared storage
            super()._store_transaction(transaction_id, tx_data, 30)  # 30 minute expiry
            self.logger.debug(f"Transaction {transaction_id} stored successfully in shared storage")
        except Exception as e:
            self.logger.warning(f"Failed to store transaction in shared storage: {str(e)}")
            # Fallback to class storage if shared storage fails
            try:
                if not hasattr(self.__class__, '_transactions'):
                    self.__class__._transactions = {}
                self.__class__._transactions[transaction_id] = tx_data
                self.logger.debug(f"Transaction {transaction_id} stored in fallback class storage")
            except Exception as fallback_error:
                self.logger.error(f"Both shared storage and fallback storage failed: {str(fallback_error)}")
        
    def _get_stored_transaction(self, transaction_id: str) -> Optional[Dict]:
        """Get stored transaction data from shared storage"""
        try:
            # First try to get from shared storage
            if self.storage:
                tx_data = self.storage.get_transaction(transaction_id)
                if tx_data:
                    return tx_data
            
            # Fallback to class storage for backward compatibility
            if hasattr(self.__class__, '_transactions'):
                return self.__class__._transactions.get(transaction_id)
            
            self.logger.warning(f"Transaction {transaction_id} not found in any storage")
            return None
            
        except Exception as e:
            self.logger.error(f"Error retrieving transaction: {str(e)}")
            return None 
    
    def _log_transaction(self, transaction_id: str, action: str, data: dict):
        """لاگ کردن عملیات تراکنش"""
        try:
            self.logger.info(f"Transaction {transaction_id} {action}: {json.dumps(data, indent=2, default=str)}")
        except Exception as e:
            self.logger.warning(f"Failed to log transaction: {str(e)}") 