from flask import Blueprint, request, jsonify
from sqlalchemy.orm import Session
from database import Users, Wallets, Address, SessionLocal

# تعریف Blueprint
phrase_key_bp = Blueprint('phrase_key', __name__)

# مسیر برای دریافت Phrase Key
@phrase_key_bp.route('/get_phrase_key', methods=['POST'])
def get_phrase_key():
    try:
        # اتصال به دیتابیس
        session = SessionLocal()

        # دریافت UserID از درخواست
        data = request.get_json()
        user_id = data.get('UserID')
        
        if not user_id:
            return jsonify({"success": False, "message": "UserID is required"}), 400

        # جستجوی WalletID در جدول Wallets
        wallet = session.query(Wallets).filter(Wallets.UserID == user_id).first()

        if not wallet:
            return jsonify({"success": False, "message": "Wallet not found for the given UserID"}), 404

        # جستجوی PhraseKey در جدول Address
        address = session.query(Address).filter(Address.WalletID == wallet.WalletID).first()

        if not address or not address.PhraseKey:
            return jsonify({"success": False, "message": "PhraseKey not found for the given WalletID"}), 404

        # بازگرداندن PhraseKey به کاربر
        return jsonify({
            "success": True,
            "PhraseKey": address.PhraseKey
        })

    except Exception as e:
        return jsonify({"success": False, "message": f"An error occurred: {str(e)}"}), 500

    finally:
        session.close()