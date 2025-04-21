from webhook.webhook_routes import webhook_bp
from webhook.tatum_subscription import (
    create_contract_subscription, 
    list_subscriptions,
    delete_subscription, 
    create_address_subscription
)

# Importing chain-specific modules
from webhook.chains import eth, btc, trx, matic, sol, xrp, doge, ltc, ada

def init_app(app):
    """
    تنظیم برنامه Flask برای استفاده از وب‌هوک‌ها
    
    Args:
        app: برنامه Flask
    """
    # ثبت مسیر‌های وب‌هوک
    app.register_blueprint(webhook_bp)

__all__ = [
    'init_app',
    'webhook_bp',
    'create_contract_subscription',
    'list_subscriptions',
    'delete_subscription',
    'create_address_subscription'
] 