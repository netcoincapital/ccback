"""
Cache Proxy API — V2 Public Endpoints
=======================================

این Blueprint شامل endpointهای عمومی v2 است که:
- بدون UserID کار می‌کنند (Non-Custodial)
- از RAM کش می‌دهند (مقیاس‌پذیر)
- داده‌های خود را از CoinGecko / Public RPC / Block Explorer می‌گیرند (رایگان)

Endpoints:
GET  /api/v2/prices          — قیمت لحظه‌ای همه ارزها
GET  /api/v2/prices/<symbol> — قیمت یک ارز خاص
GET  /api/v2/chart           — داده‌های نمودار
GET  /api/v2/gas             — کارمزد شبکه‌ها
GET  /api/v2/coins           — لیست همه ارزها (صفحه‌بندی شده)
GET  /api/v2/notifications   — نوتیفیکیشن تراکنش‌ها (Active Address Registry)
GET  /api/v2/health          — وضعیت کش
GET  /api/v2/airdrops        — لیست airdropها (از CryptoRank)
GET  /api/v2/airdrops/<id>   — جزئیات یک airdrop
GET  /api/v2/airdrops/<id>/tasks — وظایف یک airdrop
"""

from datetime import datetime, timezone
from decimal import Decimal
from typing import Dict, Optional

from flask import Blueprint, jsonify, request
from utils.logging_config import get_logger

from .price_cache import get_price_cache
from .chart_cache import get_chart_cache
from .gas_cache import get_gas_cache
from .coin_cache import get_coin_cache
from .block_scanner import mark_active, get_cached_txs, get_cache_stats, get_last_scanned
from .airdrop_cache import get_airdrop_cache

logger = get_logger(__file__)

# ============================================================
# Token symbol mapping: blockchain display name → native coin symbol
# ============================================================
BLOCKCHAIN_NATIVE_SYMBOL: Dict[str, str] = {
    "Ethereum": "ETH",
    "BSC": "BNB",
    "Polygon": "POL",
    "Avalanche": "AVAX",
    "Arbitrum": "ARB",
    "Optimism": "OP",
    "Tron": "TRX",
    "Solana": "SOL",
    "Bitcoin": "BTC",
    "XRP": "XRP",
    "Polkadot": "DOT",
}

# Native coin decimals per blockchain
BLOCKCHAIN_DECIMALS: Dict[str, int] = {
    "Ethereum": 18,
    "BSC": 18,
    "Polygon": 18,
    "Avalanche": 18,
    "Arbitrum": 18,
    "Optimism": 18,
    "Tron": 6,       # SUN → TRX
    "Solana": 9,     # Lamports → SOL
    "Bitcoin": 8,    # Satoshis → BTC
    "XRP": 6,        # Drops → XRP
    "Polkadot": 10,  # Planck → DOT
}


def _format_amount(tx: Dict) -> str:
    """
    تبدیل مقدار خام تراکنش به فرمت خواندنی (DECIMAL).
    بسته به بلاکچین، واحد پایه متفاوت است:
      - EVM: wei → 10^18
      - Tron: SUN → 10^6
      - Solana: lamports → 10^9
      - Bitcoin: satoshis → 10^8
    """
    blockchain = tx.get("blockchain", "")
    decimals = BLOCKCHAIN_DECIMALS.get(blockchain, 18)

    raw_value: Optional[int] = None
    # EVM chains — value_wei از RPC به صورت هگز یا عدد صحیح
    value_wei = tx.get("value_wei")
    if value_wei is not None:
        if isinstance(value_wei, str):
            if value_wei.startswith("0x"):
                raw_value = int(value_wei, 16)
            else:
                try:
                    raw_value = int(value_wei)
                except ValueError:
                    raw_value = 0
        else:
            raw_value = int(value_wei)

    # Tron — SUN
    if raw_value is None:
        value_sun = tx.get("value_sun")
        if value_sun is not None:
            raw_value = int(value_sun)

    # Bitcoin — Satoshis
    if raw_value is None:
        value_sat = tx.get("value_sat")
        if value_sat is not None:
            raw_value = int(value_sat)

    # Solana — Lamports
    if raw_value is None:
        value_lamports = tx.get("value_lamports")
        if value_lamports is not None:
            raw_value = int(value_lamports)

    if raw_value is None or raw_value == 0:
        return "0"

    divisor = 10 ** decimals
    amount = Decimal(raw_value) / Decimal(divisor)
    # فرمت: حذف صفرهای اضافی (مثلاً 0.500000 → 0.5)
    formatted = f"{amount:.{decimals}f}"
    if "." in formatted:
        formatted = formatted.rstrip("0").rstrip(".")
    return formatted


