from CC.webhook.chains.ltc.processor import LitecoinProcessor

# ایجاد نمونه پردازشگر برای استفاده در webhook_routes.py
processor = LitecoinProcessor()

__all__ = ['LitecoinProcessor'] 