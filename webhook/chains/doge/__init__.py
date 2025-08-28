from CC.webhook.chains.doge.processor import DogecoinProcessor

# ایجاد نمونه پردازشگر برای استفاده در webhook_routes.py
processor = DogecoinProcessor()

__all__ = ['DogecoinProcessor'] 