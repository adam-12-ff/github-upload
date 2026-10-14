#!/usr/bin/env python3
"""
LinkedIn Auth Helper — one-time setup ke liye
=============================================
Ye script chalao apne PC pe, browser mein login karo, aur tokens mil jayenge.
Milne wale tokens GitHub Secrets mein daalo.

Pehle chahiye:
  export LINKEDIN_CLIENT_ID="..."     (LinkedIn app se)
  export LINKEDIN_CLIENT_SECRET="..."
  App mein redirect URL add karo: http://localhost:8081/callback
  Products add karo: "Share on LinkedIn" + "Sign In with LinkedIn using OpenID Connect"

Phir chalao:
  python linkedin_auth.py
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

PORT = 8000
REDIRECT_URI = f"http://localhost:{PORT}/callback"
SCOPE = "openid profile email w_member_social"
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


def main():
    cid = os.getenv("LINKEDIN_CLIENT_ID") or input("LINKEDIN_CLIENT_ID: ").strip()
    cs = os.getenv("LINKEDIN_CLIENT_SECRET") or input("LINKEDIN_CLIENT_SECRET: ").strip()
    state = secrets.token_urlsafe(16)

    auth_url = (
        "https://www.linkedin.com/oauth/v2/authorization?"
        + urllib.parse.urlencode({
            "response_type": "code", "client_id": cid, "redirect_uri": REDIRECT_URI,
            "state": state, "scope": SCOPE,
        })
    )

    server = http.server.HTTPServer(("localhost", PORT), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()

    print("\n1) Browser khul raha hai — LinkedIn login karo aur 'Allow' dabao...\n")
    webbrowser.open(auth_url)

    while not result.get("code") and not result.get("error"):
        pass
    server.shutdown()
    if result.get("error"):
        print(f"\n❌ Login fail: {result['error']}")
        return 1

    # code -> access token
    r = requests.post(
        "https://www.linkedin.com/oauth/v2/accessToken",
        data={
            "grant_type": "authorization_code", "code": result["code"],
            "redirect_uri": REDIRECT_URI, "client_id": cid, "client_secret": cs,
        },
        timeout=30,
    )
    r.raise_for_status()
    tok = r.json()
    access, refresh = tok.get("access_token"), tok.get("refresh_token")
    expires_in = tok.get("expires_in", 0)

    # member id (OpenID userinfo se)
    me = requests.get(
        "https://api.linkedin.com/v2/userinfo",
        headers={"Authorization": f"Bearer {access}"}, timeout=30,
    ).json()

    print("\n" + "=" * 62)
    print("  YE VALUES GITHUB SECRETS MEIN DAALO:")
    print("=" * 62)
    print(f"LINKEDIN_CLIENT_ID     = {cid}")
    print(f"LINKEDIN_CLIENT_SECRET = {cs[:4]}****  (purana hi)")
    print(f"LINKEDIN_ACCESS_TOKEN  = {access}")
    from datetime import datetime, timedelta
    exp = datetime.now() + timedelta(seconds=expires_in)
    print(f"LINKEDIN_TOKEN_EXPIRY  = {exp.isoformat()}")
    print(f"  ⚠️  Token {expires_in//86400} din valid ({exp:%d %b %Y} tak).")
    print("     poster.py expiry se 7 din pehle Telegram pe reminder bhejega.")
    print("     Expire hone par ye script dobara chalao (2 min ka kaam).")
    print(f"LINKEDIN_MEMBER_URN    = urn:li:person:{me.get('sub')}")
    print("=" * 62)
    print("\nNote: ACCESS_TOKEN file mein save MAT karo — direct Secrets mein daalo.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
