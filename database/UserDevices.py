from sqlalchemy import Column, String, Integer, ForeignKey, TIMESTAMP
from sqlalchemy.orm import relationship
from datetime import datetime
from .base import Base

class UserDevices(Base):
    __tablename__ = 'user_devices'

    DeviceID = Column(Integer, primary_key=True, autoincrement=True)
    UserID = Column(String(36), ForeignKey('users.UserID', ondelete='CASCADE'), nullable=False)
    WalletID = Column(String(50), ForeignKey('wallets.WalletID', ondelete='CASCADE'), nullable=False)
    DeviceToken = Column(String(255), nullable=False, unique=True)
    DeviceName = Column(String(100), nullable=True)
    DeviceType = Column(String(50), nullable=True)  # android, ios
    CreatedAt = Column(TIMESTAMP, default=datetime.utcnow, nullable=False)
    UpdatedAt = Column(TIMESTAMP, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # روابط
    user = relationship('Users', backref='devices')
    wallet = relationship('Wallets', backref='devices')

    def __repr__(self):
        return f"<UserDevice(DeviceID={self.DeviceID}, UserID={self.UserID}, WalletID={self.WalletID})>" 