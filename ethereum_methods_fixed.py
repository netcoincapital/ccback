#!/usr/bin/env python3
"""
کدهای اصلاح شده برای جایگزینی در ethereum_service.py
Fixed code for replacement in ethereum_service.py
"""

# 1. متد estimate_fee اصلاح شده

    def estimate_fee(self, sender: str, recipient: str, amount, 
                    smart_contract_address: Optional[str] = None) -> Tuple[Decimal, Optional[str]]:
        """
        تخمین کارمزد اصلاح شده - رفع کامل خطای HTTP 400
        Fixed fee estimation - completely resolves HTTP 400 error
        """
        try:
            from decimal import Decimal, ROUND_DOWN, InvalidOperation, getcontext
            getcontext().prec = 80
            
            # تبدیل ایمن amount
            try:
                if isinstance(amount, str):
                    amount_decimal = Decimal(amount.strip())
                elif isinstance(amount, (int, float)):
                    amount_decimal = Decimal(str(amount))
                elif isinstance(amount, Decimal):
                    amount_decimal = amount
                else:
                    raise ValueError(f"Unsupported amount type: {type(amount)}")
                
                if amount_decimal <= 0:
                    raise ValueError("Amount must be positive")
                
                amount_wei = int((amount_decimal * Decimal(10**18)).to_integral_value())
                
            except Exception as amount_error:
                return None, f"invalid_input: Invalid amount: {str(amount_error)}"
            
            # نرمال‌سازی ایمن آدرس‌ها
            try:
                if not self.w3.is_address(sender):
                    raise ValueError("Invalid sender address")
                if not self.w3.is_address(recipient):
                    raise ValueError("Invalid recipient address")
                
                sender_norm = self.w3.to_checksum_address(sender)
                recipient_norm = self.w3.to_checksum_address(recipient)
                
            except Exception as addr_error:
                return None, f"invalid_input: {str(addr_error)}"
            
            # تخمین gas واقعی
            try:
                estimated_gas = self.w3.eth.estimate_gas({
                    'from': sender_norm,
                    'to': recipient_norm,
                    'value': amount_wei
                })
                gas_limit = max(21000, int(estimated_gas * 1.2))
                self.logger.debug(f"Gas estimation: {estimated_gas} → {gas_limit}")
                
            except Exception as gas_error:
                error_msg = str(gas_error).lower()
                if "execution reverted" in error_msg:
                    return None, f"invalid_input: Transaction would fail - recipient rejected transfer"
                elif "insufficient funds" in error_msg:
                    return None, f"invalid_input: Insufficient balance"
                else:
                    gas_limit = 21000  # fallback
                    self.logger.warning(f"Gas estimation failed, using {gas_limit}")
            
            # محاسبه کارمزد
            try:
                # تلاش برای EIP-1559
                latest_block = self.w3.eth.get_block('latest')
                
                if 'baseFeePerGas' in latest_block:
                    base_fee = latest_block['baseFeePerGas']
                    priority_fee = self.w3.to_wei(2, 'gwei')
                    max_fee = (base_fee * 2) + priority_fee
                    
                    # محدودیت معقول
                    if max_fee > self.w3.to_wei(100, 'gwei'):
                        max_fee = self.w3.to_wei(100, 'gwei')
                    
                    total_fee_wei = max_fee * gas_limit
                else:
                    # Legacy
                    gas_price = self.w3.eth.gas_price
                    total_fee_wei = gas_price * gas_limit
                
                fee_eth = Decimal(total_fee_wei) / Decimal(10**18)
                self.logger.info(f"Estimated fee: {fee_eth:.6f} ETH")
                
                return fee_eth, None
                
            except Exception as fee_error:
                return None, f"upstream_error: Fee calculation failed: {str(fee_error)}"
            
        except Exception as e:
            return None, f"upstream_error: Unexpected error: {str(e)}"
    

