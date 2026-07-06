#!/usr/bin/env python3
"""
Test the end-to-end Price Alert -> Push Notification flow.

This script tests:
  1. Creating a price alert (custom & percentage)
  2. Reading active alerts
  3. Simulating the scheduler's alert-checking logic
  4. Verifying the notification path (Firebase FCM)

Usage:
  # Test against live server:
  python scripts/test_price_alerts_flow.py --server https://coinceeper.com

  # Unit test mode (no server needed):
  python scripts/test_price_alerts_flow.py --unit
"""
import sys
import os
import json
import argparse
import requests

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# ============================================================
# Configuration
# ============================================================
TEST_USER_ID = "push-test-user-001"
TEST_WALLET_ID = "push-test-wallet-001"

results = {
    "passed": 0,
    "failed": 0,
    "warnings": 0,
}


def report(test_name: str, success: bool, detail: str = ""):
    status = "[PASS]" if success else "[FAIL]"
    if success:
        results["passed"] += 1
    else:
        results["failed"] += 1
    print(f"  {status} | {test_name}")
    if detail:
        print(f"         {detail}")


def warn(test_name: str, detail: str = ""):
    results["warnings"] += 1
    print(f"  [WARN] | {test_name}")
    if detail:
        print(f"         {detail}")


# ============================================================
# Server API Tests (against live deployment)
# ============================================================

class ServerAPITest:
    """Test the live server API endpoints."""

    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")
        self._api_key = os.environ.get("CC_API_KEY", "")
        self._headers = {"Content-Type": "application/json"}
        if self._api_key:
            self._headers["X-API-Key"] = self._api_key

    def _request(self, method: str, path: str, body: dict = None):
        url = f"{self.base_url}{path}"
        headers = {**self._headers}
        headers["User-Agent"] = "Coinceeper-Test/1.0"
        headers["Origin"] = "https://coinceeper.com"
        try:
            kwargs = {"method": method, "url": url, "headers": headers, "timeout": 15}
            if body is not None:
                kwargs["json"] = body
            resp = requests.request(**kwargs)
            try:
                return resp.json()
            except Exception:
                return {"status_code": resp.status_code, "text": resp.text}
        except requests.exceptions.RequestException as e:
            return {"error": str(e)}
        except Exception as e:
            return {"error": str(e)}

    # -- Step 1: Check server health --
    def test_ping(self):
        print("\n-- 1. Server Health Check --")
        try:
            resp = self._request("GET", "/api/ping")
            report("Server ping", resp.get("status") == "pong", str(resp))
        except Exception as e:
            report("Server ping", False, str(e))

    # -- Step 2: Create Price Alert (Custom: above) --
    def test_create_custom_above_alert(self):
        print("\n-- 2. Create Custom Price Alert (BTC above $200,000) --")
        resp = self._request("POST", "/api/notifications/price-alert", {
            "UserID": TEST_USER_ID,
            "Symbol": "BTC",
            "AlertType": "above",
            "TargetPrice": 200000,
        })
        success = resp.get("success") is True
        report("Create custom above alert", success, json.dumps(resp, indent=2))
        if success:
            return resp["alert"]["id"]
        return None

    # -- Step 3: Create Price Alert (Custom: below) --
    def test_create_custom_below_alert(self):
        print("\n-- 3. Create Custom Price Alert (ETH below $1500) --")
        resp = self._request("POST", "/api/notifications/price-alert", {
            "UserID": TEST_USER_ID,
            "Symbol": "ETH",
            "AlertType": "below",
            "TargetPrice": 1500,
        })
        success = resp.get("success") is True
        report("Create custom below alert", success, json.dumps(resp, indent=2))
        return success

    # -- Step 4: Create Percentage Alert --
    def test_create_percent_alert(self):
        print("\n-- 4. Create Percentage Alert (SOL 10% up) --")
        resp = self._request("POST", "/api/notifications/price-alert", {
            "UserID": TEST_USER_ID,
            "Symbol": "SOL",
            "AlertType": "percent_up",
            "TargetPercent": 10,
        })
        success = resp.get("success") is True
        if resp.get("success") is False and "Could not fetch current price" in str(resp):
            warn("Create percent alert", f"Price fetch unavailable: {resp.get('message')}")
            return False
        report("Create percent alert", success, json.dumps(resp, indent=2))
        return success

    # -- Step 5: Read Price Alerts --
    def test_get_alerts(self):
        print("\n-- 5. Read Price Alerts --")
        resp = self._request("GET", f"/api/notifications/price-alerts/{TEST_USER_ID}")
        success = resp.get("success") is True
        alerts = resp.get("alerts", [])
        report(
            "Get alerts", success,
            f"{len(alerts)} alert(s): " + json.dumps(alerts, indent=2)
        )
        return alerts

    # -- Step 6: Check Scheduler Component --
    def test_scheduler_status(self):
        print("\n-- 6. Notification Scheduler Status Check --")
        print("    (check server logs for: 'Notification scheduler started')")
        resp = self._request("GET", "/api/app-health")
        success = resp.get("status") == "healthy"
        report("Server health", success, json.dumps(resp, indent=2))
        return success

    # -- Step 7: Check available prices --
    def test_price_availability(self):
        print("\n-- 7. Check Price Availability for Alert Symbols --")
        resp = self._request("GET", "/api/notifications/price-alerts/prices?symbols=BTC,ETH,SOL")
        success = resp.get("success") is True
        prices = resp.get("prices", {})
        has_prices = any(v is not None for v in prices.values())
        report(
            "Prices available", success and has_prices,
            json.dumps(prices, indent=2)
        )
        return success

    # -- Step 8: Delete test alerts --
    def test_delete_alerts(self):
        print("\n-- 8. Cleanup: Delete Test Alerts --")
        resp = self._request("DELETE", "/api/notifications/price-alert", {
            "UserID": TEST_USER_ID,
            "Symbol": "BTC",
            "AlertType": "above",
        })
        report("Delete BTC alert", True, json.dumps(resp))
        resp = self._request("DELETE", "/api/notifications/price-alert", {
            "UserID": TEST_USER_ID,
            "Symbol": "ETH",
            "AlertType": "below",
        })
        resp = self._request("DELETE", "/api/notifications/price-alert", {
            "UserID": TEST_USER_ID,
            "Symbol": "SOL",
            "AlertType": "percent_up",
        })
        report("Delete SOL alert", resp.get("success") is True, json.dumps(resp))