def _get_token_symbol(tx: Dict) -> str:
    """دریافت سمبل توکن (نیتیو کوین یا توکن) برای یک تراکنش."""
    # اگر token_symbol از قبل ذخیره شده، مستقیماً برگردان
    stored = tx.get("token_symbol")
    if stored:
        return stored

    # نیتیو کوین بر اساس نام بلاکچین
    blockchain = tx.get("blockchain", "")
    return BLOCKCHAIN_NATIVE_SYMBOL.get(blockchain, blockchain.upper())

cache_proxy_bp = Blueprint("cache_proxy_v2", __name__, url_prefix="/api/v2")


# ===================== قیمت لحظه‌ای =====================


@cache_proxy_bp.route("/prices", methods=["GET"])
@cache_proxy_bp.route("/prices/", methods=["GET"])
def get_prices():
    """
    دریافت قیمت لحظه‌ای همه ارزهای پشتیبانی شده.

    این endpoint عمومی است و نیازی به UserID ندارد.
    داده‌ها از CoinGecko (رایگان) هر ۲ دقیقه یکبار کش می‌شوند.

    Query Parameters:
        symbol (str, optional): فیلتر بر اساس سمبل (مثلاً ?symbol=BTC)
        currency (str, optional): ارز مرجع (پیش‌فرض: USD)

    Returns:
        200: قیمت‌ها
    """
    try:
        pc = get_price_cache()
        all_prices = pc.get_all_prices()

        symbol_filter = request.args.get("symbol", "").upper()
        if symbol_filter:
            symbol_filter = symbol_filter.strip()
            if symbol_filter in all_prices:
                result = {symbol_filter: all_prices[symbol_filter]}
            else:
                result = {}
        else:
            result = all_prices

        # تبدیل قیمت به ارزهای فیات (اختیاری)
        currency = request.args.get("currency", "USD").upper()
        if currency != "USD":
            fiat_rate = _get_fiat_rate(currency)
            if fiat_rate and fiat_rate != 1.0:
                converted = {}
                for sym, data in result.items():
                    converted[sym] = dict(data)
                    if "price" in converted[sym] and converted[sym]["price"] is not None:
                        converted[sym]["price"] = round(
                            converted[sym]["price"] * fiat_rate, 8
                        )
                    if "market_cap" in converted[sym] and converted[sym]["market_cap"] is not None:
                        converted[sym]["market_cap"] = round(
                            converted[sym]["market_cap"] * fiat_rate, 2
                        )
                    converted[sym]["currency"] = currency
                    converted[sym]["fiat_rate"] = fiat_rate
                result = converted

        return jsonify({
            "success": True,
            "prices": result,
            "count": len(result),
            "cache_age_seconds": pc.get_age_seconds(),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "note": "Non-custodial: no UserID required. Data cached from CoinGecko.",
        }), 200

    except Exception as e:
        logger.error("v2/prices error: %s", e, exc_info=True)
        return jsonify({
            "success": False,
            "error": str(e),
        }), 500


@cache_proxy_bp.route("/prices/<symbol>", methods=["GET"])
def get_price_by_symbol(symbol: str):
    """
    دریافت قیمت یک ارز خاص.

    Args:
        symbol: سمبل ارز (مثلاً BTC, ETH, TRX)

    Returns:
        200: قیمت ارز
        404: ارز پیدا نشد
    """
    try:
        pc = get_price_cache()
        price_data = pc.get_price(symbol.upper())

        if price_data is None:
            return jsonify({
                "success": False,
                "error": f"Symbol '{symbol.upper()}' not found",
            }), 404

        return jsonify({
            "success": True,
            "symbol": symbol.upper(),
            "price": price_data,
            "cache_age_seconds": pc.get_age_seconds(),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }), 200

    except Exception as e:
        logger.error("v2/prices/%s error: %s", symbol, e, exc_info=True)
        return jsonify({
            "success": False,
            "error": str(e),
        }), 500


