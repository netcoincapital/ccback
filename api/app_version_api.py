"""
App Version API
=================
ارسال آخرین نسخه مورد نیاز اپلیکیشن برای هر پلتفرم.
فرانت‌اند از این endpoint برای تشخیص آپدیت اجباری استفاده می‌کند.

Endpoints:
  GET /api/app/version  ← نسخه مورد نیاز + لینک آپدیت
"""
import os
import json
from flask import Blueprint, jsonify, send_file
from utils.logging_config import get_logger

logger = get_logger(__name__)

app_version_bp = Blueprint('app_version', __name__)

# مسیر فایل تنظیمات نسخه
_VERSION_CONFIG_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    'config',
    'app_version.json'
)

_last_mtime = 0
_version_cache = None


def _load_version_config():
    """بارگذاری تنظیمات نسخه از فایل JSON با invalidate خودکار."""
    global _version_cache, _last_mtime
    try:
        current_mtime = os.path.getmtime(_VERSION_CONFIG_PATH)
        if _version_cache is not None and current_mtime <= _last_mtime:
            return _version_cache

        with open(_VERSION_CONFIG_PATH, 'r', encoding='utf-8') as f:
            _version_cache = json.load(f)
        _last_mtime = current_mtime
        logger.info(f"App version config loaded: {_version_cache}")
        return _version_cache
    except Exception as e:
        logger.error(f"Failed to load app version config: {e}")
        return None


@app_version_bp.route('/app/version', methods=['GET'])
def get_app_version():
    """
    دریافت اطلاعات آخرین نسخه اپلیکیشن.

    Returns:
        JSON با نسخه‌های مورد نیاز برای هر پلتفرم:
        {
            "success": true,
            "android": {
                "min_version": "1.0.0",
                "latest_version": "1.0.1",
                "update_url": "https://play.google.com/..."
            },
            "ios": {
                "min_version": "1.0.0",
                "latest_version": "1.0.1",
                "update_url": "https://apps.apple.com/..."
            },
            "force_update_message": {
                "title": "...",
                "body": "..."
            },
            "optional_update_message": {
                "title": "...",
                "body": "..."
            }
        }
    """
    config = _load_version_config()
    if not config:
        return jsonify({
            "success": False,
            "message": "Version configuration not available"
        }), 500

    return jsonify({
        "success": True,
        "android": config.get("android", {}),
        "ios": config.get("ios", {}),
        "force_update_message": config.get("force_update_message", {}),
        "optional_update_message": config.get("optional_update_message", {}),
    })


@app_version_bp.route('/app/version/update-config', methods=['POST'])
def update_version_config():
    """
    آپدیت تنظیمات نسخه (برای ادمین/دیپلوی).

    Body:
    {
        "platform": "android" | "ios",
        "min_version": "1.2.0",
        "latest_version": "1.2.5",
        "update_url": "https://..."
    }
    """
    from flask import request

    data = request.get_json() or {}
    platform = data.get('platform')
    if platform not in ('android', 'ios'):
        return jsonify({
            "success": False,
            "message": "Platform must be 'android' or 'ios'"
        }), 400

    config = _load_version_config()
    if not config:
        return jsonify({"success": False, "message": "Cannot load config"}), 500

    # بروزرسانی فیلدهای ارسال شده
    if platform in config:
        if 'min_version' in data:
            config[platform]['min_version'] = data['min_version']
        if 'latest_version' in data:
            config[platform]['latest_version'] = data['latest_version']
        if 'update_url' in data:
            config[platform]['update_url'] = data['update_url']

    # ذخیره در فایل
    try:
        with open(_VERSION_CONFIG_PATH, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        _load_version_config()  # فوراً کش رو آپدیت کن
        logger.info(f"App version config updated for {platform}: {data}")
        return jsonify({
            "success": True,
            "message": f"Version config updated for {platform}",
            "config": config.get(platform)
        })
    except Exception as e:
        logger.error(f"Failed to save version config: {e}")
        return jsonify({
            "success": False,
            "message": f"Failed to save: {str(e)}"
        }), 500
