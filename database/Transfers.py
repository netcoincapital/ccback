from sqlalchemy import Column, String, Integer, BigInteger, ForeignKey, DECIMAL, TIMESTAMP, Boolean, Text
from sqlalchemy.orm import relationship
from datetime import datetime
from .base import Base

class Transfers(Base):
    __tablename__ = 'Transfers'

    TransferID = Column(BigInteger, primary_key=True, autoincrement=True)

    BlockchainID = Column(Integer, ForeignKey('Blockchains.BlockchainID'), nullable=False)
    AddressID = Column(Integer, ForeignKey('Address.AddressID'), nullable=False)
    WalletID = Column(Integer, ForeignKey('Wallets.WalletID'), nullable=False)

    TxHash = Column(String(100), nullable=False, index=True)
    BlockNumber = Column(BigInteger, nullable=True)
    Timestamp = Column(TIMESTAMP, nullable=True)

    FromAddress = Column(String(100), nullable=True)
    ToAddress = Column(String(100), nullable=True)
    Amount = Column(DECIMAL(38, 18), nullable=False, default=0)

    TokenSymbol = Column(String(20), nullable=True)
    TokenContract = Column(String(100), nullable=True)
    AssetType = Column(String(20), nullable=True)  # native / token
    Fee = Column(DECIMAL(38, 18), nullable=True, default=0)
    Direction = Column(String(10), nullable=False)  # inbound / outbound
    Status = Column(String(20), nullable=True)  # pending / confirmed / failed
    IsSuccessful = Column(Boolean, nullable=False, default=True)

    ExplorerUrl = Column(Text, nullable=True)

    CreatedAt = Column(TIMESTAMP, default=datetime.utcnow, nullable=False)
    UpdatedAt = Column(TIMESTAMP, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # روابط
    blockchain = relationship('Blockchains')
    address = relationship('Address')
    wallet = relationship('Wallets')

    def __repr__(self):
        return f"<Transfer(TxHash={self.TxHash}, Amount={self.Amount}, Direction={self.Direction})>"