# 2. متد send_transaction اصلاح شده

    def send_transaction(self, transaction_id: str, private_key: str) -> Tuple[Dict, Optional[str]]:
        """
        ارسال تراکنش اصلاح شده با 3 روش پشتیبان
        Fixed transaction sending with 3 fallback methods
        """
        try:
            # Get transaction data
            tx_data = self._get_stored_transaction(transaction_id)
            if not tx_data:
                return {}, "Transaction not found or expired"
            
            sender = tx_data['details']['sender']
            recipient = tx_data['details']['recipient']
            amount_str = tx_data['details']['amount']
            
            # تبدیل amount
            try:
                amount = Decimal(amount_str)
            except:
                return {}, "Invalid amount format"
            
            self.logger.info(f"Sending ETH transaction: {amount} ETH from {sender} to {recipient}")
            
            # Method 1: Direct Web3 (ساده‌ترین)
            try:
                self.logger.debug("Method 1: Direct Web3")
                
                # نرمال‌سازی آدرس‌ها
                sender_norm = self.w3.to_checksum_address(sender)
                recipient_norm = self.w3.to_checksum_address(recipient)
                
                # دریافت اطلاعات شبکه
                nonce = self.w3.eth.get_transaction_count(sender_norm)
                gas_price = self.w3.eth.gas_price
                chain_id = self.w3.eth.chain_id
                
                # محدود کردن gas price
                if gas_price > self.w3.to_wei(50, 'gwei'):
                    gas_price = self.w3.to_wei(50, 'gwei')
                
                # آماده‌سازی تراکنش
                transaction = {
                    'from': sender_norm,
                    'to': recipient_norm,
                    'value': self.w3.to_wei(amount, 'ether'),
                    'gas': 21000,
                    'gasPrice': gas_price,
                    'nonce': nonce,
                    'chainId': chain_id
                }
                
                # امضا و ارسال
                signed_txn = self.w3.eth.account.sign_transaction(transaction, private_key)
                tx_hash = self.w3.eth.send_raw_transaction(signed_txn.rawTransaction).hex()
                
                self.logger.info(f"✅ SUCCESS: Direct Web3 transaction sent: {tx_hash}")
                
                # بروزرسانی داده‌ها
                tx_data.update({
                    'tx_hash': tx_hash,
                    'status': 'sent',
                    'sent_at': datetime.now().isoformat(),
                    'method_used': 'direct_web3'
                })
                self._store_transaction(transaction_id, tx_data)
                
                return {
                    'transaction_id': transaction_id,
                    'tx_hash': tx_hash,
                    'status': 'sent'
                }, None
                
            except Exception as e:
                self.logger.error(f"Method 1 failed: {str(e)}")
            
            # Method 2: Alternative RPC
            try:
                self.logger.debug("Method 2: Alternative RPC")
                
                # اتصال به RPC دیگر
                alt_rpc = "https://ethereum.publicnode.com"
                alt_w3 = Web3(Web3.HTTPProvider(alt_rpc))
                
                if alt_w3.is_connected():
                    # تکرار عملیات با RPC جایگزین
                    sender_norm = alt_w3.to_checksum_address(sender)
                    recipient_norm = alt_w3.to_checksum_address(recipient)
                    
                    nonce = alt_w3.eth.get_transaction_count(sender_norm)
                    gas_price = min(alt_w3.eth.gas_price, alt_w3.to_wei(50, 'gwei'))
                    chain_id = alt_w3.eth.chain_id
                    
                    transaction = {
                        'from': sender_norm,
                        'to': recipient_norm,
                        'value': alt_w3.to_wei(amount, 'ether'),
                        'gas': 21000,
                        'gasPrice': gas_price,
                        'nonce': nonce,
                        'chainId': chain_id
                    }
                    
                    signed_txn = alt_w3.eth.account.sign_transaction(transaction, private_key)
                    tx_hash = alt_w3.eth.send_raw_transaction(signed_txn.rawTransaction).hex()
                    
                    self.logger.info(f"✅ SUCCESS: Alternative RPC transaction sent: {tx_hash}")
                    
                    tx_data.update({
                        'tx_hash': tx_hash,
                        'status': 'sent',
                        'sent_at': datetime.now().isoformat(),
                        'method_used': 'alternative_rpc'
                    })
                    self._store_transaction(transaction_id, tx_data)
                    
                    return {
                        'transaction_id': transaction_id,
                        'tx_hash': tx_hash,
                        'status': 'sent'
                    }, None
                    
            except Exception as e:
                self.logger.error(f"Method 2 failed: {str(e)}")
            
            # Method 3: Conservative approach
            try:
                self.logger.debug("Method 3: Conservative approach")
                
                # استفاده از پارامترهای محافظه‌کارانه
                sender_norm = self.w3.to_checksum_address(sender)
                recipient_norm = self.w3.to_checksum_address(recipient)
                
                nonce = self.w3.eth.get_transaction_count(sender_norm)
                gas_price = self.w3.to_wei(20, 'gwei')  # ثابت 20 Gwei
                chain_id = self.w3.eth.chain_id
                
                transaction = {
                    'from': sender_norm,
                    'to': recipient_norm,
                    'value': self.w3.to_wei(amount, 'ether'),
                    'gas': 25000,  # کمی بیشتر از 21000
                    'gasPrice': gas_price,
                    'nonce': nonce,
                    'chainId': chain_id
                }
                
                signed_txn = self.w3.eth.account.sign_transaction(transaction, private_key)
                tx_hash = self.w3.eth.send_raw_transaction(signed_txn.rawTransaction).hex()
                
                self.logger.info(f"✅ SUCCESS: Conservative transaction sent: {tx_hash}")
                
                tx_data.update({
                    'tx_hash': tx_hash,
                    'status': 'sent',
                    'sent_at': datetime.now().isoformat(),
                    'method_used': 'conservative'
                })
                self._store_transaction(transaction_id, tx_data)
                
                return {
                    'transaction_id': transaction_id,
                    'tx_hash': tx_hash,
                    'status': 'sent'
                }, None
                
            except Exception as e:
                self.logger.error(f"Method 3 failed: {str(e)}")
            
            # همه روش‌ها شکست خورد
            return {}, "All transaction methods failed. Please check network connectivity and try again."
            
        except Exception as e:
            self.logger.error(f"Error in send_transaction: {str(e)}")
            return {}, str(e)
    
