"""
PriceAlert ORM Model
=====================
جدول اختصاصی price_alerts با پشتیبانی از دو نوع هشدار:

1. هشدار قیمت دقیق (Custom):
   - alert_type: "above" یا "below"
   - target_price: قیمت هدف (مثلاً 75000)
   - reference_price: NULL

2. هشدار درصدی (Quick):
   - alert_type: "percent_up" یا "percent_down"
   - target_percent: درصد تغییر (مثلاً 10)
   - reference_price: قیمت مرجع برای محاسبه درصد (قیمت لحظه ایجاد)
   - target_price: NULL
"""

from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, TIMESTAMP, Enum as SAEnum
from datetime import datetime
from .base import Base


class PriceAlert(Base):
    __tablename__ = 'price_alerts'

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(36), nullable=False, index=True)
    symbol = Column(String(10), nullable=False, index=True)

    # نوع هشدار: above | below | percent_up | percent_down
    alert_type = Column(String(20), nullable=False)

    # برای هشدار قیمت دقیق (Custom)
    target_price = Column(Float, nullable=True)

    # برای هشدار درصدی (Quick)
    target_percent = Column(Float, nullable=True)
    reference_price = Column(Float, nullable=True)

    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(TIMESTAMP, default=datetime.utcnow, nullable=False)
    updated_at = Column(TIMESTAMP, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    def to_dict(self) -> dict:
        """Convert to API response format."""
        result = {
            "id": self.id,
            "symbol": self.symbol,
            "alert_type": self.alert_type,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
        if self.alert_type in ("above", "below"):
            result["target_price"] = self.target_price
        else:
            result["target_percent"] = self.target_percent
            result["reference_price"] = round(self.reference_price, 2) if self.reference_price else None
        return result

    def __repr__(self):
        return (
            f"<PriceAlert(id={self.id}, user={self.user_id[:8]}..., "
            f"{self.symbol}, type={self.alert_type})>"
        )
