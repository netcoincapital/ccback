from flask import Flask, after_this_request, jsonify, request
from flask_cors import CORS
from flask_wtf.csrf import CSRFProtect, CSRFError
from database import init_db
from generate import generate_bp
from WI import import_bp
from CU import CUpdate_bp, CPost_bp
from TA import phrase_key_bp, receive_bp, gasfee_bp
from security.validators import SecurityUtils, ValidationError
import logging
import os
from datetime import datetime, timezone
from utils.error_handlers import APIErrorHandler

# تنظیمات لاگ
log_dir = os.path.join(os.path.dirname(__file__), 'logs')
os.makedirs(log_dir, exist_ok=True)

log_file = os.path.join(log_dir, f"app_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.txt")
logging.basicConfig(level=logging.DEBUG)

app = Flask(__name__)

# تنظیمات امنیتی
app.config.update(
    # کلید مخفی برای توکن CSRF
    SECRET_KEY=os.environ.get('SECRET_KEY', os.urandom(24)),
    
    # تنظیمات کوکی
    SESSION_COOKIE_SECURE=True,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Strict',
    
    # تنظیمات CSRF
    WTF_CSRF_ENABLED=True,
    WTF_CSRF_TIME_LIMIT=3600,  # مدت زمان اعتبار توکن (1 ساعت)
    WTF_CSRF_SSL_STRICT=True
)

# فعال‌سازی محافظت CSRF
csrf = CSRFProtect(app)

# لیست دامنه‌های مجاز
ALLOWED_ORIGINS = [
    'http://localhost:3000',           # برای توسعه محلی
    'https://your-frontend-domain.com', # دامنه اصلی فرانت‌اند
    'https://api.your-domain.com'      # دامنه API
]

# تنظیمات CORS با محدودیت‌های دقیق
cors = CORS(app, resources={
    r"/*": {
        "origins": ALLOWED_ORIGINS,
        "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        "allow_headers": [
            "Content-Type",
            "Authorization",
            "X-CSRF-Token",
            "X-Requested-With"
        ],
        "expose_headers": [
            "Content-Range",
            "X-Content-Range",
            "X-CSRF-Token"
        ],
        "supports_credentials": True,
        "max_age": 600,
        "vary_header": True
    }
})

# اضافه کردن هدرهای امنیتی به تمام پاسخ‌ها
@app.after_request
def add_security_headers(response):
    """افزودن هدرهای امنیتی به تمام پاسخ‌ها"""
    response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'SAMEORIGIN'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    response.headers['Content-Security-Policy'] = "default-src 'self'"
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    return response

# افزودن هدرهای Keep-Alive به تمام پاسخ‌ها
@app.after_request
def add_keep_alive_headers(response):
    """افزودن هدرهای Keep-Alive به تمام پاسخ‌ها"""
    response.headers['Connection'] = 'keep-alive'
    response.headers['Keep-Alive'] = 'timeout=5, max=100'
    return response

# ثبت blueprints
app.register_blueprint(generate_bp)
app.register_blueprint(import_bp)
app.register_blueprint(CUpdate_bp)
app.register_blueprint(CPost_bp)
app.register_blueprint(phrase_key_bp)
app.register_blueprint(receive_bp)
app.register_blueprint(gasfee_bp)

# مقداردهی اولیه پایگاه داده
init_db()

# مدیریت خطاها
@app.errorhandler(ValidationError)
@app.errorhandler(CSRFError)
@app.errorhandler(Exception)
def handle_error(e):
    return APIErrorHandler.handle_error(e, request)

if __name__ == '__main__':
    # در محیط توسعه از HTTPS استفاده کنید
    context = ('cert.pem', 'key.pem')  # گواهی‌نامه و کلید SSL
    
    logging.info("Starting Flask app with security settings enabled.")
    app.run(
        debug=False,  # در محیط تولید حتماً False باشد
        host='0.0.0.0',
        port=5000,
        ssl_context=context
    )
