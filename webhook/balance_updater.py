import logging
import json
from datetime import datetime
from decimal import Decimal
from sqlalchemy.exc import SQLAlchemyError
import os

from models.wallet_balance import WalletBalance
from models.balance_update_log import BalanceUpdateLog
from utils.logging_config import get_log_directory


class BalanceUpdater:
    """
    Class responsible for updating wallet balances based on transaction information
    """
    
    def __init__(self, config, db_operations):
        """
        Initialize the BalanceUpdater
        
        Args:
            config (dict): Application configuration
            db_operations: Database operations helper
        """
        self.config = config
        self.db_operations = db_operations
        
        # Setup dedicated logger for balance updater
        self.logger = logging.getLogger('webhook.balance_updater')
        
        # Remove existing handlers to avoid duplicates
        if self.logger.handlers:
            self.logger.handlers = []
            
        # Set logging level
        self.logger.setLevel(logging.INFO)
        self.logger.propagate = False
        
        # Create formatter
        formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
        
        # Add console handler
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        self.logger.addHandler(console_handler)
        
        # Add file handler
        log_dir = get_log_directory()
        log_file = os.path.join(log_dir, "webhook_balance_updater.log")
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(formatter)
        self.logger.addHandler(file_handler)
        
        self.logger.info("🚀 BalanceUpdater initialized")
    
    def update_wallet_balance(self, wallet_id, blockchain, token_symbol, amount, direction, tx_id, contract_address=None):
        """
        Update a wallet's balance based on transaction information
        
        Args:
            wallet_id (str): ID of the wallet to update
            blockchain (str): Blockchain name (e.g., 'ETH', 'BTC')
            token_symbol (str): Symbol of the token (e.g., 'ETH', 'USDT')
            amount (str): Amount of tokens to add/subtract
            direction (str): 'inbound' for deposits, 'outbound' for withdrawals
            tx_id (str): Transaction ID
            contract_address (str, optional): Contract address for tokens
            
        Returns:
            dict: Result of the balance update operation
        """
        try:
            self.logger.info(f"💰 Updating balance for wallet {wallet_id}, {direction} {amount} {token_symbol}")
            
            # Convert amount to Decimal
            try:
                decimal_amount = Decimal(amount)
            except Exception as e:
                self.logger.error(f"⛔ Invalid amount format: {amount}. Error: {str(e)}")
                return {
                    'success': False,
                    'message': f'Invalid amount format: {amount}',
                    'wallet_id': wallet_id,
                    'asset': token_symbol
                }
            
            # Determine the sign based on direction
            if direction.lower() == 'inbound':
                # For deposits, add to balance
                sign = 1
            elif direction.lower() == 'outbound':
                # For withdrawals, subtract from balance
                sign = -1
            else:
                self.logger.error(f"⛔ Invalid direction: {direction}. Must be 'inbound' or 'outbound'")
                return {
                    'success': False,
                    'message': f'Invalid direction: {direction}. Must be inbound or outbound',
                    'wallet_id': wallet_id,
                    'asset': token_symbol
                }
            
            # Create session and update balance
            with self.db_operations.session_factory() as session:
                # Find or create wallet balance record
                wallet_balance = self._get_or_create_wallet_balance(
                    session=session,
                    wallet_id=wallet_id,
                    blockchain=blockchain,
                    token_symbol=token_symbol,
                    contract_address=contract_address
                )
                
                if not wallet_balance:
                    self.logger.error(f"⛔ Failed to get or create wallet balance record")
                    return {
                        'success': False,
                        'message': 'Failed to get or create wallet balance record',
                        'wallet_id': wallet_id,
                        'asset': token_symbol
                    }
                
                # Calculate new balance
                old_balance = Decimal(wallet_balance.balance)
                change_amount = sign * decimal_amount
                new_balance = old_balance + change_amount
                
                # Check if withdrawal would result in negative balance
                if new_balance < 0 and direction.lower() == 'outbound':
                    self.logger.warning(f"⚠️ Insufficient balance. Available: {old_balance}, Requested: {decimal_amount}")
                    
                    # Based on config, either allow negative balances or not
                    if not self.config.get('ALLOW_NEGATIVE_BALANCES', False):
                        return {
                            'success': False,
                            'message': f'Insufficient balance. Available: {old_balance}, Requested: {decimal_amount}',
                            'wallet_id': wallet_id,
                            'asset': token_symbol,
                            'current_balance': str(old_balance)
                        }
                
                # Update the balance
                wallet_balance.balance = str(new_balance)
                wallet_balance.updated_at = datetime.now()
                
                # Create balance update log
                balance_log = BalanceUpdateLog(
                    wallet_id=wallet_id,
                    blockchain=blockchain,
                    token_symbol=token_symbol,
                    contract_address=contract_address,
                    old_balance=str(old_balance),
                    new_balance=str(new_balance),
                    change_amount=str(change_amount),
                    direction=direction,
                    tx_id=tx_id,
                    created_at=datetime.now()
                )
                
                # Save changes
                session.add(wallet_balance)
                session.add(balance_log)
                session.commit()
                
                self.logger.info(f"✅ Balance updated for wallet {wallet_id}. New balance: {new_balance} {token_symbol}")
                
                return {
                    'success': True,
                    'message': 'Balance updated successfully',
                    'wallet_id': wallet_id,
                    'asset': token_symbol,
                    'old_balance': str(old_balance),
                    'new_balance': str(new_balance),
                    'change': str(change_amount)
                }
                
        except SQLAlchemyError as e:
            self.logger.error(f"⛔ Database error updating balance: {str(e)}", exc_info=True)
            return {
                'success': False,
                'message': f'Database error: {str(e)}',
                'wallet_id': wallet_id,
                'asset': token_symbol
            }
        except Exception as e:
            self.logger.error(f"⛔ Error updating balance: {str(e)}", exc_info=True)
            return {
                'success': False,
                'message': f'Error: {str(e)}',
                'wallet_id': wallet_id,
                'asset': token_symbol
            }
    
    def _get_or_create_wallet_balance(self, session, wallet_id, blockchain, token_symbol, contract_address=None):
        """
        Get or create a wallet balance record
        
        Args:
            session: Database session
            wallet_id (str): Wallet ID
            blockchain (str): Blockchain name
            token_symbol (str): Token symbol
            contract_address (str, optional): Contract address for tokens
            
        Returns:
            WalletBalance: The wallet balance record
        """
        try:
            # First, try to find existing balance record
            wallet_balance = self.db_operations.find_wallet_balance(
                session=session,
                wallet_id=wallet_id,
                blockchain=blockchain,
                token_symbol=token_symbol,
                contract_address=contract_address
            )
            
            # If record exists, return it
            if wallet_balance:
                return wallet_balance
            
            # Create new balance record with zero balance
            self.logger.info(f"Creating new balance record for wallet {wallet_id}, {token_symbol} on {blockchain}")
            
            new_balance = WalletBalance(
                wallet_id=wallet_id,
                blockchain=blockchain,
                token_symbol=token_symbol,
                contract_address=contract_address,
                balance='0',
                created_at=datetime.now(),
                updated_at=datetime.now()
            )
            
            session.add(new_balance)
            session.flush()  # Flush to get the ID, but don't commit yet
            
            return new_balance
            
        except Exception as e:
            self.logger.error(f"⛔ Error getting/creating wallet balance: {str(e)}", exc_info=True)
            return None
    
    def get_wallet_balance(self, wallet_id, blockchain, token_symbol, contract_address=None):
        """
        Get current wallet balance
        
        Args:
            wallet_id (str): Wallet ID
            blockchain (str): Blockchain name
            token_symbol (str): Token symbol
            contract_address (str, optional): Contract address for tokens
            
        Returns:
            dict: Balance information
        """
        try:
            with self.db_operations.session_factory() as session:
                wallet_balance = self.db_operations.find_wallet_balance(
                    session=session,
                    wallet_id=wallet_id,
                    blockchain=blockchain,
                    token_symbol=token_symbol,
                    contract_address=contract_address
                )
                
                if wallet_balance:
                    return {
                        'success': True,
                        'wallet_id': wallet_id,
                        'blockchain': blockchain,
                        'token_symbol': token_symbol,
                        'contract_address': contract_address,
                        'balance': wallet_balance.balance,
                        'updated_at': wallet_balance.updated_at.isoformat() if wallet_balance.updated_at else None
                    }
                else:
                    return {
                        'success': True,
                        'wallet_id': wallet_id,
                        'blockchain': blockchain,
                        'token_symbol': token_symbol,
                        'contract_address': contract_address,
                        'balance': '0',
                        'updated_at': None
                    }
                    
        except Exception as e:
            self.logger.error(f"⛔ Error getting wallet balance: {str(e)}", exc_info=True)
            return {
                'success': False,
                'message': f'Error: {str(e)}',
                'wallet_id': wallet_id,
                'blockchain': blockchain,
                'token_symbol': token_symbol
            }
    
    def get_all_wallet_balances(self, wallet_id):
        """
        Get all balances for a wallet
        
        Args:
            wallet_id (str): Wallet ID
            
        Returns:
            dict: All wallet balances
        """
        try:
            with self.db_operations.session_factory() as session:
                wallet_balances = self.db_operations.find_all_wallet_balances(
                    session=session,
                    wallet_id=wallet_id
                )
                
                balances = []
                for balance in wallet_balances:
                    balances.append({
                        'blockchain': balance.blockchain,
                        'token_symbol': balance.token_symbol,
                        'contract_address': balance.contract_address,
                        'balance': balance.balance,
                        'updated_at': balance.updated_at.isoformat() if balance.updated_at else None
                    })
                
                return {
                    'success': True,
                    'wallet_id': wallet_id,
                    'balances': balances
                }
                
        except Exception as e:
            self.logger.error(f"⛔ Error getting all wallet balances: {str(e)}", exc_info=True)
            return {
                'success': False,
                'message': f'Error: {str(e)}',
                'wallet_id': wallet_id
            } 