from sqlalchemy.orm import Session
from CC.database import Transfers, Blockchains, Address, Wallets, Price, Currencies
from decimal import Decimal
from datetime import datetime
import logging
from CC.utils.logging_config import get_logger

# Configure logging
logger = get_logger('firebase')  # Use firebase logger for notifications

# Function to register transfer for processing - defined locally to avoid circular imports
def _register_transfer_created(transfer_id: int):
    """
    Register a newly created transfer for processing
    
    This function is defined locally to avoid circular imports with TransferHandler.
    Temporarily simplified to avoid circular imports during debugging.
    
    Args:
        transfer_id: ID of the newly created transfer
    """
    try:
        # Log the transfer creation but don't process it for now
        logger.info(f"Transfer {transfer_id} created - further processing disabled for debugging")
        
        # Import firebase here to avoid circular imports
        from config.firebase import send_notification
        
        # Get the transfer details
        from database import SessionLocal, Transfers
        session = SessionLocal()
        try:
            transfer = session.query(Transfers).filter(Transfers.TransferID == transfer_id).first()
            if transfer:
                # Get user's device token
                from database import UserDevices
                device = session.query(UserDevices).filter(UserDevices.WalletID == transfer.WalletID).first()
                if device and device.DeviceToken:
                    # Prepare notification message
                    title = "New Transaction"
                    body = f"Received {transfer.Amount} {transfer.TokenSymbol} from {transfer.FromAddress}"
                    if transfer.Direction == 'outbound':
                        body = f"Sent {transfer.Amount} {transfer.TokenSymbol} to {transfer.ToAddress}"
                    
                    # Send notification
                    logger.info(f"Sending notification for transfer {transfer_id} to device {device.DeviceToken}")
                    send_notification(
                        token=device.DeviceToken,
                        title=title,
                        body=body,
                        data={
                            'transfer_id': str(transfer.TransferID),
                            'tx_hash': transfer.TxHash,
                            'amount': str(transfer.Amount),
                            'token_symbol': transfer.TokenSymbol,
                            'direction': transfer.Direction
                        }
                    )
                    logger.info(f"Notification sent successfully for transfer {transfer_id}")
                else:
                    logger.warning(f"No device token found for wallet {transfer.WalletID}")
        finally:
            session.close()
        
        # Actual implementation is commented out to avoid circular imports
        # In a future update, this should be moved to a proper event system
        """
        # Import here to avoid circular dependencies
        from services.TransferHandler import register_transfer_created
        from config.queue import get_rabbitmq_connection
        
        # Forward the call to the actual implementation
        register_transfer_created(transfer_id)
            
        # If we can't import or call the handler, try direct processing
        try:
            from services.TransferHandler import on_new_transfer
            on_new_transfer(transfer_id)
        except Exception as inner_e:
            logger.error(f"Fallback processing also failed for {transfer_id}: {str(inner_e)}")
        """
    except Exception as e:
        logger.error(f"Error in register_transfer_created for {transfer_id}: {str(e)}")

