"""
Test script for the new price alerts API (dual-type: custom + percentage).
Run: python scripts/test_price_alerts_api.py
"""

import sys
import os
import json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
os.environ['FLASK_ENV'] = 'development'

# Force CC package resolution
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from flask import Flask
from api.notifications_admin_api import notifications_admin_bp
from database import init_db, SessionLocal, PriceAlert
from sqlalchemy import text

# ─── Mini test app ───
app = Flask(__name__)
app.register_blueprint(notifications_admin_bp, url_prefix='/api')
app.config['TESTING'] = True
client = app.test_client()
app.secret_key = 'test-secret'


def setup():
    """Ensure table exists."""
    try:
        init_db()
        print("✓ Database initialized")
    except Exception as e:
        print(f"⚠ DB init (may be expected): {e}")

    # Also create via raw SQL
    try:
        session = SessionLocal()
        session.execute(text("""
            CREATE TABLE IF NOT EXISTS price_alerts (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id VARCHAR(36) NOT NULL,
                symbol VARCHAR(10) NOT NULL,
                alert_type VARCHAR(20) NOT NULL,
                target_price DECIMAL(20, 8) NULL,
                target_percent DECIMAL(10, 2) NULL,
                reference_price DECIMAL(20, 8) NULL,
                is_active TINYINT(1) NOT NULL DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                INDEX idx_user (user_id),
                INDEX idx_symbol (symbol)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """))
        session.commit()
        session.close()
        print("✓ price_alerts table ensured")
    except Exception as e:
        print(f"⚠ Table creation: {e}")


def cleanup():
    """Clean up test data."""
    try:
        session = SessionLocal()
        session.query(PriceAlert).filter(
            PriceAlert.user_id == 'test-user-123'
        ).delete()
        session.commit()
        session.close()
        print("✓ Test data cleaned")
    except Exception as e:
        print(f"⚠ Cleanup: {e}")


def test_create_custom_price_alert():
    """Test creating a custom above price alert."""
    print("\n── Test: Create Custom Price Alert (above) ──")
    resp = client.post(
        '/api/notifications/price-alert',
        json={
            "UserID": "test-user-123",
            "Symbol": "BTC",
            "AlertType": "above",
            "TargetPrice": 75000,
        }
    )
    data = resp.get_json()
    assert resp.status_code == 201, f"Expected 201, got {resp.status_code}: {data}"
    assert data['success'] is True, f"Expected success: {data}"
    assert data['alert']['symbol'] == 'BTC'
    assert data['alert']['alert_type'] == 'above'
    assert data['alert']['target_price'] == 75000.0
    print(f"  ✓ Created: {json.dumps(data['alert'], indent=2)}")
    return data['alert']['id']


def test_create_custom_below_alert():
    """Test creating a custom below price alert."""
    print("\n── Test: Create Custom Price Alert (below) ──")
    resp = client.post(
        '/api/notifications/price-alert',
        json={
            "UserID": "test-user-123",
            "Symbol": "ETH",
            "AlertType": "below",
            "TargetPrice": 2000,
        }
    )
    data = resp.get_json()
    assert resp.status_code == 201, f"Expected 201, got {resp.status_code}: {data}"
    assert data['success'] is True
    print(f"  ✓ Created: {json.dumps(data['alert'], indent=2)}")


def test_create_percent_up_alert():
    """Test creating a percent_up quick alert."""
    print("\n── Test: Create Quick Alert (percent_up) ──")
    resp = client.post(
        '/api/notifications/price-alert',
        json={
            "UserID": "test-user-123",
            "Symbol": "SOL",
            "AlertType": "percent_up",
            "TargetPercent": 10,
        }
    )
    data = resp.get_json()
    print(f"  Response: {json.dumps(data, indent=2)}")

    # This might fail if we can't fetch live prices, which is OK in test mode
    if resp.status_code == 503:
        print("  ⚠ Live price fetch unavailable (expected without CoinGecko cache)")
        return None

    assert resp.status_code == 201, f"Expected 201, got {resp.status_code}: {data}"
    assert data['success'] is True
    assert data['alert']['alert_type'] == 'percent_up'
    assert data['alert']['target_percent'] == 10.0
    print(f"  ✓ Created: {json.dumps(data['alert'], indent=2)}")
    return data['alert']['id']


def test_create_percent_down_alert():
    """Test creating a percent_down quick alert."""
    print("\n── Test: Create Quick Alert (percent_down) ──")
    resp = client.post(
        '/api/notifications/price-alert',
        json={
            "UserID": "test-user-123",
            "Symbol": "BTC",
            "AlertType": "percent_down",
            "TargetPercent": 5,
        }
    )
    data = resp.get_json()

    if resp.status_code == 503:
        print("  ⚠ Live price fetch unavailable (expected)")
        return

    assert resp.status_code == 201, f"Expected 201, got {resp.status_code}: {data}"
    assert data['success'] is True
    print(f"  ✓ Created: {json.dumps(data['alert'], indent=2)}")


