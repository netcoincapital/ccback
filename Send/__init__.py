from Send.Send import send_bp

def init_send_routes(app):
    """Initialize send routes"""
    app.register_blueprint(send_bp, url_prefix='/send') 