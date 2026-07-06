#!/usr/bin/env python3
"""
Update App Version Config
=========================
اسکریپت برای بروزرسانی نسخه اپلیکیشن در بک‌اند.

Usage:
  python update_app_version.py --platform android --min 1.2.0 --latest 1.2.5 --url "https://play.google.com/..."
  python update_app_version.py --platform ios --min 1.2.0 --latest 1.2.5 --url "https://apps.apple.com/..."
  python update_app_version.py --status
"""
import argparse, json, sys, os, requests

BASE = "https://coinceeper.com"
HDRS = {
    "User-Agent": "VersionUpdater/1.0",
    "Origin": "https://coinceeper.com",
    "Content-Type": "application/json",
}

def show_status():
    r = requests.get(f"{BASE}/api/app/version", headers=HDRS, timeout=10)
    data = r.json()
    if data.get("success"):
        print("Current version config:")
        print(f"  Android: min={data['android']['min_version']}, latest={data['android']['latest_version']}")
        print(f"  iOS:     min={data['ios']['min_version']}, latest={data['ios']['latest_version']}")
    else:
        print("Error fetching version config")

def update_platform(platform, min_ver, latest_ver, url):
    body = {"platform": platform}
    if min_ver: body["min_version"] = min_ver
    if latest_ver: body["latest_version"] = latest_ver
    if url: body["update_url"] = url

    r = requests.post(f"{BASE}/api/app/version/update-config", json=body, headers=HDRS, timeout=10)
    data = r.json()
    if data.get("success"):
        print(f"[OK] {platform} updated: {json.dumps(data.get('config', {}))}")
    else:
        print(f"[FAIL] {data.get('message', 'Unknown error')}")
        sys.exit(1)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Update app version config")
    parser.add_argument("--platform", choices=["android", "ios"], help="Target platform")
    parser.add_argument("--min", help="Minimum required version (force update)")
    parser.add_argument("--latest", help="Latest available version (optional update)")
    parser.add_argument("--url", help="Store URL")
    parser.add_argument("--status", action="store_true", help="Show current status")

    args = parser.parse_args()

    if args.status:
        show_status()
    elif args.platform:
        update_platform(args.platform, args.min, args.latest, args.url)
    else:
        parser.print_help()
