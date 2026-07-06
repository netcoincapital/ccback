"""
Tron Comprehensive Test Suite
==============================
تست جامع برای تمام اجزای ترون (TRX, TRC10, TRC20).

این فایل شامل تست‌های واحد (unit tests) با mock است.
برای تست real-time روی Shasta Testnet به فایل scripts/test_tron_shasta.py مراجعه کنید.

اجرا:
    python -m pytest tests/test_tron_comprehensive.py -v
    python -m unittest tests.test_tron_comprehensive -v
"""

import unittest
from unittest.mock import Mock, patch, PropertyMock, MagicMock, call
from decimal import Decimal
import importlib.util
import json
import os
import sys
import time
from datetime import datetime, timedelta

# ---------------------------------------------------------------------------
# Helper: resolve project root
# ---------------------------------------------------------------------------
_PROJ = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _PROJ not in sys.path:
    sys.path.insert(0, _PROJ)


# ---------------------------------------------------------------------------
# Helper: import a module by file path without triggering package __init__
# ---------------------------------------------------------------------------
def _import_file(mod_name: str, file_path: str):
    """Import a module from a file path directly, bypassing package __init__.py."""
    spec = importlib.util.spec_from_file_location(mod_name, file_path)
    if spec is None:
        raise ImportError(f"Could not load spec for {mod_name} at {file_path}")
    mod = importlib.util.module_from_spec(spec)
    # Don't exec in the parent package context to avoid __init__
    # But we still need to be able to resolve relative intra-package imports.
    # Instead, temporarily add the file's directory to sys.path.
    old_path = sys.path.copy()
    spec.loader.exec_module(mod)
    sys.path[:] = old_path
    return mod


# ===================================================================
# 1.  Address Conversion  (webhook/chains/trx/utils.py)
# ===================================================================
class TestTronAddressConversion(unittest.TestCase):
    """تست توابع تبدیل آدرس ترون (Base58 ↔ Hex)."""

    maxDiff = None

    @classmethod
    def setUpClass(cls):
        # Direct import via file path to avoid webhook/__init__.py cascade
        import base58
        _mod = _import_file(
            "tron_utils",
            os.path.join(_PROJ, "webhook", "chains", "trx", "utils.py"),
        )
        cls.to_hex = staticmethod(_mod.tron_address_to_hex)
        cls.to_base58 = staticmethod(_mod.hex_to_tron_address)

        # Generate GUARANTEED valid test vectors dynamically:
        #   Base58Check(0x41 + 20 random bytes) gives a valid Tron address.
        cls.HEX_1 = "41a614f803b6fd780986a42c78ec9c7f77e6de13ea"
        cls.HEX_2 = "41e552f6487585c2b58bc2c9bb4492bc1f17132f70"
        cls.B58_1 = base58.b58encode_check(bytes.fromhex(cls.HEX_1)).decode()
        cls.B58_2 = base58.b58encode_check(bytes.fromhex(cls.HEX_2)).decode()

    # ---------- Base58 → Hex ----------
    def test_to_hex_valid(self):
        result = self.to_hex(self.B58_1)
        self.assertEqual(result, self.HEX_1)

    def test_to_hex_shasta_faucet(self):
        result = self.to_hex(self.B58_2)
        self.assertEqual(result, self.HEX_2)

    def test_to_hex_invalid_short(self):
        self.assertIsNone(self.to_hex("T123"))

    def test_to_hex_invalid_wrong_prefix(self):
        self.assertIsNone(self.to_hex("0xabcd"))
        self.assertIsNone(self.to_hex("41abcd"))

    def test_to_hex_empty(self):
        self.assertIsNone(self.to_hex(""))
        self.assertIsNone(self.to_hex(None))

    # ---------- Hex → Base58 ----------
    def test_to_base58_valid(self):
        result = self.to_base58(self.HEX_1)
        self.assertEqual(result, self.B58_1)

    def test_to_base58_faucet(self):
        result = self.to_base58(self.HEX_2)
        self.assertEqual(result, self.B58_2)

    def test_to_base58_with_0x_prefix(self):
        result = self.to_base58("0x" + self.HEX_1)
        self.assertEqual(result, self.B58_1)

    def test_to_base58_invalid(self):
        self.assertIsNone(self.to_base58(""))
        self.assertIsNone(self.to_base58(None))
        self.assertIsNone(self.to_base58("T123"))

    def test_roundtrip(self):
        intermediate = self.to_hex(self.B58_1)
        result = self.to_base58(intermediate)
        self.assertEqual(result, self.B58_1)


