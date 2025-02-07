from flask import Flask, after_this_request
from flask_cors import CORS
from database import init_db
from generate import generate_bp
from WI import import_bp
from CU import CUpdate_bp, CPost_bp
from TA import phrase_key_bp, receive_bp
from balance import balance_bp
import logging
import os
from datetime import datetime, timezone

# تنظیمات لاگ
log_dir = os.path.join(os.path.dirname(__file__), 'logs')
os.makedirs(log_dir, exist_ok=True)

log_file = os.path.join(log_dir, f"log_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.txt")
logging.basicConfig(level=logging.DEBUG, filename=log_file, filemode='a',
                    format='%(asctime)s - %(levelname)s - %(message)s')

app = Flask(__name__)

# تنظیمات CORS
cors = CORS(app, resources={
    r"/*": {
        "origins": "*",  # یا به‌صورت خاص: ["http://example.com", "http://localhost:3000"]
        "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        "allow_headers": ["Content-Type", "Authorization"],
        "supports_credentials": True
    }
})

# افزودن هدرهای Keep-Alive به تمام پاسخ‌ها
@app.after_request
def add_keep_alive_headers(response):
    """
    افزودن هدرهای Keep-Alive به تمام پاسخ‌ها.
    """
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
app.register_blueprint(balance_bp)

# مقداردهی اولیه پایگاه داده
init_db()

if __name__ == '__main__':
    logging.info("Starting Flask app with Keep-Alive enabled.")
    app.run(debug=True, host='0.0.0.0', port=5000)