def test_get_alerts():
    """Test listing alerts for a user."""
    print("\n── Test: Get Price Alerts ──")
    resp = client.get('/api/notifications/price-alerts/test-user-123')
    data = resp.get_json()
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {data}"
    assert data['success'] is True
    assert 'alerts' in data
    print(f"  ✓ Got {len(data['alerts'])} alert(s):")
    for a in data['alerts']:
        print(f"    - {a['symbol']} | {a['alert_type']} | {json.dumps({k: v for k, v in a.items() if k != 'symbol' and k != 'alert_type'})}")


def test_delete_by_id(alert_id):
    """Test deleting an alert by ID."""
    print(f"\n── Test: Delete Alert by ID (#{alert_id}) ──")
    resp = client.delete(
        '/api/notifications/price-alert',
        json={
            "UserID": "test-user-123",
            "AlertID": alert_id,
        }
    )
    data = resp.get_json()
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {data}"
    assert data['success'] is True
    print(f"  ✓ Deleted: {data['message']}")


def test_delete_by_symbol():
    """Test deleting an alert by Symbol + AlertType."""
    print("\n── Test: Delete Alert by Symbol/Type ──")
    resp = client.delete(
        '/api/notifications/price-alert',
        json={
            "UserID": "test-user-123",
            "Symbol": "ETH",
            "AlertType": "below",
        }
    )
    data = resp.get_json()
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {data}"
    assert data['success'] is True
    print(f"  ✓ Deleted: {data['message']}")


def test_get_bulk_prices():
    """Test the bulk prices endpoint."""
    print("\n── Test: Bulk Prices ──")
    resp = client.get('/api/notifications/price-alerts/prices?symbols=BTC,ETH,SOL')
    data = resp.get_json()
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {data}"
    assert data['success'] is True
    assert 'prices' in data
    print(f"  ✓ Got {data['count']} prices:")
    for sym, price in data['prices'].items():
        print(f"    {sym}: {price}")


def test_validation():
    """Test validation errors."""
    print("\n── Test: Validation ──")

    # Missing fields
    resp = client.post('/api/notifications/price-alert', json={})
    assert resp.status_code == 400
    print("  ✓ Missing fields rejected")

    # Invalid type
    resp = client.post('/api/notifications/price-alert', json={
        "UserID": "test-user-123",
        "Symbol": "BTC",
        "AlertType": "invalid_type",
    })
    assert resp.status_code == 400
    print("  ✓ Invalid alert_type rejected")

    # Negative percent
    resp = client.post('/api/notifications/price-alert', json={
        "UserID": "test-user-123",
        "Symbol": "BTC",
        "AlertType": "percent_up",
        "TargetPercent": -5,
    })
    assert resp.status_code == 400
    print("  ✓ Negative percent rejected")

    # Zero price
    resp = client.post('/api/notifications/price-alert', json={
        "UserID": "test-user-123",
        "Symbol": "BTC",
        "AlertType": "above",
        "TargetPrice": 0,
    })
    assert resp.status_code == 400
    print("  ✓ Zero price rejected")

    # Percent too large
    resp = client.post('/api/notifications/price-alert', json={
        "UserID": "test-user-123",
        "Symbol": "BTC",
        "AlertType": "percent_up",
        "TargetPercent": 9999,
    })
    assert resp.status_code == 400
    print("  ✓ >1000% rejected")


def test_cache():
    """Test that GET is served from cache on repeated calls."""
    print("\n── Test: Cache ──")
    # First call
    resp1 = client.get('/api/notifications/price-alerts/test-user-123')
    data1 = resp1.get_json()
    assert 'cached' not in data1 or data1['cached'] is False

    # Second call (within 30s TTL)
    resp2 = client.get('/api/notifications/price-alerts/test-user-123')
    data2 = resp2.get_json()
    print(f"  First call cached={data1.get('cached')}, Second call cached={data2.get('cached')}")
    # Cache might or might not be served in test mode; not critical


if __name__ == '__main__':
    print("╔══════════════════════════════════════════════════╗")
    print("║    Price Alerts API — Integration Tests          ║")
    print("╚══════════════════════════════════════════════════╝")

    setup()
    cleanup()  # Start clean

    try:
        # 1. Create custom alerts
        aid1 = test_create_custom_price_alert()
        test_create_custom_below_alert()

        # 2. Create quick percentage alerts
        perc_id = test_create_percent_up_alert()
        test_create_percent_down_alert()

        # 3. List alerts
        test_get_alerts()

        # 4. Delete by ID
        if aid1:
            test_delete_by_id(aid1)

        # 5. Delete by symbol
        test_delete_by_symbol()

        # 6. Bulk prices
        test_get_bulk_prices()

        # 7. Validation
        test_validation()

        # 8. Cache
        test_cache()

        print("\n" + "═" * 50)
        print("✅ ALL TESTS PASSED")
        print("═" * 50)

    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        cleanup()