# ===================================================================
# 2.  Core Services
# ===================================================================
class TestTronServiceCore(unittest.TestCase):
    """تست سرویس اصلی ترون (با mock)."""

    @classmethod
    def setUpClass(cls):
        from services.blockchains.tron_service import TronService
        cls.service_cls = TronService

    def setUp(self):
        self.env_patcher = patch.dict("os.environ", {
            "TRON_NODE_URL": "https://api.trongrid.io",
        })
        self.env_patcher.start()

        self.tron_patcher = patch("services.blockchains.tron_service.Tron")
        self.mock_tron = self.tron_patcher.start()
        self.mock_client = MagicMock()
        self.mock_client.is_address.return_value = True
        self.mock_tron.return_value = self.mock_client

        self.logger_patcher = patch("services.blockchains.tron_service.get_logger")
        self.mock_get_logger = self.logger_patcher.start()
        self.mock_get_logger.return_value = MagicMock()

        self.tatum_patcher = patch("services.blockchains.tron_service.TatumHelper")
        self.mock_tatum = self.tatum_patcher.start()

        self.service = self.service_cls()
        self.service.tron_available = True

        # Patch SessionLocal at the place it's imported in the function
        # tron_service.py imports: from database import SessionLocal
        self.db_patcher = patch("database.SessionLocal")
        self.mock_db_session = self.db_patcher.start()
        self.mock_db_session.return_value.__enter__.return_value = MagicMock()

    def tearDown(self):
        self.env_patcher.stop()
        self.tron_patcher.stop()
        self.logger_patcher.stop()
        self.tatum_patcher.stop()
        self.db_patcher.stop()

    VALID_ADDR = "TJCnKsPa7y5wG4R9P7Jm6G5NKeP4H5c5qK"

    # ---------- Address Validation ----------
    def test_validate_address_valid(self):
        result = self.service.validate_address(self.VALID_ADDR)
        self.assertTrue(result)
        self.mock_client.is_address.assert_called_with(self.VALID_ADDR)

    def test_validate_address_invalid(self):
        self.mock_client.is_address.return_value = False
        result = self.service.validate_address("invalid")
        self.assertFalse(result)

    def test_validate_address_client_unavailable(self):
        self.service.tron_available = False
        addr = "T" + "A" * 33
        self.assertTrue(self.service.validate_address(addr))
        self.assertFalse(self.service.validate_address("T1234"))

    # ---------- Get Balance ----------
    def test_get_balance_via_client(self):
        self.service.client.get_account_balance.return_value = 15_000_000
        balance, err = self.service.get_balance(self.VALID_ADDR)
        self.assertIsNone(err)
        self.assertEqual(balance, Decimal("15"))

    def test_get_balance_from_database(self):
        """دریافت balance از دیتابیس."""
        mock_db = self.mock_db_session.return_value.__enter__.return_value
        mock_db.execute.return_value.fetchone.return_value = (Decimal("25.5"),)
        balance, err = self.service.get_balance(self.VALID_ADDR)
        self.assertIsNone(err)
        self.assertEqual(balance, Decimal("25.5"))

    # ---------- Estimate Fee ----------
    def test_estimate_fee_default_fallback(self):
        fee, err = self.service.estimate_fee(self.VALID_ADDR, self.VALID_ADDR, "10")
        self.assertIsNone(err)
        self.assertGreater(fee, Decimal("0"))

    # ---------- Transaction Status ----------
    def test_get_transaction_status_confirmed(self):
        self.mock_client.get_transaction.return_value = {
            "ret": [{"contractRet": "SUCCESS"}]
        }
        status, err = self.service.get_transaction_status("abc123")
        self.assertIsNone(err)
        self.assertEqual(status, "confirmed")

    def test_get_transaction_status_failed(self):
        self.mock_client.get_transaction.return_value = {
            "ret": [{"contractRet": "FAILED"}]
        }
        status, err = self.service.get_transaction_status("abc123")
        self.assertIsNone(err)
        self.assertEqual(status, "failed")


