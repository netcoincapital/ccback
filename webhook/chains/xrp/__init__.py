from CC.webhook.chains.xrp.processor import RippleProcessor

# ایجاد نمونه پردازشگر برای استفاده در webhook_routes.py
processor = RippleProcessor()

__all__ = ['RippleProcessor']