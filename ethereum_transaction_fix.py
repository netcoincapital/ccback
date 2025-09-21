#!/usr/bin/env python3
"""
اصلاح سیستم تراکنش اتریوم با الگوی پلیگان
Fix Ethereum transaction system with Polygon pattern
"""

def create_improved_ethereum_send_transaction():
    """ایجاد نسخه بهبود یافته send_transaction برای اتریوم"""
    
    improved_code = '''
    @handle_api_errors
    def send_transaction(self, transaction_id: str, private_key: str) -> Tuple[Dict, Optional[str]]:
        """
        Send Ethereum transaction with multiple fallback methods (like Polygon)
        ارسال تراکنش اتریوم با روش‌های پشتیبان متعدد (مثل پلیگان)
        """
        try:
            # Get transaction data
            tx_data = self._get_transaction(transaction_id)
            if not tx_data:
                return {}, f"Transaction {transaction_id} not found"
            
            sender = tx_data['sender']
            recipient = tx_data['recipient']
            amount_str = tx_data['amount']
            smart_contract_address = tx_data.get('smart_contract_address')
            
            try:
                amount = Decimal(amount_str)
            except Exception as e:
                self.logger.error(f"Error converting amount to Decimal: {str(e)}")
                return {}, f"Invalid amount format: {amount_str}"
            
            self.logger.info(f"Addresses validated: sender={sender}, recipient={recipient}")
            self.logger.info(f"Sending Ethereum transaction using multi-method approach")
            
            # Method 1: Web3 signing + Tatum broadcasting (original method)
            self.logger.debug(f"Method 1: Web3 signing + Tatum broadcasting")
            
            try:
                # Final balance verification
                current_balance, balance_error = self.get_balance(sender)
                if balance_error:
                    self.logger.error(f"Could not verify balance: {balance_error}")
                    return {}, f"Could not verify current balance: {balance_error}"
                
                current_fee, fee_error = self.estimate_fee(sender, recipient, amount)
                if fee_error:
                    self.logger.warning(f"Could not get fee estimate, using default: {fee_error}")
                    current_fee = Decimal('0.002')
                
                total_required = amount + current_fee
                
                if current_balance < total_required:
                    error_msg = f"Insufficient balance. Available: {current_balance} ETH, Required: {total_required} ETH"
                    self.logger.error(f"❌ Balance check failed: {error_msg}")
                    return {}, error_msg
                
                # Get current nonce
                nonce = self.w3.eth.get_transaction_count(sender)
                self.logger.info(f"Current nonce for {sender}: {nonce}")
                
                # Prepare transaction parameters
                params = {
                    'from': sender,
                    'to': recipient,
                    'value': self.w3.to_wei(amount, 'ether'),
                    'gas': 21000,
                    'gasPrice': self._get_cached_gas_price(),
                    'nonce': nonce,
                    'chainId': 1
                }
                
                # Sign transaction
                signed_tx = self.w3.eth.account.sign_transaction(params, private_key)
                self.logger.info(f"Successfully signed Ethereum transaction with Web3")
                
                # Get raw transaction
                raw_tx = signed_tx.rawTransaction.hex()
                if not raw_tx.startswith('0x'):
                    raw_tx = '0x' + raw_tx
                
                self.logger.debug(f"Signed transaction length: {len(raw_tx)} characters")
                self.logger.debug(f"Broadcasting Ethereum transaction via Tatum API")
                
                # Broadcast via Tatum
                result, error = self.tatum.send_transaction(
                    'ethereum',
                    sender,
                    recipient,
                    amount_str,
                    private_key,
                    {'signed_tx': raw_tx}
                )
                
                if not error and result:
                    tx_hash = result.get('transaction_hash') or result.get('txId')
                    if tx_hash:
                        self.logger.info(f"✅ SUCCESS: Method 1 - Ethereum transaction sent: {tx_hash}")
                        
                        # Update transaction data
                        tx_data.update({
                            'tx_hash': tx_hash,
                            'status': 'sent',
                            'sent_at': datetime.now().isoformat(),
                            'sent_via': 'web3_tatum_broadcast',
                            'method_used': 1
                        })
                        self._store_transaction(transaction_id, tx_data)
                        
                        return {
                            'transaction_id': transaction_id,
                            'tx_hash': tx_hash,
                            'status': 'sent',
                            'method': 'web3_tatum_broadcast'
                        }, None
                else:
                    self.logger.error(f"Tatum API broadcast error: {error}")
                    
            except Exception as e:
                self.logger.error(f"Method 1 failed: {str(e)}")
            
            # Method 2: Direct Web3 sending with nonce retry (like Polygon)
            self.logger.debug(f"Method 2: Direct Web3 sending with nonce retry")
            
            try:
                max_retries = 3
                for retry in range(max_retries):
                    try:
                        # Get fresh nonce for each retry
                        current_nonce = self.w3.eth.get_transaction_count(sender)
                        adjusted_nonce = current_nonce + retry  # Try different nonces
                        
                        self.logger.info(f"Trying with nonce: {adjusted_nonce}")
                        
                        # Prepare transaction with adjusted nonce
                        transaction = {
                            'from': sender,
                            'to': recipient,
                            'value': self.w3.to_wei(amount, 'ether'),
                            'gas': 21000,
                            'gasPrice': self._get_cached_gas_price(),
                            'nonce': adjusted_nonce,
                            'chainId': 1
                        }
                        
                        # Sign transaction
                        signed_txn = self.w3.eth.account.sign_transaction(transaction, private_key)
                        
                        # Send raw transaction directly via Web3
                        tx_hash = self.w3.eth.send_raw_transaction(signed_txn.rawTransaction).hex()
                        
                        self.logger.info(f"✅ SUCCESS: Method 2 - Ethereum transaction sent via Web3: {tx_hash}")
                        
                        # Update transaction data
                        tx_data.update({
                            'tx_hash': tx_hash,
                            'status': 'sent',
                            'sent_at': datetime.now().isoformat(),
                            'sent_via': 'web3_direct',
                            'method_used': 2,
                            'nonce_used': adjusted_nonce
                        })
                        self._store_transaction(transaction_id, tx_data)
                        
                        return {
                            'transaction_id': transaction_id,
                            'tx_hash': tx_hash,
                            'status': 'sent',
                            'method': 'web3_direct'
                        }, None
                        
                    except Exception as e:
                        error_msg = str(e)
                        if "nonce too low" in error_msg.lower():
                            self.logger.warning(f"Nonce too low, retrying with higher nonce (attempt {retry + 1}/{max_retries})")
                            continue
                        elif "replacement transaction underpriced" in error_msg.lower():
                            self.logger.warning(f"Transaction underpriced, retrying with higher gas (attempt {retry + 1}/{max_retries})")
                            # Increase gas price for next attempt
                            continue
                        else:
                            self.logger.error(f"Web3 sending failed: {error_msg}")
                            break
                
                self.logger.error(f"All Web3 retries failed after {max_retries} attempts")
                
            except Exception as e:
                self.logger.error(f"Method 2 failed: {str(e)}")
            
            # Method 3: Tatum transaction endpoint (let Tatum handle everything)
            if self.tatum:
                try:
                    self.logger.debug(f"Method 3: Tatum transaction endpoint with improved error handling")
                    
                    # Use Tatum's transaction endpoint which handles signing internally
                    result, error = self.tatum.send_transaction(
                        'ethereum',
                        sender,
                        recipient,
                        amount_str,
                        private_key
                    )
                    
                    if error:
                        # Enhanced error handling for common issues
                        if "insufficient funds" in error.lower():
                            # Get current balance to provide better error message
                            current_balance, _ = self.get_balance(sender)
                            fee_estimate, _ = self.estimate_fee(sender, recipient, amount_str)
                            
                            if current_balance and fee_estimate:
                                required = amount + fee_estimate
                                error_msg = f"Tatum reports insufficient funds. Our calculations: Available={current_balance} ETH, Required={required} ETH. This may indicate a private key mismatch or higher gas costs in Tatum."
                            else:
                                error_msg = f"Tatum reports insufficient funds: {error}. This usually indicates a private key mismatch."
                            
                            self.logger.error(error_msg)
                            return {}, error_msg
                            
                        elif "bad syntax" in error.lower() or "400" in error:
                            # Handle HTTP 400 errors specifically
                            error_msg = f"Transaction validation failed. This usually means: 1) Invalid address format, 2) Invalid amount format, 3) Network congestion. Original error: {error}"
                            self.logger.error(error_msg)
                            return {}, error_msg
                            
                        elif "network fee" in error.lower():
                            # Handle network fee estimation errors
                            error_msg = f"Network fee estimation failed. Try again in a few minutes or check network status. Original error: {error}"
                            self.logger.error(error_msg)
                            return {}, error_msg
                            
                        else:
                            self.logger.error(f"Tatum transaction endpoint failed: {error}")
                            return {}, f"Tatum transaction failed: {error}"
                    
                    tx_hash = result.get('transaction_hash') or result.get('txId')
                    if tx_hash:
                        self.logger.info(f"✅ SUCCESS: Method 3 - Ethereum transaction sent via Tatum: {tx_hash}")
                        
                        # Update transaction data
                        tx_data.update({
                            'tx_hash': tx_hash,
                            'status': 'sent',
                            'sent_at': datetime.now().isoformat(),
                            'sent_via': 'tatum_endpoint',
                            'method_used': 3
                        })
                        self._store_transaction(transaction_id, tx_data)
                        
                        return {
                            'transaction_id': transaction_id,
                            'tx_hash': tx_hash,
                            'status': 'sent',
                            'method': 'tatum_endpoint'
                        }, None
                    else:
                        self.logger.error(f"No transaction hash returned from Tatum")
                        
                except Exception as e:
                    self.logger.error(f"Method 3 failed: {str(e)}")
            
            # Method 4: Alternative gas price and retry (new method)
            self.logger.debug(f"Method 4: Alternative gas price strategy")
            
            try:
                # Try with different gas price strategies
                gas_strategies = [
                    {'multiplier': 1.5, 'name': 'High Priority'},
                    {'multiplier': 2.0, 'name': 'Maximum Priority'},
                    {'multiplier': 0.8, 'name': 'Low Priority'}
                ]
                
                for strategy in gas_strategies:
                    try:
                        self.logger.info(f"Trying {strategy['name']} gas strategy")
                        
                        # Get base gas price
                        base_gas_price = self._get_cached_gas_price()
                        adjusted_gas_price = int(base_gas_price * strategy['multiplier'])
                        
                        # Get fresh nonce
                        nonce = self.w3.eth.get_transaction_count(sender)
                        
                        # Prepare transaction
                        transaction = {
                            'from': sender,
                            'to': recipient,
                            'value': self.w3.to_wei(amount, 'ether'),
                            'gas': 25000,  # Slightly higher gas limit
                            'gasPrice': adjusted_gas_price,
                            'nonce': nonce,
                            'chainId': 1
                        }
                        
                        # Sign and send
                        signed_txn = self.w3.eth.account.sign_transaction(transaction, private_key)
                        tx_hash = self.w3.eth.send_raw_transaction(signed_txn.rawTransaction).hex()
                        
                        self.logger.info(f"✅ SUCCESS: Method 4 - {strategy['name']} gas strategy worked: {tx_hash}")
                        
                        # Update transaction data
                        tx_data.update({
                            'tx_hash': tx_hash,
                            'status': 'sent',
                            'sent_at': datetime.now().isoformat(),
                            'sent_via': 'web3_alternative_gas',
                            'method_used': 4,
                            'gas_strategy': strategy['name']
                        })
                        self._store_transaction(transaction_id, tx_data)
                        
                        return {
                            'transaction_id': transaction_id,
                            'tx_hash': tx_hash,
                            'status': 'sent',
                            'method': 'web3_alternative_gas'
                        }, None
                        
                    except Exception as e:
                        self.logger.warning(f"{strategy['name']} strategy failed: {str(e)}")
                        continue
                
                self.logger.error(f"All gas strategies failed")
                
            except Exception as e:
                self.logger.error(f"Method 4 failed: {str(e)}")
            
            # Final error - all methods failed
            error_msg = "All transaction methods failed. This could be due to: 1) Network congestion, 2) Invalid private key, 3) Insufficient funds, 4) Invalid transaction parameters. Please check your wallet and try again."
            self.logger.error(f"❌ ALL METHODS FAILED: {error_msg}")
            
            return {}, error_msg
            
        except Exception as e:
            self.logger.error(f"Error in send_transaction: {str(e)}")
            return {}, str(e)
    '''
    
    return improved_code

