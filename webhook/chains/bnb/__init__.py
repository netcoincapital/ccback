from CC.webhook.chains.bnb.processor import BNBProcessor

# ایجاد نمونه پردازشگر برای استفاده در webhook_routes.py
processor = BNBProcessor()

__all__ = ["BNBProcessor", "processor"] 