class TransferService:
    """Service for handling transfer creation and management"""
    
    def __init__(self, session: Session):
        self.session = session
    
    def _get_token_price(self, token_symbol: str, blockchain_id=None, asset_type=None) -> Decimal:
        """
        Get the current price for a token or currency
        
        Args:
            token_symbol: Token symbol to look up
            blockchain_id: Optional blockchain ID for native assets
            asset_type: Optional asset type ('native', 'token')
            
        Returns:
            Current price or None if not found
        """
        try:
            logger.info(f"Looking up price for token: {token_symbol}, asset_type: {asset_type}, blockchain_id: {blockchain_id}")
            
            # First try to query by token symbol directly
            price_record = self.session.query(Price).join(
                Currencies, 
                Price.crypto_id == Currencies.CurrencyID
            ).filter(
                Currencies.Symbol == token_symbol,
                Price.currency == 'USD'  # Default to USD
            ).first()
            
            if price_record:
                logger.info(f"Found price for {token_symbol} by direct symbol match: {price_record.price}")
                return price_record.price
            
            # If no price found and this is a native asset, try to find by blockchain
            if not price_record and asset_type == 'native' and blockchain_id:
                logger.info(f"No direct price found, trying to find native asset price for blockchain_id: {blockchain_id}")
                
                # Try to find the native currency for this blockchain
                blockchain_currency = self.session.query(Currencies).filter(
                    Currencies.BlockchainID == blockchain_id,
                    Currencies.IsToken == False
                ).first()
                
                if blockchain_currency:
                    logger.info(f"Found native currency for blockchain: {blockchain_currency.Symbol}")
                    
                    # Try to get price for the native currency
                    native_price = self.session.query(Price).filter(
                        Price.crypto_id == blockchain_currency.CurrencyID,
                        Price.currency == 'USD'
                    ).first()
                    
                    if native_price:
                        logger.info(f"Found price for native currency {blockchain_currency.Symbol}: {native_price.price}")
                        return native_price.price
                    else:
                        logger.warning(f"No price found for native currency {blockchain_currency.Symbol}")
                else:
                    logger.warning(f"No native currency found for blockchain_id {blockchain_id}")
            
            # Check the total number of price records for debugging
            total_prices = self.session.query(Price).count()
            logger.info(f"Total price records in database: {total_prices}")
            
            # If we still don't have a price, log more details and return None
            logger.warning(f"No price found for {token_symbol} after all attempts")
            return None
            
        except Exception as e:
            logger.error(f"Error getting price for {token_symbol}: {str(e)}", exc_info=True)
            return None
    
    def create_transfer(self, 
                        tx_hash: str,
                        blockchain_id: int,
                        address_id: int,
                        wallet_id: int,
                        amount: Decimal,
                        token_symbol: str,
                        direction: str,
                        status: str = "confirmed",
                        token_contract: str = None,
                        asset_type: str = "native",
                        from_address: str = None,
                        to_address: str = None,
                        block_number: int = None,
                        fee: Decimal = None,
                        explorer_url: str = None,
                        timestamp: datetime = None) -> Transfers:
        """
        Create a new transfer record in the database
        
        Args:
            tx_hash: Transaction hash
            blockchain_id: Blockchain ID
            address_id: Address ID
            wallet_id: Wallet ID
            amount: Transaction amount
            token_symbol: Token symbol
            direction: 'inbound' or 'outbound'
            status: Transaction status (pending, confirmed, failed)
            token_contract: Token contract address (for tokens)
            asset_type: 'native' or 'token'
            from_address: Sender address
            to_address: Recipient address
            block_number: Block number
            fee: Transaction fee
            explorer_url: URL to view transaction on blockchain explorer
            timestamp: Transaction timestamp
            
        Returns:
            Created transfer record
        """
        try:
            # Check if token_symbol is BSC and change it to BNB
            if token_symbol.upper() == 'BSC':
                token_symbol = 'BNB'
                logger.info(f"Changed token symbol from BSC to BNB for transfer {tx_hash}")
            
            # Get current price for the token
            current_price = self._get_token_price(token_symbol, blockchain_id, asset_type)
            
            # If still no price found, use a default value of 0
            if current_price is None:
                logger.warning(f"Using default price of 0 for {token_symbol}")
                current_price = Decimal('0')
                
            # Calculate the value of the transaction (amount * price)
            transaction_value = amount * current_price
            logger.info(f"Calculated transaction value: {amount} * {current_price} = {transaction_value}")
            
            # Create new transfer record
            transfer = Transfers(
                BlockchainID=blockchain_id,
                AddressID=address_id,
                WalletID=wallet_id,
                TxHash=tx_hash,
                BlockNumber=block_number,
                Timestamp=timestamp or datetime.utcnow(),
                FromAddress=from_address,
                ToAddress=to_address,
                Amount=amount,
                Price=transaction_value,  # Store the calculated value (amount * price)
                TokenSymbol=token_symbol,
                TokenContract=token_contract,
                AssetType=asset_type,
                Fee=fee,
                Direction=direction,
                Status=status,
                IsSuccessful=(status == "confirmed"),
                ExplorerUrl=explorer_url,
                CreatedAt=datetime.utcnow(),
                UpdatedAt=datetime.utcnow()
            )
            
            # Add to session and commit
            self.session.add(transfer)
            self.session.flush()  # فلاش برای گرفتن TransferID
            
            # کامیت تغییرات
            self.session.commit()
            
            # فراخوانی هندلر ثبت تراکنش برای به‌روزرسانی موجودی و اعلان‌ها
            if hasattr(transfer, 'TransferID'):
                _register_transfer_created(transfer.TransferID)
            
            return transfer
            
        except Exception as e:
            self.session.rollback()
            logger.error(f"خطا در ایجاد رکورد انتقال: {str(e)}", exc_info=True)
            raise
    
    def record_outgoing_transaction(self, 
                                   tx_hash: str,
                                   blockchain_name: str,
                                   sender_address: str,
                                   recipient_address: str,
                                   amount: str,
                                   token_symbol: str,
                                   asset_type: str = "native",
                                   token_contract: str = None,
                                   fee: str = None,
                                   explorer_url: str = None) -> Transfers:
        """
        Record an outgoing transaction
        
        Args:
            tx_hash: Transaction hash
            blockchain_name: Blockchain name
            sender_address: Sender address
            recipient_address: Recipient address
            amount: Amount to send
            token_symbol: Token symbol
            asset_type: 'native' or 'token'
            token_contract: Token contract address for tokens
            fee: Transaction fee
            explorer_url: URL to view transaction on blockchain explorer
            
        Returns:
            Created transfer record
        """
        try:
            # Find the blockchain
            blockchain = self.session.query(Blockchains).filter(
                Blockchains.BlockchainName == blockchain_name
            ).first()
            
            if not blockchain:
                logger.error(f"Blockchain {blockchain_name} not found")
                raise ValueError(f"Blockchain {blockchain_name} not found")
                
            # Find the address
            address = self.session.query(Address).filter(
                Address.PublicAddress == sender_address,
                Address.BlockchainID == blockchain.BlockchainID
            ).first()
            
            if not address:
                logger.error(f"Address {sender_address} not found for blockchain {blockchain_name}")
                raise ValueError(f"Address {sender_address} not found for blockchain {blockchain_name}")
                
            # Create the transfer
            return self.create_transfer(
                tx_hash=tx_hash,
                blockchain_id=blockchain.BlockchainID,
                address_id=address.AddressID,
                wallet_id=address.WalletID,
                amount=Decimal(amount),
                token_symbol=token_symbol,
                direction="outbound",
                token_contract=token_contract,
                asset_type=asset_type,
                from_address=sender_address,
                to_address=recipient_address,
                fee=Decimal(fee) if fee else None,
                explorer_url=explorer_url
            )
            
        except Exception as e:
            logger.error(f"Error recording outgoing transaction: {str(e)}")
            raise
    
    def record_incoming_transaction(self,
                                   tx_hash: str,
                                   blockchain_name: str,
                                   recipient_address: str,
                                   sender_address: str,
                                   amount: str,
                                   token_symbol: str,
                                   asset_type: str = "native",
                                   token_contract: str = None,
                                   explorer_url: str = None) -> Transfers:
        """
        Record an incoming transaction
        
        Args:
            tx_hash: Transaction hash
            blockchain_name: Blockchain name
            recipient_address: Recipient address
            sender_address: Sender address
            amount: Amount received
            token_symbol: Token symbol
            asset_type: 'native' or 'token'
            token_contract: Token contract address for tokens
            explorer_url: URL to view transaction on blockchain explorer
            
        Returns:
            Created transfer record
        """
        try:
            # Find the blockchain
            blockchain = self.session.query(Blockchains).filter(
                Blockchains.BlockchainName == blockchain_name
            ).first()
            
            if not blockchain:
                logger.error(f"Blockchain {blockchain_name} not found")
                raise ValueError(f"Blockchain {blockchain_name} not found")
                
            # Find the address
            address = self.session.query(Address).filter(
                Address.PublicAddress == recipient_address,
                Address.BlockchainID == blockchain.BlockchainID
            ).first()
            
            if not address:
                logger.error(f"Address {recipient_address} not found for blockchain {blockchain_name}")
                raise ValueError(f"Address {recipient_address} not found for blockchain {blockchain_name}")
                
            # Create the transfer
            return self.create_transfer(
                tx_hash=tx_hash,
                blockchain_id=blockchain.BlockchainID,
                address_id=address.AddressID,
                wallet_id=address.WalletID,
                amount=Decimal(amount),
                token_symbol=token_symbol,
                direction="inbound",
                token_contract=token_contract,
                asset_type=asset_type,
                from_address=sender_address,
                to_address=recipient_address,
                explorer_url=explorer_url
            )
            
        except Exception as e:
            logger.error(f"Error recording incoming transaction: {str(e)}")
            raise
    
    def get_user_transfers(self, user_id: str, limit: int = 50, offset: int = 0):
        """
        Get transfers for a user
        
        Args:
            user_id: User ID
            limit: Maximum number of transfers to return
            offset: Offset for pagination
            
        Returns:
            List of transfers
        """
        try:
            # Get user's wallets
            wallets = self.session.query(Wallets).filter(Wallets.UserID == user_id).all()
            
            if not wallets:
                logger.warning(f"No wallets found for user {user_id}")
                return []
                
            # Get wallet IDs
            wallet_ids = [wallet.WalletID for wallet in wallets]
            
            # Get transfers for these wallets
            transfers = self.session.query(Transfers).filter(
                Transfers.WalletID.in_(wallet_ids)
            ).order_by(
                Transfers.CreatedAt.desc()
            ).limit(limit).offset(offset).all()
            
            return transfers
            
        except Exception as e:
            logger.error(f"Error getting transfers for user {user_id}: {str(e)}")
            raise 