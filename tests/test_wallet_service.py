import pytest
from unittest.mock import Mock, patch
from services.wallet_service import WalletService
from database import SessionLocal

@pytest.fixture
def mock_session():
    return Mock(spec=SessionLocal)

@pytest.fixture
def wallet_service(mock_session):
    return WalletService(mock_session)

def test_create_wallet_success(wallet_service):
    """Test successful wallet creation"""
    wallet_name = "Test Wallet"
    result = wallet_service.create_wallet(wallet_name)
    
    assert result["user_id"] is not None
    assert len(result["mnemonic"].split()) in [12, 24]
    assert all(addr["address"] for addr in result["addresses"])

def test_create_wallet_invalid_name(wallet_service):
    """Test wallet creation with invalid name"""
    with pytest.raises(ValueError):
        wallet_service.create_wallet("")

@pytest.mark.integration
def test_wallet_creation_integration():
    """Integration test for wallet creation"""
    session = SessionLocal()
    service = WalletService(session)
    
    try:
        result = service.create_wallet("Integration Test Wallet")
        assert result["user_id"] is not None
        
        # Verify database entries
        user = session.query(Users).filter_by(id=result["user_id"]).first()
        assert user is not None
        
        wallet = session.query(Wallets).filter_by(user_id=user.id).first()
        assert wallet is not None
    finally:
        session.rollback()
        session.close() 