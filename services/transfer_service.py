from sqlalchemy.orm import Session
from database import Transfers, Blockchains, Address, Wallets
from decimal import Decimal
from datetime import datetime
import logging
from utils.logging_config import get_logger

# Configure logging
logger = get_logger(__file__)

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
            self.session.commit()
            
            # Get the transfer ID from the newly created record
            transfer_id = transfer.TransferID
            
            logger.info(f"Created new transfer record with ID {transfer_id} for tx {tx_hash}")
            
            # Trigger the event handler for new transfers
            # This will update user holdings based on the transfer
            _register_transfer_created(transfer_id)
            
            return transfer
            
        except Exception as e:
            self.session.rollback()
            logger.error(f"Error creating transfer record: {str(e)}")
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