# ===================================================================
# 3.  TronGrid Proxy  (services/cache_proxy/providers/trongrid.py)
# ===================================================================
class TestTronGridProxy(unittest.TestCase):
    """تست TronGrid Proxy با mock."""

    @classmethod
    def setUpClass(cls):
        from services.cache_proxy.providers.trongrid import (
            TronGridProxy,
            get_trongrid_proxy,
        )
        cls.proxy_cls = TronGridProxy
        cls.get_proxy = get_trongrid_proxy

    def setUp(self):
        self.cache_patcher = patch(
            "services.cache_proxy.providers.trongrid.get_cache_layer"
        )
        self.mock_cache_layer = self.cache_patcher.start()

        self.pool_patcher = patch(
            "services.cache_proxy.providers.trongrid.get_key_pool_manager"
        )
        self.mock_pool_mgr = self.pool_patcher.start()

        self.mock_pool = MagicMock()
        self.mock_pool.get_next_key.return_value = ("test_api_key", MagicMock())
        self.mock_pool_mgr.return_value.get_pool.return_value = self.mock_pool

        self.log_patcher = patch(
            "services.cache_proxy.providers.trongrid.logger"
        )
        self.mock_log = self.log_patcher.start()

        self.proxy = self.proxy_cls(cache=MagicMock())
        self.proxy.cache.get.return_value = None

    def tearDown(self):
        self.cache_patcher.stop()
        self.pool_patcher.stop()
        self.log_patcher.stop()

    KNOWN_ACCOUNT = "TJCnKsPa7y5wG4R9P7Jm6G5NKeP4H5c5qK"

    @patch("services.cache_proxy.providers.trongrid.requests.request")
    def test_get_account(self, mock_req):
        mock_req.return_value.status_code = 200
        mock_req.return_value.json.return_value = {
            "data": [{"address": self.KNOWN_ACCOUNT, "balance": 10_000_000}]
        }
        result = self.proxy.get_account(self.KNOWN_ACCOUNT)
        self.assertIsNotNone(result)
        self.assertEqual(result["data"][0]["balance"], 10_000_000)

    @patch("services.cache_proxy.providers.trongrid.requests.request")
    def test_get_balance(self, mock_req):
        mock_req.return_value.status_code = 200
        mock_req.return_value.json.return_value = {
            "data": [{"address": self.KNOWN_ACCOUNT, "balance": 5_000_000}]
        }
        balance = self.proxy.get_balance(self.KNOWN_ACCOUNT)
        self.assertIsNotNone(balance)
        self.assertEqual(balance, 5.0)

    @patch("services.cache_proxy.providers.trongrid.requests.request")
    def test_get_trc20_transactions(self, mock_req):
        mock_req.return_value.status_code = 200
        mock_req.return_value.json.return_value = {
            "data": [
                {
                    "transaction_id": "tx1",
                    "token_info": {"symbol": "USDT", "decimals": 6},
                    "value": "1000000",
                }
            ]
        }
        txs = self.proxy.get_trc20_transactions(self.KNOWN_ACCOUNT, limit=10)
        self.assertIsNotNone(txs)
        self.assertEqual(len(txs), 1)
        self.assertEqual(txs[0]["token_info"]["symbol"], "USDT")

    @patch("services.cache_proxy.providers.trongrid.requests.request")
    def test_get_trc20_balance(self, mock_req):
        mock_req.return_value.status_code = 200
        mock_req.return_value.json.return_value = {
            "data": [
                {
                    "address": self.KNOWN_ACCOUNT,
                    "trc20": [
                        {"TG3XXyExBkPp9nzdajDZsozEu4BkaSJozs": "5000000"}
                    ],
                }
            ]
        }
        balance = self.proxy.get_trc20_balance(
            self.KNOWN_ACCOUNT,
            "TG3XXyExBkPp9nzdajDZsozEu4BkaSJozs",
        )
        self.assertEqual(balance, "5000000")

    @patch("services.cache_proxy.providers.trongrid.requests.request")
    def test_get_token_info_trc20(self, mock_req):
        """Endpoint /v1/contracts/ (not /v1/tokens/)."""
        mock_req.return_value.status_code = 200
        mock_req.return_value.json.return_value = {
            "data": [{
                "name": "Tether USD",
                "symbol": "USDT",
                "decimals": 6,
            }]
        }
        info = self.proxy.get_token_info("TG3XXyExBkPp9nzdajDZsozEu4BkaSJozs")
        self.assertIsNotNone(info)
        self.assertEqual(info["symbol"], "USDT")
        self.assertEqual(info["decimals"], 6)
        called_path = mock_req.call_args[1]["url"]
        self.assertIn("/v1/contracts/", called_path)

    @patch("services.cache_proxy.providers.trongrid.requests.request")
    def test_rate_limit_handling(self, mock_req):
        mock_req.return_value.status_code = 429
        result = self.proxy.get_account(self.KNOWN_ACCOUNT)
        self.assertIsNone(result)


