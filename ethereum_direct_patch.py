#!/usr/bin/env python3
# Patch برای اضافه کردن روش مستقیم به ethereum_service.py


    def send_transaction_direct_fallback(self, transaction_id: str, private_key: str):
        """
        روش پشتیبان: ارسال مستقیم بدون Tatum
        Fallback method: Direct sending without Tatum
        """
        try:
            # Get transaction data
            tx_data = self._get_transaction(transaction_id)
            if not tx_data:
                return {}, f"Transaction {transaction_id} not found"
            
            sender = tx_data['details']['sender']
            recipient = tx_data['details']['recipient']
            amount_str = tx_data['details']['amount']
            amount = Decimal(amount_str)
            
            self.logger.info(f"🔄 Method 4: Direct Web3 without Tatum")
            
            # اتصال مستقیم به چندین RPC
            rpc_endpoints = [
                "https://eth.llamarpc.com",
                "https://ethereum.publicnode.com",
                "https://rpc.ankr.com/eth"
            ]
            
            for rpc_url in rpc_endpoints:
                try:
                    # ایجاد اتصال جدید
                    direct_w3 = Web3(Web3.HTTPProvider(rpc_url, request_kwargs={'timeout': 15}))
                    
                    if not direct_w3.is_connected():
                        continue
                    
                    # دریافت اطلاعات شبکه
                    nonce = direct_w3.eth.get_transaction_count(sender)
                    gas_price = direct_w3.eth.gas_price
                    
                    # کاهش gas price اگر خیلی زیاد باشد
                    max_gas_price = 50 * 10**9  # 50 Gwei
                    if gas_price > max_gas_price:
                        gas_price = max_gas_price
                        self.logger.warning(f"Gas price reduced to {gas_price/10**9:.2f} Gwei")
                    
                    # آماده‌سازی تراکنش
                    transaction = {
                        'from': sender,
                        'to': recipient,
                        'value': direct_w3.to_wei(amount, 'ether'),
                        'gas': 21000,
                        'gasPrice': gas_price,
                        'nonce': nonce,
                        'chainId': 1
                    }
                    
                    # امضا
                    signed_txn = direct_w3.eth.account.sign_transaction(transaction, private_key)
                    
                    # ارسال
                    tx_hash = direct_w3.eth.send_raw_transaction(signed_txn.rawTransaction)
                    tx_hash_hex = tx_hash.hex()
                    
                    self.logger.info(f"✅ SUCCESS: Direct Web3 transaction sent: {tx_hash_hex}")
                    
                    # Update transaction data
                    tx_data.update({
                        'tx_hash': tx_hash_hex,
                        'status': 'sent',
                        'sent_at': datetime.now().isoformat(),
                        'sent_via': 'direct_web3_fallback',
                        'method_used': 4,
                        'rpc_used': rpc_url
                    })
                    self._store_transaction(transaction_id, tx_data)
                    
                    return {
                        'transaction_id': transaction_id,
                        'tx_hash': tx_hash_hex,
                        'status': 'sent',
                        'method': 'direct_web3_fallback'
                    }, None
                    
                except Exception as rpc_error:
                    self.logger.warning(f"RPC {rpc_url} failed: {str(rpc_error)}")
                    continue
            
            return {}, "All direct RPC methods failed"
            
        except Exception as e:
            self.logger.error(f"Direct fallback method failed: {str(e)}")
            return {}, str(e)
    
