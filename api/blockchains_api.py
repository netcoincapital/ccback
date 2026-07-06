"""
Blockchains List API
====================
لیست تمام بلاکچین‌های ذخیره شده در جدول blockchains را برمی‌گرداند.

Endpoints:
  GET  /api/blockchains  ← لیست کامل بلاکچین‌ها
"""
from flask import Blueprint, jsonify
from sqlalchemy import text
from utils.logging_config import get_logger

logger = get_logger(__name__)

blockchains_bp = Blueprint('blockchains', __name__)


@blockchains_bp.route('/blockchains', methods=['GET'])
def get_blockchains():
    """
    دریافت لیست کامل بلاکچین‌ها از دیتابیس.

    Returns:
        JSON:
        {
            "success": true,
            "blockchains": [
                {
                    "id": 1,
                    "name": "Ethereum",
                    "symbol": "ETH",
                    "chain_code": "ethereum"
                },
                ...
            ]
        }
    """
    try:
        # Import here to avoid circular import at module level
        from database import SessionLocal, Blockchains

        session = SessionLocal()
        try:
            records = session.query(Blockchains).order_by(Blockchains.BlockchainID).all()

            blockchains = []
            for b in records:
                blockchains.append({
                    "id": b.BlockchainID,
                    "name": b.BlockchainName,
                    "symbol": b.Symbol,
                    "chain_code": b.ChainCode,
                })

            logger.info(f"Returning {len(blockchains)} blockchains from DB")
            return jsonify({
                "success": True,
                "blockchains": blockchains,
                "count": len(blockchains),
            })

        finally:
            session.close()

    except Exception as e:
        logger.error(f"Error fetching blockchains: {str(e)}", exc_info=True)
        return jsonify({
            "success": False,
            "message": f"Database error: {str(e)}"
        }), 500
