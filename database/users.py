from sqlalchemy import Column, Integer, String, TIMESTAMP
from sqlalchemy.orm import relationship
from datetime import datetime
from .base import Base
import uuid

def generate_uuid():
    return str(uuid.uuid4())

class Users(Base):
    __tablename__ = 'users'

    UserID = Column(String(36), primary_key=True, default=generate_uuid)
    ID = Column(Integer, primary_key=True, autoincrement=True)
    Email = Column(String(255), nullable=True, unique=True)
    CreatedAt = Column(TIMESTAMP, default=datetime.utcnow, nullable=False)
    UpdatedAt = Column(TIMESTAMP, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    Device = Column(String(255), nullable=True)
    IP = Column(String(45), nullable=True)

    wallets = relationship('Wallets', back_populates='user', foreign_keys='Wallets.UserID')
    user_holdings = relationship('UserHolding', back_populates='user', cascade='all, delete-orphan')

    def __repr__(self):
        return f"<User(UserID={self.UserID}, ID={self.ID}, Email='{self.Email}')>"