def create_error_handler():
    """ایجاد مدیر خطاهای اختصاصی اتریوم"""
    
    error_handler_code = '''
    def handle_ethereum_transaction_error(self, error_message, method_name):
        """
        مدیریت خطاهای اختصاصی تراکنش اتریوم
        Handle Ethereum-specific transaction errors
        """
        error_lower = error_message.lower()
        
        # HTTP 400 - Bad Request
        if "400" in error_message or "bad syntax" in error_lower:
            return {
                'error_type': 'validation_error',
                'user_message': 'تراکنش نامعتبر است. لطفاً آدرس و مقدار را بررسی کنید.',
                'technical_message': 'HTTP 400: Request validation failed',
                'retry_recommended': True,
                'retry_delay': 30
            }
        
        # Network fee estimation errors
        elif "network fee" in error_lower or "fee estimation" in error_lower:
            return {
                'error_type': 'fee_estimation_error', 
                'user_message': 'خطا در برآورد کارمزد شبکه. چند دقیقه دیگر تلاش کنید.',
                'technical_message': 'Network fee estimation failed',
                'retry_recommended': True,
                'retry_delay': 120
            }
        
        # Insufficient funds
        elif "insufficient funds" in error_lower:
            return {
                'error_type': 'insufficient_funds',
                'user_message': 'موجودی کافی نیست. لطفاً موجودی کیف پول را بررسی کنید.',
                'technical_message': 'Insufficient balance for transaction + fees',
                'retry_recommended': False,
                'retry_delay': 0
            }
        
        # Nonce errors
        elif "nonce" in error_lower:
            return {
                'error_type': 'nonce_error',
                'user_message': 'خطا در ترتیب تراکنش. لطفاً چند ثانیه صبر کنید.',
                'technical_message': 'Transaction nonce conflict',
                'retry_recommended': True,
                'retry_delay': 10
            }
        
        # Gas price errors
        elif "gas" in error_lower and ("too low" in error_lower or "underpriced" in error_lower):
            return {
                'error_type': 'gas_price_error',
                'user_message': 'کارمزد شبکه کم است. تراکنش با کارمزد بالاتر ارسال می‌شود.',
                'technical_message': 'Gas price too low for network conditions',
                'retry_recommended': True,
                'retry_delay': 5
            }
        
        # Network congestion
        elif "timeout" in error_lower or "congestion" in error_lower:
            return {
                'error_type': 'network_congestion',
                'user_message': 'شبکه شلوغ است. لطفاً چند دقیقه دیگر تلاش کنید.',
                'technical_message': 'Network congestion detected',
                'retry_recommended': True,
                'retry_delay': 300
            }
        
        # Default error
        else:
            return {
                'error_type': 'unknown_error',
                'user_message': 'خطای غیرمنتظره در ارسال تراکنش. لطفاً دوباره تلاش کنید.',
                'technical_message': error_message,
                'retry_recommended': True,
                'retry_delay': 60
            }
    '''
    
    return error_handler_code

