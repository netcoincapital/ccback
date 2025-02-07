from flask import Blueprint, request, jsonify
from sqlalchemy.orm import Session
from database import Users, Wallets, Address, SessionLocal

# تعریف Blueprint
receive_bp = Blueprint('receive', __name__)

# مسیر برای دریافت Public Address
@receive_bp.route('/Recive', methods=['POST'])
def get_public_address():
    try:
        # اتصال به دیتابیس
        session = SessionLocal()

        # دریافت UserID و BlockchainName از درخواست
        data = request.get_json()
        user_id = data.get('UserID')
        blockchain_name = data.get('BlockchainName')

        if not user_id or not blockchain_name:
            return jsonify({"success": False, "message": "UserID and BlockchainName are required"}), 400

        # مپ کردن BlockchainName به BlockchainID
        blockchain_mapping = {
            "Ethereum": 1,
            "Tron": 2,
            "BNB": 3
        }

        blockchain_id = blockchain_mapping.get(blockchain_name)
        if not blockchain_id:
            return jsonify({"success": False, "message": "Invalid BlockchainName"}), 400

        print(f"Mapped BlockchainName={blockchain_name} to BlockchainID={blockchain_id}")

        # جستجوی WalletID در جدول Wallets بر اساس UserID
        wallet = session.query(Wallets).filter(Wallets.UserID == user_id).first()
        if not wallet:
            return jsonify({"success": False, "message": "Wallet not found for the given UserID"}), 404

        print(f"Wallet found: WalletID={wallet.WalletID}, UserID={wallet.UserID}")

        # جستجوی Public Address در جدول Address بر اساس WalletID و BlockchainID
        address = session.query(Address).filter(
            Address.WalletID == wallet.WalletID,
            Address.BlockchainID == blockchain_id
        ).first()

        if not address or not address.PublicAddress:
            return jsonify({"success": False, "message": "Public Address not found for the given criteria"}), 404

        print(f"Address found: PublicAddress={address.PublicAddress}, WalletID={address.WalletID}, BlockchainID={address.BlockchainID}")

        # بازگرداندن Public Address به کاربر
        return jsonify({
            "success": True,
            "PublicAddress": address.PublicAddress
        })

    except Exception as e:
        print(f"An error occurred: {str(e)}")
        return jsonify({"success": False, "message": f"An error occurred: {str(e)}"}), 500

    finally:
        session.close()