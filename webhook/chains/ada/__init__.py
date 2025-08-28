from CC.webhook.chains.ada.processor import CardanoProcessor

# Create processor instance for use in webhook_routes.py
processor = CardanoProcessor()

__all__ = ['CardanoProcessor', 'processor'] 