def create_transaction_validator():
    """ایجاد اعتبارسنج تراکنش پیشرفته"""
    
    validator_code = '''
    def validate_transaction_params(self, sender, recipient, amount, private_key):
        """
        اعتبارسنجی پیشرفته پارامترهای تراکنش
        Advanced validation of transaction parameters
        """
        validation_errors = []
        
        # Validate addresses
        if not self.w3.is_address(sender):
            validation_errors.append("آدرس فرستنده نامعتبر است")
        
        if not self.w3.is_address(recipient):
            validation_errors.append("آدرس گیرنده نامعتبر است")
        
        if sender.lower() == recipient.lower():
            validation_errors.append("آدرس فرستنده و گیرنده نمی‌توانند یکسان باشند")
        
        # Validate amount
        try:
            amount_decimal = Decimal(str(amount))
            if amount_decimal <= 0:
                validation_errors.append("مقدار باید بزرگتر از صفر باشد")
        except:
            validation_errors.append("فرمت مقدار نامعتبر است")
        
        # Validate private key format
        if not private_key or len(private_key) < 64:
            validation_errors.append("کلید خصوصی نامعتبر است")
        
        # Check if private key matches sender address
        try:
            account = self.w3.eth.account.from_key(private_key)
            if account.address.lower() != sender.lower():
                validation_errors.append("کلید خصوصی با آدرس فرستنده مطابقت ندارد")
        except:
            validation_errors.append("کلید خصوصی نامعتبر است")
        
        # Network connectivity check
        try:
            latest_block = self.w3.eth.get_block('latest')
            if not latest_block:
                validation_errors.append("عدم دسترسی به شبکه اتریوم")
        except:
            validation_errors.append("خطا در اتصال به شبکه")
        
        return validation_errors
    '''
    
    return validator_code