# ===================== داده‌های نمودار =====================


@cache_proxy_bp.route("/chart", methods=["GET"])
def get_chart():
    """
    دریافت داده‌های نمودار (قیمت تاریخی) برای یک ارز.

    Query Parameters:
        symbol (str): سمبل ارز (الزامی)
        days (int, optional): تعداد روز (پیش‌فرض: 7)
        currency (str, optional): ارز مرجع (پیش‌فرض: USD)

    Returns:
        200: داده‌های نمودار
        400: پارامتر symbol الزامی است
    """
    try:
        symbol = request.args.get("symbol", "").upper().strip()
        if not symbol:
            return jsonify({
                "success": False,
                "error": "symbol parameter is required",
            }), 400

        days_str = request.args.get("days", "7").strip()
        try:
            days = int(days_str)
            if days < 1:
                days = 1
            elif days > 365:
                days = 365
        except ValueError:
            days = 7

        cc = get_chart_cache()
        chart_data = cc.get_chart_data(symbol, days)

        if chart_data is None:
            return jsonify({
                "success": False,
                "error": f"No chart data available for '{symbol}'",
            }), 404

        return jsonify({
            "success": True,
            "chart_data": chart_data,
            "points_count": len(chart_data.get("prices", [])),
            "symbol": symbol,
            "days": days,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }), 200

    except Exception as e:
        logger.error("v2/chart error: %s", e, exc_info=True)
        return jsonify({
            "success": False,
            "error": str(e),
        }), 500


# ===================== کارمزد شبکه =====================


@cache_proxy_bp.route("/gas", methods=["GET"])
def get_gas_fees():
    """
    دریافت کارمزد (Gas Fee) برای شبکه‌های پشتیبانی شده.

    Query Parameters:
        chain (str, optional): نام شبکه (مثلاً ?chain=Ethereum)

    Returns:
        200: کارمزد شبکه‌ها
    """
    try:
        gc = get_gas_cache()
        chain_filter = request.args.get("chain", "").strip()

        if chain_filter:
            gas_data = gc.get_gas(chain_filter)
            if gas_data is None:
                return jsonify({
                    "success": False,
                    "error": f"Chain '{chain_filter}' not supported",
                    "supported_chains": list(gc.get_all_gas().keys()),
                }), 404
            result = {chain_filter: gas_data}
        else:
            result = gc.get_all_gas()

        return jsonify({
            "success": True,
            "gas_fees": result,
            "count": len(result),
            "cache_age_seconds": gc.get_age_seconds(),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }), 200

    except Exception as e:
        logger.error("v2/gas error: %s", e, exc_info=True)
        return jsonify({
            "success": False,
            "error": str(e),
        }), 500


# ===================== لیست ارزها =====================