# ===================================================================
# 4.  Tron Broadcast Provider  (tron_broadcast.py)
# ===================================================================
class TestTronBroadcastProvider(unittest.TestCase):
    """تست Broadcast Provider ترون با mock."""

    @classmethod
    def setUpClass(cls):
        from services.cache_proxy.providers.tron_broadcast import (
            TronBroadcastProvider,
            get_tron_broadcast_provider,
            _decode_tron_error,
            ProviderError,
            ProviderTimeoutError,
        )
        cls.provider_cls = TronBroadcastProvider
        cls.get_provider = get_tron_broadcast_provider
        cls.ProviderError = ProviderError
        cls.ProviderTimeoutError = ProviderTimeoutError
        # Store as a class-level reference, not bound to instance
        cls._decode = _decode_tron_error

    def setUp(self):
        self.pool_patcher = patch(
            "services.cache_proxy.providers.tron_broadcast.get_key_pool_manager"
        )
        self.mock_pool_mgr = self.pool_patcher.start()

        self.mock_pool = MagicMock()
        self.mock_pool.get_next_key.return_value = ("test_key", MagicMock())
        self.mock_pool_mgr.return_value.get_pool.return_value = self.mock_pool

        self.log_patcher = patch(
            "services.cache_proxy.providers.tron_broadcast.logger"
        )
        self.mock_log = self.log_patcher.start()

        self.provider = self.provider_cls()

    def tearDown(self):
        self.pool_patcher.stop()
        self.log_patcher.stop()

    @patch("services.cache_proxy.providers.tron_broadcast.requests.post")
    def test_broadcast_success(self, mock_post):
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {
            "result": True,
            "txid": "8a1f9a3d5b7c2e4f6a8b0c1d2e3f4a5b6c7d8e9f",
        }
        tx_id = self.provider.broadcast("0a8a010a02...signed_tx_hex...")
        self.assertEqual(tx_id, "8a1f9a3d5b7c2e4f6a8b0c1d2e3f4a5b6c7d8e9f")

    @patch("services.cache_proxy.providers.tron_broadcast.requests.post")
    def test_broadcast_rejected_sigerror(self, mock_post):
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {
            "result": False, "code": "SIGERROR", "message": "",
        }
        with self.assertRaises(self.ProviderError) as ctx:
            self.provider.broadcast("0a...bad_sig...")
        self.assertIn("signature is invalid", str(ctx.exception).lower())

    @patch("services.cache_proxy.providers.tron_broadcast.requests.post")
    def test_broadcast_rejected_no_energy(self, mock_post):
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {
            "result": False, "code": "NOT_ENOUGH_ENERGY", "message": "",
        }
        with self.assertRaises(self.ProviderError) as ctx:
            self.provider.broadcast("0a...hex...")
        self.assertIn("energy", str(ctx.exception).lower())

    @patch("services.cache_proxy.providers.tron_broadcast.requests.post")
    def test_broadcast_dup_transaction(self, mock_post):
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {
            "result": False, "code": "DUP_TRANSACTION_ERROR", "message": "",
        }
        with self.assertRaises(self.ProviderError) as ctx:
            self.provider.broadcast("0a...hex...")
        self.assertIn("duplicate", str(ctx.exception).lower())

    @patch("services.cache_proxy.providers.tron_broadcast.requests.post")
    def test_broadcast_rate_limited(self, mock_post):
        mock_post.return_value.status_code = 429
        with self.assertRaises(self.ProviderError) as ctx:
            self.provider.broadcast("0a...hex...")
        self.assertIn("rate limit", str(ctx.exception).lower())

    @patch("services.cache_proxy.providers.tron_broadcast.requests.post")
    def test_broadcast_http_500(self, mock_post):
        mock_post.return_value.status_code = 500
        mock_post.return_value.text = "Internal Server Error"
        with self.assertRaises(self.ProviderError) as ctx:
            self.provider.broadcast("0a...hex...")
        self.assertIn("500", str(ctx.exception))

    @patch("services.cache_proxy.providers.tron_broadcast.requests.post")
    def test_broadcast_timeout(self, mock_post):
        from requests import Timeout
        mock_post.side_effect = Timeout("Connection timed out")
        with self.assertRaises(self.ProviderTimeoutError) as ctx:
            self.provider.broadcast("0a...hex...")
        self.assertIn("timed out", str(ctx.exception).lower())

    def test_health_check_active(self):
        self.mock_pool.total_keys = 12
        self.mock_pool.available_keys = 10
        health = self.provider.check_health()
        self.assertEqual(health["status"], "active")
        self.assertEqual(health["total_keys"], 12)
        self.assertEqual(health["available_keys"], 10)

    def test_health_check_disabled(self):
        self.mock_pool_mgr.return_value.get_pool.return_value = None
        provider = self.provider_cls()
        health = provider.check_health()
        self.assertEqual(health["status"], "disabled")

    # ---------- Error Decoding (using module function directly) ----------
    def test_decode_error_by_code(self):
        msg = TestTronBroadcastProvider._decode("", "SIGERROR")
        self.assertIn("signature is invalid", msg.lower())

        msg = TestTronBroadcastProvider._decode("", "NOT_ENOUGH_ENERGY")
        self.assertIn("energy", msg.lower())
        self.assertIn("stake", msg.lower())

        msg = TestTronBroadcastProvider._decode("", "ACCOUNT_NOT_EXIST_ERROR")
        self.assertIn("does not exist", msg.lower())

    def test_decode_error_hex_message(self):
        hex_msg = "436f6e74726163742076616c6964617465206572726f72203a20544f4f5f4249475f5452414e53414354494f4e"
        msg = TestTronBroadcastProvider._decode(hex_msg, "")
        self.assertIn("rejected", msg.lower())
        # The hex decodes to "Contract validate error : TOO_BIG_TRANSACTION"
        self.assertIn("too_big", msg.lower())

    def test_decode_error_fallback(self):
        msg = TestTronBroadcastProvider._decode("some random error", "")
        self.assertIn("rejected", msg.lower())

        msg = TestTronBroadcastProvider._decode("", "")
        self.assertIn("rejected", msg.lower())