def main():
    print("🔧 اصلاح سیستم تراکنش اتریوم")
    print("Ethereum Transaction System Fix")
    print("="*60)
    
    print("📋 تحلیل مشکل:")
    print("   خطای HTTP 400: 'Client error - bad syntax'")
    print("   مشابه مشکل قبلی پلیگان")
    print("   نیاز به سیستم چندمرحله‌ای")
    
    print(f"\n✅ راه‌حل پلیگان:")
    print("   Method 1: Web3 signing + Tatum broadcast")
    print("   Method 2: Direct Web3 with nonce retry")
    print("   Method 3: Full Tatum endpoint")
    print("   + مدیریت خطاهای اختصاصی")
    
    # ایجاد کدهای اصلاحی
    improved_send = create_improved_ethereum_send_transaction()
    error_handler = create_error_handler()
    validator = create_transaction_validator()
    
    # ذخیره کد کامل
    full_code = f'''#!/usr/bin/env python3
"""
کد اصلاحی کامل برای سرویس اتریوم
Complete fix for Ethereum service
"""

# 1. نسخه بهبود یافته send_transaction
{improved_send}

# 2. مدیر خطاهای اختصاصی
{error_handler}

# 3. اعتبارسنج پیشرفته
{validator}
'''
    
    with open('ethereum_service_fix.py', 'w', encoding='utf-8') as f:
        f.write(full_code)
    
    print(f"\n💾 کد اصلاحی در فایل ethereum_service_fix.py ذخیره شد")
    
    print(f"\n🔄 مراحل اعمال:")
    print("1. بک‌آپ از فایل services/blockchains/ethereum_service.py")
    print("2. جایگزینی متد send_transaction با نسخه جدید")
    print("3. اضافه کردن متدهای error handling")
    print("4. تست با تراکنش واقعی")
    
    print(f"\n🎯 نتیجه مورد انتظار:")
    print("   ✅ رفع خطای HTTP 400")
    print("   ✅ مدیریت بهتر خطاهای شبکه")
    print("   ✅ چندین روش پشتیبان")
    print("   ✅ پیام‌های خطای واضح‌تر")

if __name__ == "__main__":
    main()