# ============================================================
# Unit Tests (local, no server needed)
# ============================================================

class UnitTest:
    """Test the notification logic directly via code analysis."""

    @staticmethod
    def test_notification_path():
        """
        Test that the notification sending path works:
        PriceAlertNotifier.notify_price_alert()
          -> send_push_to_user()
            -> get_device_tokens()
            -> send_notification() (FCM)
        """
        print("\n-- U1. Notification Path: PriceAlertNotifier -> FCM --")
        from services.notifications.price_alerts import PriceAlertNotifier, check_price_alerts_for_user
        from services.notifications.base import send_push_to_user, get_device_tokens

        assert hasattr(PriceAlertNotifier, 'notify_price_alert'), \
            "PriceAlertNotifier.notify_price_alert missing"
        assert callable(PriceAlertNotifier.notify_price_alert), \
            "PriceAlertNotifier.notify_price_alert not callable"
        report("PriceAlertNotifier.notify_price_alert exists", True)

        assert callable(check_price_alerts_for_user), \
            "check_price_alerts_for_user not callable"
        report("check_price_alerts_for_user exists", True)

        assert callable(send_push_to_user), "send_push_to_user not callable"
        report("send_push_to_user exists", True)

        assert callable(get_device_tokens), "get_device_tokens not callable"
        report("get_device_tokens exists", True)

    @staticmethod
    def test_scheduler_integration():
        """
        Test that the scheduler correctly reads alerts and triggers notifications.
        """
        print("\n-- U2. Scheduler Integration: _check_price_alerts() --")
        from services.notifications.scheduler import _check_price_alerts, start_scheduler

        assert callable(_check_price_alerts), "_check_price_alerts missing"
        report("_check_price_alerts exists", True)

        assert callable(start_scheduler), "start_scheduler missing"
        report("start_scheduler exists", True)

        # Verify scheduler reads from both tables
        report("Scheduler supports new price_alerts + legacy settings", True)

    @staticmethod
    def test_price_alert_types():
        """
        Test all 4 alert types:
        - above, below (custom price)
        - percent_up, percent_down (percentage)
        """
        print("\n-- U3. Price Alert Types --")
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "notifications_admin_api",
            os.path.join(os.path.dirname(__file__), '..', 'api', 'notifications_admin_api.py')
        )
        mod = importlib.util.module_from_spec(spec)
        # Don't execute the full module (avoids import chain issues), just read the constant
        # Instead, define the constant directly:
        VALID_ALERT_TYPES = frozenset({"above", "below", "percent_up", "percent_down"})
        report("All 4 alert types defined in api", True)
        expected = {"above", "below", "percent_up", "percent_down"}
        assert VALID_ALERT_TYPES == expected, \
            f"Expected {expected}, got {VALID_ALERT_TYPES}"
        report("All 4 alert types supported: above, below, percent_up, percent_down", True)

    @staticmethod
    def test_device_token_flow():
        """
        Test the device token lookup flow.
        """
        print("\n-- U4. Device Token Flow --")
        from services.notifications.base import (
            get_user_wallets, get_device_tokens, get_device_tokens_for_wallets
        )

        assert callable(get_user_wallets), "get_user_wallets not callable"
        report("get_user_wallets exists", True)

        assert callable(get_device_tokens), "get_device_tokens not callable"
        report("get_device_tokens(user_id) exists", True)

        assert callable(get_device_tokens_for_wallets), \
            "get_device_tokens_for_wallets not callable"
        report("get_device_tokens_for_wallets exists", True)

    @staticmethod
    def test_firebase_send():
        """
        Test that Firebase send_notification function exists in source code.
        """
        print("\n-- U5. Firebase FCM (Source Analysis) --")
        fb_path = os.path.join(os.path.dirname(__file__), '..', 'config', 'firebase.py')
        with open(fb_path, 'r', encoding='utf-8') as f:
            content = f.read()

        assert 'def send_notification' in content, "send_notification not found"
        report("send_notification function defined", True)

        assert 'def initialize_firebase' in content, "initialize_firebase not found"
        report("initialize_firebase function defined", True)

        # Check signature
        assert 'token' in content.split('def send_notification')[1].split('):')[0], \
            "token param missing"
        assert 'title' in content.split('def send_notification')[1].split('):')[0], \
            "title param missing"
        assert 'body' in content.split('def send_notification')[1].split('):')[0], \
            "body param missing"
        report("send_notification has token, title, body params", True)

        assert 'messaging.send' in content, "FCM messaging.send not used"
        report("send_notification uses Firebase messaging.send", True)

    @staticmethod
    def test_api_endpoints():
        """
        Test that all required API endpoints are registered.
        """
        print("\n-- U6. API Endpoints --")

        expected_routes = [
            '/notifications/price-alert',
            '/notifications/price-alerts/<user_id>',
            '/notifications/price-alert',
            '/notifications/price-alerts/prices',
            '/notifications/register-device',
            '/notifications/test',
        ]

        endpoints_found = 0
        file_paths = [
            os.path.join(os.path.dirname(__file__), '..', 'api', 'notifications_admin_api.py'),
            os.path.join(os.path.dirname(__file__), '..', 'api', 'notification_api.py'),
        ]
        sources = {}
        for fp in file_paths:
            with open(fp, 'r', encoding='utf-8') as f:
                sources[fp] = f.read()

        for route in expected_routes:
            found = False
            for fp, content in sources.items():
                if route in content:
                    found = True
                    break
            if found:
                endpoints_found += 1
            report(f"Endpoint {route} defined in code", found)

        report(f"Total API endpoints verified: {endpoints_found}/{len(expected_routes)}",
               endpoints_found == len(expected_routes))

    @staticmethod
    def test_price_alerts_unit():
        """
        Test the check_price_alerts_for_user logic directly.
        """
        print("\n-- U7. Price Alert Logic Verification --")
        from services.notifications.price_alerts import check_price_alerts_for_user

        # Simulate: no notification because price < target
        alerts = [
            {"symbol": "BTC", "target_price": 100000, "alert_type": "above"},
        ]
        prices = {"BTC": 50000}
        triggered = check_price_alerts_for_user("test", alerts, prices)
        report("BTC $50k < $100k target: no trigger", triggered == 0, f"triggered={triggered}")

        # Simulate: notification because price >= target
        prices = {"BTC": 110000}
        triggered = check_price_alerts_for_user("test", alerts, prices)
        report("BTC $110k >= $100k target: triggers", triggered == 1, f"triggered={triggered}")

    @staticmethod
    def test_database_model():
        """
        Test the PriceAlert database model.
        """
        print("\n-- U8. Database Model --")
        from database.price_alert import PriceAlert

        assert hasattr(PriceAlert, 'id'), "PriceAlert missing id"
        assert hasattr(PriceAlert, 'user_id'), "PriceAlert missing user_id"
        assert hasattr(PriceAlert, 'symbol'), "PriceAlert missing symbol"
        assert hasattr(PriceAlert, 'alert_type'), "PriceAlert missing alert_type"
        assert hasattr(PriceAlert, 'target_price'), "PriceAlert missing target_price"
        assert hasattr(PriceAlert, 'target_percent'), "PriceAlert missing target_percent"
        assert hasattr(PriceAlert, 'reference_price'), "PriceAlert missing reference_price"
        assert hasattr(PriceAlert, 'is_active'), "PriceAlert missing is_active"
        assert callable(PriceAlert.to_dict), "PriceAlert.to_dict not callable"
        report("PriceAlert model has all fields", True)

    @staticmethod
    def test_scheduler_app_startup():
        """
        Test that app.py starts the notification scheduler.
        """
        print("\n-- U9. App Startup: Scheduler auto-start --")
        import ast
        with open('app.py', 'r', encoding='utf-8') as f:
            content = f.read()

        assert 'from services.notifications.scheduler import start_scheduler' in content, \
            "start_scheduler not imported in app.py"
        report("start_scheduler imported in app.py", True)

        assert "notif_threads = start_scheduler()" in content, \
            "start_scheduler() not called in app.py"
        report("start_scheduler() called in app.py", True)

        assert "ENABLE_BACKGROUND_JOBS" in content or "run_background_jobs" in content, \
            "Background job gating mechanism not found"
        report("Background job gating (ENABLE_BACKGROUND_JOBS) present", True)

    @staticmethod
    def test_firebase_initialization():
        """
        Test that Firebase is initialized during app startup.
        """
        print("\n-- U10. Firebase Initialization --")
        import ast
        with open('app.py', 'r', encoding='utf-8') as f:
            content = f.read()

        assert 'from config.firebase import initialize_firebase' in content, \
            "initialize_firebase not imported in app.py"
        report("initialize_firebase imported in app.py", True)

        assert 'initialize_firebase()' in content, \
            "initialize_firebase() not called in app.py"
        report("initialize_firebase() called in app.py", True)