@cache_proxy_bp.route("/coins", methods=["GET"])
def get_coins():
    """
    دریافت لیست کامل ارزهای دیجیتال با صفحه‌بندی.

    ⚠️ Non-blocking: اگر کش هنوز آماده نیست، بلافاصله با وضعیت "warming" برمی‌گردد.
    درخواست بعدی داده کامل را دریافت می‌کند.

    Query Parameters:
        search  (str, optional): جستجو در نام یا سمبل ارزها
        page    (int, optional): شماره صفحه (پیش‌فرض: 1)
        per_page(int, optional): تعداد آیتم در هر صفحه (پیش‌فرض: 50، حداکثر: 200)
        limit   (int, optional): [DEPRECATED] از per_page استفاده کنید

    Returns:
        200: لیست ارزها با متادیتای صفحه‌بندی
    """
    try:
        cc = get_coin_cache()
        search_query = request.args.get("search", "").strip()

        # اگر کش هنوز آماده نیست، بلافاصله برگردان
        if not cc.ready() and not search_query:
            return jsonify({
                "success": True,
                "coins": [],
                "count": 0,
                "page": 1,
                "per_page": 50,
                "total": 0,
                "total_pages": 0,
                "has_next": False,
                "has_prev": False,
                "cache_status": cc.get_refresh_status(),
                "cache_age_seconds": None,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "message": "Coin list is being loaded. Please retry in a few seconds.",
            }), 200

        # دریافت و اعتبارسنجی پارامترهای صفحه‌بندی
        if search_query:
            all_coins = cc.search(search_query)
        else:
            all_coins = cc.get_all_coins()

        total = len(all_coins)

        # page: پیش‌فرض 1، حداقل 1
        try:
            page = max(1, int(request.args.get("page", "1")))
        except (ValueError, TypeError):
            page = 1

        # per_page: اولویت با per_page. پشتیبانی از limit (قدیمی)
        per_page_param = request.args.get("per_page", "").strip()
        if not per_page_param:
            limit_param = request.args.get("limit", "").strip()
            per_page = min(200, max(1, int(limit_param))) if limit_param else 50
        else:
            try:
                per_page = min(200, max(1, int(per_page_param)))
            except (ValueError, TypeError):
                per_page = 50

        # محاسبه صفحه‌بندی
        total_pages = max(1, (total + per_page - 1) // per_page)
        page = min(page, total_pages)
        start = (page - 1) * per_page
        end = start + per_page
        coins_page = all_coins[start:end]

        return jsonify({
            "success": True,
            "coins": coins_page,
            "count": len(coins_page),
            "page": page,
            "per_page": per_page,
            "total": total,
            "total_pages": total_pages,
            "has_next": page < total_pages,
            "has_prev": page > 1,
            "cache_status": cc.get_refresh_status(),
            "cache_age_seconds": cc.get_age_seconds(),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }), 200

    except Exception as e:
        logger.error("v2/coins error: %s", e, exc_info=True)
        return jsonify({
            "success": False,
            "error": str(e),
        }), 500


# ===================== وضعیت سلامت =====================


@cache_proxy_bp.route("/health", methods=["GET"])
def cache_health():
    """
    بررسی وضعیت کش.
    Non-blocking: از get_age_seconds() استفاده نمی‌کند تا باعث رفرش نشود.

    Returns:
        200: وضعیت همه کش‌ها
    """
    try:
        pc = get_price_cache()
        cc = get_chart_cache()
        gc = get_gas_cache()
        coin_c = get_coin_cache()
        ac = get_airdrop_cache()
        scan_stats = get_cache_stats()

        return jsonify({
            "success": True,
            "service": "Cache Proxy V2",
            "version": "2.1.0",
            "status": "healthy",
            "caches": {
                "prices": {
                    "status": pc.get_refresh_status(),
                    "coins_count": len(pc._cache) if hasattr(pc, '_cache') else 0,
                },
                "chart": {
                    "entries": len(cc._cache) if hasattr(cc, '_cache') else 0,
                },
                "gas": {
                    "status": gc.get_refresh_status(),
                    "chains_count": len(gc._cache) if hasattr(gc, '_cache') else 0,
                },
                "coins": {
                    "status": coin_c.get_refresh_status(),
                    "coins_count": len(coin_c._cache) if hasattr(coin_c, '_cache') else 0,
                },
                "airdrops": {
                    "status": ac.get_refresh_status(),
                    "airdrops_count": ac.get_count(),
                    "data_source": "cryptorank",
                },
                "notifications": {
                    "active_addresses": scan_stats.get("active_addresses", 0),
                    "cached_transactions": scan_stats.get("cached_transactions", 0),
                    "last_scanned": scan_stats.get("last_scanned", {}),
                },
            },
            "non_custodial": True,
            "note": "All endpoints are public and require no UserID",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }), 200

    except Exception as e:
        logger.error("v2/health error: %s", e, exc_info=True)
        return jsonify({
            "success": False,
            "error": str(e),
        }), 500


# ===================== نوتیفیکیشن تراکنش‌ها =====================


@cache_proxy_bp.route("/notifications", methods=["GET"])
def get_notifications():
    """
    دریافت نوتیفیکیشن تراکنش‌های جدید برای آدرس‌های مشخص.

    Non-custodial: فقط آدرس‌های عمومی — هیچ UserID/Token لازم نیست.
    معماری Active Address Registry: فقط آدرس‌های فعال در ۵ دقیقه اخیر اسکن می‌شوند.

    Query Parameters:
        addresses (str): آدرس‌های کیف پول (comma-separated)

    Returns:
        200: لیست تراکنش‌های جدید
    """
    try:
        raw = request.args.get("addresses", "").strip()
        if not raw:
            return jsonify({
                "success": True,
                "txs": [],
                "count": 0,
                "note": "No addresses provided. Pass ?addresses=addr1,addr2,...",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }), 200

        addresses = [a.strip().lower() for a in raw.split(",") if a.strip()]
        result = []
        for addr in addresses:
            mark_active(addr)
            txs = get_cached_txs(addr)
            if txs:
                for tx in txs:
                    # backward compat: ensure blockNumber camelCase alias
                    if "block_number" in tx and "blockNumber" not in tx:
                        tx["blockNumber"] = tx["block_number"]

                    tx["address"] = addr
                    # direction detection
                    tx_to = tx.get("to", "").lower()
                    tx_from = tx.get("from", "").lower()
                    if tx_to == addr:
                        tx["direction"] = "inbound"
                    elif tx_from == addr:
                        tx["direction"] = "outbound"
                    else:
                        tx["direction"] = "unknown"

                    # amount: تبدیل مقدار خام به فرمت خواندنی
                    tx["amount"] = _format_amount(tx)

                    # tokenSymbol: تعیین سمبل توکن
                    tx["tokenSymbol"] = _get_token_symbol(tx)

                    # اطمینان از وجود from و to
                    tx.setdefault("from", "")
                    tx.setdefault("to", "")

                    result.append(tx)

        seen = set()
        unique = []
        for tx in result:
            h = tx.get("hash", "")
            if h and h not in seen:
                seen.add(h)
                unique.append(tx)

        return jsonify({
            "success": True,
            "txs": unique,
            "count": len(unique),
            "addresses_count": len(addresses),
            "last_scanned": get_last_scanned(),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "note": "Non-custodial: no UserID required. Active Address Registry + Block Scanner.",
        }), 200

    except Exception as e:
        logger.error("v2/notifications error: %s", e, exc_info=True)
        return jsonify({
            "success": False,
            "error": str(e),
        }), 500


# ===================== Airdrops (CryptoRank) =====================


@cache_proxy_bp.route("/airdrops", methods=["GET"])
@cache_proxy_bp.route("/airdrops/", methods=["GET"])
def get_airdrops():
    """
    دریافت لیست airdropها از CryptoRank.

    داده‌ها از CryptoRank API (v3/drophunting/list) کش می‌شوند.
    لیست هر ۵ دقیقه رفرش می‌شود.

    Query Parameters:
        search    (str, optional): جستجو در نام پروژه
        status    (str, optional): فیلتر بر اساس وضعیت (active, upcoming, ended)
        chain     (str, optional): فیلتر بر اساس بلاکچین
        page      (int, optional): شماره صفحه (پیش‌فرض: 1)
        per_page  (int, optional): تعداد آیتم در هر صفحه (پیش‌فرض: 20، حداکثر: 100)
        sort      (str, optional): مرتب‌سازی (name, status, reward, date)

    Returns:
        200: لیست airdropها
    """
    try:
        ac = get_airdrop_cache()
        all_airdrops = ac.get_all_airdrops()

        if not all_airdrops:
            return jsonify({
                "success": True,
                "airdrops": [],
                "count": 0,
                "total": 0,
                "page": 1,
                "per_page": 20,
                "total_pages": 0,
                "has_next": False,
                "has_prev": False,
                "cache_status": ac.get_refresh_status(),
                "cache_age_seconds": ac.get_list_age_seconds(),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }), 200

        # --- فیلترها ---
        search_query = request.args.get("search", "").strip().lower()
        status_filter = request.args.get("status", "").strip().lower()
        chain_filter = request.args.get("chain", "").strip().lower()

        filtered = all_airdrops

        # جستجو در نام پروژه
        if search_query:
            filtered = [
                a for a in filtered
                if search_query in str(a.get("name", "")).lower()
                or search_query in str(a.get("title", "")).lower()
                or search_query in a.get("id", "").lower()
            ]

        # فیلتر وضعیت
        if status_filter:
            filtered = [
                a for a in filtered
                if status_filter in str(a.get("status", "")).lower()
                or status_filter in str(a.get("rewardStatus", "")).lower()
            ]

        # فیلتر بلاکچین
        if chain_filter:
            filtered = [
                a for a in filtered
                if chain_filter in str(a.get("blockchain", "")).lower()
                or chain_filter in str(a.get("chain", "")).lower()
                or any(
                    chain_filter in str(chain).lower()
                    for chain in (a.get("blockchains", []) or [])
                )
            ]

        total = len(filtered)

        # --- صفحه‌بندی ---
        try:
            page = max(1, int(request.args.get("page", "1")))
        except (ValueError, TypeError):
            page = 1

        try:
            per_page = min(100, max(1, int(request.args.get("per_page", "20"))))
        except (ValueError, TypeError):
            per_page = 20

        total_pages = max(1, (total + per_page - 1) // per_page)
        page = min(page, total_pages)
        start = (page - 1) * per_page
        end = start + per_page
        airdrops_page = filtered[start:end]

        return jsonify({
            "success": True,
            "airdrops": airdrops_page,
            "count": len(airdrops_page),
            "total": total,
            "page": page,
            "per_page": per_page,
            "total_pages": total_pages,
            "has_next": page < total_pages,
            "has_prev": page > 1,
            "cache_status": ac.get_refresh_status(),
            "cache_age_seconds": ac.get_list_age_seconds(),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "data_source": "cryptorank",
        }), 200

    except Exception as e:
        logger.error("v2/airdrops error: %s", e, exc_info=True)
        return jsonify({
            "success": False,
            "error": str(e),
        }), 500


@cache_proxy_bp.route("/airdrops/<string:airdrop_id>", methods=["GET"])
def get_airdrop_detail(airdrop_id: str):
    """
    دریافت جزئیات یک airdrop خاص.

    Args:
        airdrop_id: شناسه airdrop

    Returns:
        200: جزئیات airdrop
        404: airdrop پیدا نشد
    """
    try:
        ac = get_airdrop_cache()
        detail = ac.get_airdrop_detail(airdrop_id)

        if detail is None:
            return jsonify({
                "success": False,
                "error": f"Airdrop '{airdrop_id}' not found or detailed data unavailable (requires upgraded CryptoRank plan)",
            }), 404

        return jsonify({
            "success": True,
            "airdrop": detail,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "data_source": "cryptorank",
        }), 200

    except Exception as e:
        logger.error("v2/airdrops/%s error: %s", airdrop_id, e, exc_info=True)
        return jsonify({
            "success": False,
            "error": str(e),
        }), 500


@cache_proxy_bp.route("/airdrops/<string:airdrop_id>/tasks", methods=["GET"])
def get_airdrop_tasks(airdrop_id: str):
    """
    دریافت لیست tasks مربوط به یک airdrop خاص.

    Args:
        airdrop_id: شناسه airdrop

    Returns:
        200: لیست tasks
        404: airdrop پیدا نشد
    """
    try:
        ac = get_airdrop_cache()
        tasks = ac.fetch_airdrop_tasks(airdrop_id)

        if tasks is None:
            return jsonify({
                "success": False,
                "error": f"Airdrop '{airdrop_id}' not found or tasks unavailable (requires upgraded CryptoRank plan)",
            }), 404

        return jsonify({
            "success": True,
            "tasks": tasks,
            "count": len(tasks),
            "airdrop_id": airdrop_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "data_source": "cryptorank",
        }), 200

    except Exception as e:
        logger.error("v2/airdrops/%s/tasks error: %s", airdrop_id, e, exc_info=True)
        return jsonify({
            "success": False,
            "error": str(e),
        }), 500


# ===================== داخلی =====================


def _get_fiat_rate(currency: str) -> float:
    """دریافت نرخ تبدیل ارز فیات از دیتابیس."""
    try:
        from sqlalchemy import text
        from database import engine

        with engine.connect() as conn:
            row = conn.execute(
                text(
                    "SELECT rate FROM fiat_rates WHERE quote_currency = :cur"
                ),
                {"cur": currency},
            ).first()
            if row:
                return float(row[0])
    except Exception as e:
        logger.debug("Fiat rate lookup failed for %s: %s", currency, e)
    return 1.0  # default to USD
