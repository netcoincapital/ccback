from flask import Flask, jsonify, request
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine
import logging

from CC.database.ads import Ads

app = Flask(__name__)

# Assuming you have a database URL
DATABASE_URL = "sqlite:///./test.db"  # Replace with your actual database URL
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Configure logging
logging.basicConfig(level=logging.DEBUG)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.route("/ads/", methods=["GET"])
def read_ads():
    skip = request.args.get('skip', default=0, type=int)
    limit = request.args.get('limit', default=10, type=int)
    try:
        db = next(get_db())
        ads = db.query(Ads).offset(skip).limit(limit).all()
        if not ads:
            return jsonify({"error": "Ads not found"}), 404
        return jsonify([ad.__dict__ for ad in ads])
    except Exception as e:
        logging.error("Error occurred while fetching ads: %s", e)
        return jsonify({"error_type": "internal_error", "message": str(e), "success": False}), 500

if __name__ == "__main__":
    app.run(debug=True) 