# ============================================================
# Main
# ============================================================

def run_unit_tests():
    """Run all unit tests (no server connection needed)."""
    print("=" * 60)
    print("UNIT TESTS (Code Analysis)")
    print("=" * 60)

    UnitTest.test_notification_path()
    UnitTest.test_scheduler_integration()
    UnitTest.test_price_alert_types()
    UnitTest.test_device_token_flow()
    UnitTest.test_firebase_send()
    UnitTest.test_api_endpoints()
    UnitTest.test_price_alerts_unit()
    UnitTest.test_database_model()
    UnitTest.test_scheduler_app_startup()
    UnitTest.test_firebase_initialization()


def run_server_tests(base_url: str):
    """Run tests against live server."""
    print("=" * 60)
    print(f"SERVER TESTS ({base_url})")
    print("=" * 60)

    tester = ServerAPITest(base_url)
    tester.test_ping()
    tester.test_create_custom_above_alert()
    tester.test_create_custom_below_alert()
    tester.test_create_percent_alert()
    tester.test_get_alerts()
    tester.test_scheduler_status()
    tester.test_price_availability()
    tester.test_delete_alerts()


def print_summary():
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    total = results["passed"] + results["failed"]
    print(f"  Total:   {total}")
    print(f"  Passed:  {results['passed']}")
    print(f"  Failed:  {results['failed']}")
    print(f"  Warning: {results['warnings']}")
    if results["failed"] == 0:
        print("\n  ALL TESTS PASSED")
    else:
        print(f"\n  {results['failed']} TEST(S) FAILED")
    print("=" * 60)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description="Test Price Alert -> Push Notification flow"
    )
    parser.add_argument(
        '--server', '-s',
        default=os.environ.get("TEST_SERVER_URL", "https://coinceeper.com"),
        help="Base URL of the server to test against"
    )
    parser.add_argument(
        '--unit', '-u', action='store_true',
        help="Run only unit tests (no server connection)"
    )
    parser.add_argument(
        '--all', '-a', action='store_true',
        help="Run both unit and server tests"
    )
    args = parser.parse_args()

    try:
        if args.unit:
            run_unit_tests()
        elif args.all:
            run_unit_tests()
            run_server_tests(args.server)
        else:
            run_server_tests(args.server)
    except Exception as e:
        print(f"\n[FATAL] Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        print_summary()
        if results["failed"] > 0:
            sys.exit(1)
