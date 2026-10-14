#!/usr/bin/env python3
"""
Meta (Instagram) Auth Helper — one-time setup ke liye
=====================================================
Ye script chalao, Facebook login karo, aur Instagram page tokens mil jayenge.

Pehle chahiye:
  export META_APP_ID="..."       (developers.facebook.com pe app banao)
  export META_APP_SECRET="..."
  Facebook Login product add karo + Valid OAuth Redirect URI:
      http://localhost:8080/callback
  Aapko app mein Admin/Developer/Tester role hona chahiye (khud ka app hai toh ho)

Phir chalao:
  python meta_auth.py
"""

import http.server
import json
import os
import secrets
import threading
import urllib.parse
import webbrowser

import requests
from pathlib import Path


def load_env():
    """Script ke bagal wali .env file se credentials auto-load."""
    p = Path(__file__).resolve().parent / ".env"
    if not p.exists():
        return
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip().strip("'\""))


load_env()

PORT = 8080
GRAPH = "v23.0"
REDIRECT_URI = f"http://localhost:{PORT}/callback"
SCOPES = ("pages_show_list,pages_read_engagement,pages_manage_posts,"
          "instagram_basic,instagram_content_publish,business_management")
result = {}


class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        result["code"] = q.get("code", [None])[0]
        result["error"] = q.get("error_description", q.get("error", [None]))[0]
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        msg = "✅ Token mil gaya! Is tab ko band karke terminal wapas dekho."
        if result["error"]:
            msg = f"❌ Error: {result['error']}"
        self.wfile.write(f"<h2>{msg}</h2>".encode())

    def log_message(self, *a):
        pass


def g(url, params):
    r = requests.get(url, params=params, timeout=30)
    if not r.ok:
        raise RuntimeError(f"Graph API error: {r.text[:300]}")
    return r.json()


def main():
    app_id = os.getenv("META_APP_ID") or input("META_APP_ID: ").strip()
    app_secret = os.getenv("META_APP_SECRET") or input("META_APP_SECRET: ").strip()
    state = secrets.token_urlsafe(16)

    auth_url = (
        f"https://www.facebook.com/{GRAPH}/dialog/oauth?"
        + urllib.parse.urlencode({
            "client_id": app_id, "redirect_uri": REDIRECT_URI,
            "state": state, "response_type": "code", "scope": SCOPES,
        })
    )

    server = http.server.HTTPServer(("localhost", PORT), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()

    print("\n1) Browser khul raha hai — Facebook login karo aur 'Allow' dabao...\n")
    webbrowser.open(auth_url)

    while not result.get("code") and not result.get("error"):
        pass
    server.shutdown()
    if result.get("error"):
        print(f"\n❌ Login fail: {result['error']}")
        return 1

    # code -> short-lived token -> long-lived token (~60 din, auto-refresh hota hai)
    short = g(f"https://graph.facebook.com/{GRAPH}/oauth/access_token", {
        "client_id": app_id, "client_secret": app_secret,
        "redirect_uri": REDIRECT_URI, "code": result["code"],
    })["access_token"]

    longlived = g(f"https://graph.facebook.com/{GRAPH}/oauth/access_token", {
        "grant_type": "fb_exchange_token", "client_id": app_id,
        "client_secret": app_secret, "fb_exchange_token": short,
    })["access_token"]

    # pages list
    pages = g(f"https://graph.facebook.com/{GRAPH}/me/accounts",
              {"access_token": longlived, "limit": 100}).get("data", [])
    if not pages:
        print("❌ Koi Facebook Page nahi mila jisme aap admin ho.")
        print("   Pehle FB Page banao + Instagram Professional account usse link karo.")
        return 1

    print("\nAapke Facebook Pages:")
    for i, p in enumerate(pages, 1):
        print(f"  {i}. {p['name']}  (id: {p['id']})")
    if len(pages) == 1:
        choice = 1
    else:
        choice = int(input("\nKaunsa page? (number): ").strip() or 1)
    page = pages[choice - 1]
    page_id = page["id"]

    # page token + IG account
    detail = g(f"https://graph.facebook.com/{GRAPH}/{page_id}",
               {"fields": "access_token,instagram_business_account",
                "access_token": longlived})
    page_token = detail.get("access_token", "")
    ig_id = (detail.get("instagram_business_account") or {}).get("id", "")

    print("\n" + "=" * 62)
    print("  YE VALUES GITHUB SECRETS MEIN DAALO:")
    print("=" * 62)
    print(f"META_APP_ID          = {app_id}")
    print(f"META_APP_SECRET      = {app_secret[:4]}****  (purana hi)")
    print(f"META_LONG_LIVED_TOKEN= {longlived}")
    print(f"META_PAGE_ID         = {page_id}")
    if ig_id:
        print(f"IG_USER_ID           = {ig_id}  (optional, info ke liye)")
        print("\n✅ Instagram account linked mil gaya — posting ready!")
    else:
        print("\n⚠️  Is Facebook Page se Instagram PROFESSIONAL account linked nahi hai.")
        print("   SETUP_GUIDE.md Part 1 dekho: Instagram ko Business banao aur")
        print("   Facebook Page se link karo, phir ye script dobara chalao.")
    print("=" * 62)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