# ===================================================================
# 5.  Webhook Processor  (webhook/chains/trx/processor.py)
#     Imported via file path to avoid webhook/__init__.py cascade
# ===================================================================
class TestTronWebhookProcessor(unittest.TestCase):
    """تست پردازشگر وب‌هوک ترون."""

    @classmethod
    def setUpClass(cls):
        # Pre-patch heavy dependencies so the processor import doesn't cascade
        # into firebase_admin, database, etc.
        if "firebase_admin" not in sys.modules:
            sys.modules["firebase_admin"] = MagicMock()
        if "firebase_admin.credentials" not in sys.modules:
            sys.modules["firebase_admin.credentials"] = MagicMock()
        if "requests_firebase" not in sys.modules:
            sys.modules["requests_firebase"] = MagicMock()

        _mod = _import_file(
            "tron_processor",
            os.path.join(_PROJ, "webhook", "chains", "trx", "processor.py"),
        )
        cls.processor_cls = _mod.TronProcessor

        # Register under the canonical package name so @patch() resolves correctly.
        sys.modules["webhook.chains.trx.processor"] = _mod
        # Also register the parent modules that were loaded during import
        if "CC.webhook.transaction_processor" in sys.modules:
            sys.modules["webhook.transaction_processor"] = sys.modules["CC.webhook.transaction_processor"]

    def setUp(self):
        # Patch DatabaseOperations at the module where TronProcessor's parent class
        # imports it (TransactionProcessor.__init__ → DatabaseOperations()).
        self.op_patcher = patch(
            "webhook.transaction_processor.DatabaseOperations"
        )
        self.mock_db_ops = self.op_patcher.start()

        self.log_patcher = patch(
            "webhook.chains.trx.processor.logger"
        )
        self.mock_log = self.log_patcher.start()

        self.mock_engine = MagicMock()
        self.mock_db_ops.return_value._get_engine.return_value = self.mock_engine

        self.processor = self.processor_cls()

        # Override instance methods to avoid real network calls
        self.processor._get_tron_transaction_fee = MagicMock(return_value=0.01)
        self.processor._get_tron_price = MagicMock(return_value=0.12)

    def tearDown(self):
        self.op_patcher.stop()
        self.log_patcher.stop()

    # ---------- Get Transaction Fee ----------
    @patch("webhook.chains.trx.processor.requests.post")
    def test_get_fee_from_fullnode_api(self, mock_post):
        """POST /wallet/gettransactioninfobyid."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"fee": 50000}
        mock_post.return_value = mock_resp

        # Use patch.object on the instance to restore the real method
        with patch.object(self.processor, "_get_tron_transaction_fee",
                          self.processor_cls._get_tron_transaction_fee.__get__(
                              self.processor, self.processor_cls)):
            fee = self.processor._get_tron_transaction_fee("abc123")
        self.assertEqual(fee, 0.05)
        called_url = mock_post.call_args[0][0]
        self.assertIn("/wallet/gettransactioninfobyid", called_url)

    @patch("webhook.chains.trx.processor.requests.post")
    @patch("webhook.chains.trx.processor.requests.get")
    def test_get_fee_fallback_tronscan(self, mock_get, mock_post):
        mock_post.return_value.status_code = 500
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {"cost": {"fee": 30000}}

        with patch.object(self.processor, "_get_tron_transaction_fee",
                          self.processor_cls._get_tron_transaction_fee.__get__(
                              self.processor, self.processor_cls)):
            fee = self.processor._get_tron_transaction_fee("abc123")
        self.assertEqual(fee, 0.03)

    @patch("webhook.chains.trx.processor.requests.post")
    def test_get_fee_with_apikey(self, mock_post):
        with patch.dict("os.environ", {"TRONGRID_API_KEY": "my_test_key"}):
            mock_post.return_value.status_code = 200
            mock_post.return_value.json.return_value = {"fee": 100000}
            with patch.object(self.processor, "_get_tron_transaction_fee",
                              self.processor_cls._get_tron_transaction_fee.__get__(
                                  self.processor, self.processor_cls)):
                self.processor._get_tron_transaction_fee("abc123")
            headers = mock_post.call_args[1].get("headers", {})
            self.assertEqual(headers.get("TRON-PRO-API-KEY"), "my_test_key")

    # ---------- Webhook Processing ----------
    def test_process_trx_transfer(self):
        self.processor.db_operations.save_transaction = MagicMock()
        self.processor._ensure_token_exists_in_db = MagicMock()

        webhook_data = {
            "hash": "tx_hash_1",
            "from": "TJCnKsPa7y5wG4R9P7Jm6G5NKeP4H5c5qK",
            "to": "TZ4oY8LhB3tQgE7S4m1GAykM9Ey2XVnN9P",
            "amount": 10000000,
            "timestamp": int(time.time() * 1000),
            "block": 12345,
            "result": "CONFIRMED",
        }

        self.processor.process_webhook(webhook_data)

        self.processor.db_operations.save_transaction.assert_called_once()
        saved = self.processor.db_operations.save_transaction.call_args[0][0]
        self.assertEqual(saved["chain"], "TRX")
        self.assertEqual(saved["token_symbol"], "TRX")
        self.assertEqual(saved["amount"], 10.0)
        self.assertEqual(saved["transaction_hash"], "tx_hash_1")

    def test_process_trc20_transfer(self):
        self.processor.db_operations.save_transaction = MagicMock()
        self.processor._ensure_token_exists_in_db = MagicMock()
        self.processor._get_token_info_from_contract = MagicMock(
            return_value=("USDT", 6)
        )
        self.processor._get_token_symbol_from_contract = MagicMock(
            return_value="UNKNOWN"
        )

        webhook_data = {
            "hash": "tx_hash_trc20",
            "from": "TJCnKsPa7y5wG4R9P7Jm6G5NKeP4H5c5qK",
            "to": "TZ4oY8LhB3tQgE7S4m1GAykM9Ey2XVnN9P",
            "trigger_info": {
                "contract_address": "TG3XXyExBkPp9nzdajDZsozEu4BkaSJozs",
                "parameter": {"_value": "5000000"},
            },
            "timestamp": int(time.time() * 1000),
            "block": 12346,
            "result": "CONFIRMED",
        }

        self.processor.process_webhook(webhook_data)

        self.processor.db_operations.save_transaction.assert_called_once()
        saved = self.processor.db_operations.save_transaction.call_args[0][0]
        self.assertEqual(saved["token_symbol"], "USDT")
        self.assertEqual(saved["token_contract"], "TG3XXyExBkPp9nzdajDZsozEu4BkaSJozs")
        self.assertEqual(saved["amount"], 5.0)

    def test_process_trc10_transfer(self):
        self.processor.db_operations.save_transaction = MagicMock()
        self.processor._ensure_token_exists_in_db = MagicMock()

        webhook_data = {
            "hash": "tx_hash_trc10",
            "from": "TJCnKsPa7y5wG4R9P7Jm6G5NKeP4H5c5qK",
            "to": "TZ4oY8LhB3tQgE7S4m1GAykM9Ey2XVnN9P",
            "tokenInfo": {
                "tokenId": "1000001",
                "symbol": "TEST_TRC10",
                "decimal": 6,
            },
            "amount": 2000000,
            "timestamp": int(time.time() * 1000),
            "block": 12347,
            "result": "CONFIRMED",
        }

        self.processor.process_webhook(webhook_data)

        self.processor.db_operations.save_transaction.assert_called_once()
        saved = self.processor.db_operations.save_transaction.call_args[0][0]
        self.assertEqual(saved["token_symbol"], "TEST_TRC10")
        self.assertEqual(saved["token_contract"], "1000001")
        self.assertEqual(saved["amount"], 2.0)


# ===================================================================
# 6.  V3 Routes — Broadcast Endpoint  (routes_v3.py)
# ===================================================================
class TestTronBroadcastRoute(unittest.TestCase):
    """تست endpoint broadcast در V3 routes."""

    def test_error_response_contains_provider_name(self):
        from services.cache_proxy.providers.tron_broadcast import ProviderError
        try:
            raise ProviderError("TronGrid", "Test error")
        except ProviderError as e:
            self.assertEqual(e.status_code, 502)
            self.assertIn("TronGrid", str(e))


# ===================================================================
# 7.  FullNode API — Transaction Status & Details
# ===================================================================
class TestTronFullNodeEndpoints(unittest.TestCase):
    """تست interaction با FullNode API (wallet/gettransactionbyid و ...)."""

    @classmethod
    def setUpClass(cls):
        from services.blockchains.tron_service import TronService
        cls.service_cls = TronService

    def setUp(self):
        self.env_patcher = patch.dict("os.environ", {
            "TRON_NODE_URL": "https://api.trongrid.io",
        })
        self.env_patcher.start()

        self.tron_patcher = patch("services.blockchains.tron_service.Tron")
        self.mock_tron = self.tron_patcher.start()
        self.mock_client = MagicMock()
        self.mock_tron.return_value = self.mock_client

        self.logger_patcher = patch("services.blockchains.tron_service.get_logger")
        self.logger_patcher.start()

        self.tatum_patcher = patch("services.blockchains.tron_service.TatumHelper")
        self.tatum_patcher.start()

        # Patch SessionLocal for this class too
        self.db_patcher = patch("database.SessionLocal")
        self.db_patcher.start()

        self.service = self.service_cls()
        self.service.tron_available = True

    def tearDown(self):
        self.env_patcher.stop()
        self.tron_patcher.stop()
        self.logger_patcher.stop()
        self.tatum_patcher.stop()
        self.db_patcher.stop()

    def test_get_transaction_details(self):
        self.mock_client.get_transaction.return_value = {
            "ret": [{"contractRet": "SUCCESS"}],
            "raw_data": {
                "contract": [{
                    "parameter": {
                        "value": {
                            "owner_address": "41a614f803b6fd780986a42c78ec9c7f77e6de13ea",
                            "to_address": "41e552f6487585c2b58bc2c9bb4492bc1f17132f70",
                            "amount": 10000000,
                        }
                    }
                }],
                "timestamp": 1700000000000,
            },
        }
        details, err = self.service.get_transaction_details("abc123")
        self.assertIsNone(err)
        self.assertIsNotNone(details)
        self.assertIn("from", details)
        self.assertIn("to", details)
        self.assertIn("value", details)
        self.assertIn("status", details)
        self.assertEqual(details["status"], "confirmed")
        self.assertEqual(details["value"], "10")


# ===================================================================
# 8.  Fee Estimator Integration  (fee_estimator/tron.py)
# ===================================================================
class TestTronFeeEstimator(unittest.TestCase):
    """تست Fee Estimator ترون."""

    @classmethod
    def setUpClass(cls):
        from fee_estimator.tron import TronFeeEstimator
        cls.estimator_cls = TronFeeEstimator

    def setUp(self):
        self.estimator = self.estimator_cls()

    @patch("fee_estimator.tron.TronFeeEstimator._check_account_exists")
    @patch("fee_estimator.tron.TronFeeEstimator._get_account_info")
    @patch("fee_estimator.tron.TronFeeEstimator._get_trx_usd_price")
    def test_estimate_trx_fee_existing_account(
        self, mock_price, mock_account_info, mock_exists
    ):
        """Free bandwidth available → fee 0 or min."""
        mock_exists.return_value = True
        mock_account_info.return_value = {
            "freeNetUsed": 0,
            "freeNetLimit": 5000,
        }
        mock_price.return_value = 0.12

        result = self.estimator.estimate_native_fee(
            "TJCnKsPa7y5wG4R9P7Jm6G5NKeP4H5c5qK",
            "TZ4oY8LhB3tQgE7S4m1GAykM9Ey2XVnN9P",
            10.0,
        )
        self.assertIn("fee", result)
        self.assertIn("bandwidth_fee", result)
        # Free bandwidth is enough (5000 > 300 needed), so fee should be 0
        self.assertEqual(result.get("fee"), 0)
        self.assertEqual(result.get("activation_fee", 0), 0)

    @patch("fee_estimator.tron.TronFeeEstimator._check_account_exists")
    @patch("fee_estimator.tron.TronFeeEstimator._get_account_info")
    @patch("fee_estimator.tron.TronFeeEstimator._get_trx_usd_price")
    def test_estimate_trx_fee_new_account(
        self, mock_price, mock_account_info, mock_exists
    ):
        """Activation fee (1 TRX) for new accounts."""
        mock_exists.return_value = False
        mock_account_info.return_value = {
            "freeNetUsed": 0,
            "freeNetLimit": 5000,
        }
        mock_price.return_value = 0.12

        result = self.estimator.estimate_native_fee(
            "TJCnKsPa7y5wG4R9P7Jm6G5NKeP4H5c5qK",
            "TZ4oY8LhB3tQgE7S4m1GAykM9Ey2XVnN9P",
            10.0,
        )
        # Activation fee should be 1 TRX (1_000_000 SUN)
        self.assertEqual(result.get("activation_fee"), 1_000_000)
        # Total fee = activation (1_000_000) + bandwidth (0 if free available)
        self.assertGreaterEqual(result.get("fee", 0), 1_000_000)

    @patch("fee_estimator.tron.TronFeeEstimator._check_is_trc20_token", return_value=True)
    @patch("fee_estimator.tron.TronFeeEstimator._check_account_exists", return_value=True)
    @patch("fee_estimator.tron.TronFeeEstimator._get_account_info")
    @patch("fee_estimator.tron.TronFeeEstimator._get_trx_usd_price")
    def test_estimate_trc20_fee(
        self, mock_price, mock_account_info, mock_exists, mock_is_trc20
    ):
        """Energy needed for TRC20 (no staked energy)."""
        mock_account_info.return_value = {
            "EnergyLimit": 0,
            "EnergyUsed": 0,
        }
        mock_price.return_value = 0.12

        result = self.estimator.estimate_token_fee(
            "TJCnKsPa7y5wG4R9P7Jm6G5NKeP4H5c5qK",
            "TZ4oY8LhB3tQgE7S4m1GAykM9Ey2XVnN9P",
            5.0,
            "TG3XXyExBkPp9nzdajDZsozEu4BkaSJozs",
        )
        self.assertIn("fee", result)
        self.assertIn("energy_fee", result)
        self.assertGreater(result["energy_fee"], 0)


# ===================================================================
# Run All
# ===================================================================
if __name__ == "__main__":
    unittest.main(verbosity=2)
