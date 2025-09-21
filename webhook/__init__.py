from .webhook_routes import webhook_bp
# هیچ chain یا ماژول دیگری را اینجا import نکنید؛ در زمان نیاز، داخل فایل‌های مربوطه import شود.


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
    'webhook_bp'
] 