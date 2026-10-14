#!/usr/bin/env python3
"""
Arjun Auto-Poster — LinkedIn + Instagram automatic posting engine
================================================================
GitHub Actions cron se chalta hai. Content queue (content/queue.json) padhta hai,
jo post due hai usko LinkedIn API + Instagram Graph API se publish kar deta hai.

Env vars (GitHub Secrets mein set karo):
  LinkedIn:  LINKEDIN_CLIENT_ID, LINKEDIN_CLIENT_SECRET, LINKEDIN_REFRESH_TOKEN
             (ya sirf LINKEDIN_ACCESS_TOKEN — 60 din valid)
  Meta/IG:   META_APP_ID, META_APP_SECRET, META_LONG_LIVED_TOKEN, META_PAGE_ID
  Optional:  DRY_RUN=1 (test mode — kuch post nahi hota, sirf log)
             GRACE_HOURS=6 (kitne ghante purani due post abhi post hogi)
             IMAGE_BASE_URL (IG ke liye public images ka base URL)
"""

import json
import logging
import os
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import requests

# ------------------------------------------------------------------ setup


def load_env():
    """Local testing ke liye .env auto-load (GitHub pe Secrets use hote hain)."""
    p = Path(__file__).resolve().parent / ".env"
    if not p.exists():
        return
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip().strip("'\""))


load_env()

IST = ZoneInfo("Asia/Kolkata")
ROOT = Path(__file__).resolve().parent
QUEUE_PATH = Path(os.getenv("QUEUE_PATH", ROOT / "content" / "queue.json"))
STATE_PATH = Path(os.getenv("STATE_PATH", ROOT / "content" / "state.json"))

DRY_RUN = os.getenv("DRY_RUN", "").lower() in ("1", "true", "yes")
GRACE_HOURS = float(os.getenv("GRACE_HOURS", "6"))
GRAPH_VERSION = os.getenv("GRAPH_VERSION", "v23.0")
LINKEDIN_VERSION = os.getenv("LINKEDIN_VERSION", "202608")  # sunset-proof (valid till Aug 2027)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
LOG = logging.getLogger("arjun-poster")


def now_ist() -> datetime:
    return datetime.now(IST)


def load_json(path: Path, default):
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return default


def image_base_url() -> str:
    """IG ko publicly accessible image URL chahiye hota hai.
    GitHub Actions mein raw.githubusercontent.com ka URL auto ban jata hai
    (repo PUBLIC hona chahiye)."""
    base = os.getenv("IMAGE_BASE_URL")
    if base:
        return base.rstrip("/")
    server, repo = os.getenv("GITHUB_SERVER_URL"), os.getenv("GITHUB_REPOSITORY")
    ref = os.getenv("GITHUB_REF_NAME", "main")
    if server and repo:
        return f"https://raw.githubusercontent.com/{repo}/{ref}/images"
    local = (ROOT / "images").as_uri()
    LOG.warning("IMAGE_BASE_URL set nahi hai — local file URL use kar rahe hain "
                "(Instagram ise fetch NAHI kar payega). Public GitHub repo ya "
                "image host ka URL set karo.")
    return local


# ------------------------------------------------------------------ LinkedIn
def li_headers(token: str) -> dict:
    return {
        "Authorization": f"Bearer {token}",
        "LinkedIn-Version": LINKEDIN_VERSION,
        "X-Restli-Protocol-Version": "2.0.0",
        "Content-Type": "application/json",
    }


def li_access_token() -> str:
    """Refresh token se naya access token lo (60 din expiry handle ho jati hai).
    Refresh token nahi hai toh static access token use karo."""
    rt = os.getenv("LINKEDIN_REFRESH_TOKEN")
    cid, cs = os.getenv("LINKEDIN_CLIENT_ID"), os.getenv("LINKEDIN_CLIENT_SECRET")
    if rt and cid and cs:
        r = requests.post(
            "https://www.linkedin.com/oauth/v2/accessToken",
            data={
                "grant_type": "refresh_token",
                "refresh_token": rt,
                "client_id": cid,
                "client_secret": cs,
            },
            timeout=30,
        )
        if r.ok:
            LOG.info("LinkedIn token refresh ho gaya (refresh_token se)")
            return r.json()["access_token"]
        LOG.warning("LinkedIn refresh fail: %s — static token try kar rahe hain", r.text[:200])
    tok = os.getenv("LINKEDIN_ACCESS_TOKEN")
    if not tok:
        raise RuntimeError(
            "LinkedIn credentials missing: LINKEDIN_REFRESH_TOKEN + CLIENT_ID/SECRET "
            "ya LINKEDIN_ACCESS_TOKEN set karo (SETUP_GUIDE.md Part 4 dekho)"
        )
    return tok


def li_member_urn(token: str) -> str:
    urn = os.getenv("LINKEDIN_MEMBER_URN", "")
    if urn:
        return urn if urn.startswith("urn:") else f"urn:li:person:{urn}"
    r = requests.get(
        "https://api.linkedin.com/v2/userinfo",
        headers={"Authorization": f"Bearer {token}"},
        timeout=30,
    )
    r.raise_for_status()
    return f"urn:li:person:{r.json()['sub']}"


def li_upload_image(token: str, person_urn: str, path: Path) -> str:
    """Image binary LinkedIn pe upload karke media URN return karta hai."""
    r = requests.post(
        "https://api.linkedin.com/rest/images?action=initializeUpload",
        headers=li_headers(token),
        json={"initializeUploadRequest": {"owner": person_urn}},
        timeout=30,
    )
    r.raise_for_status()
    data = r.json().get("value", r.json())  # restli "value" wrapper handle
    upload_url, image_urn = data["uploadUrl"], data["image"]
    with open(path, "rb") as f:
        put = requests.put(upload_url, data=f, timeout=180)
    put.raise_for_status()
    LOG.info("LinkedIn image upload: %s", path.name)
    return image_urn


def li_post(token: str, text: str, image_path: Path | None = None) -> str:
    person = li_member_urn(token)
    body = {
        "author": person,
        "commentary": text,
        "visibility": "PUBLIC",
        "distribution": {
            "feedDistribution": "MAIN_FEED",
            "targetEntities": [],
            "thirdPartyDistributionChannels": [],
        },
        "lifecycleState": "PUBLISHED",
        "isReshareDisabledByAuthor": False,
    }
    if image_path:
        media_urn = li_upload_image(token, person, image_path)
        body["content"] = {"media": {"id": media_urn}}
    r = requests.post(
        "https://api.linkedin.com/rest/posts", headers=li_headers(token), json=body, timeout=60
    )
    if r.status_code not in (200, 201):
        raise RuntimeError(f"LinkedIn post fail {r.status_code}: {r.text[:300]}")
    return r.headers.get("x-restli-id", "")


# ------------------------------------------------------------------ Instagram
def ig_page_token() -> str:
    """Long-lived user token ko refresh karke Page token nikalta hai.
    Token chain har run pe refresh hoti hai — 60 din ka tension khatam."""
    ll = os.getenv("META_LONG_LIVED_TOKEN")
    page_id = os.getenv("META_PAGE_ID")
    if ll and page_id:
        app_id, app_secret = os.getenv("META_APP_ID"), os.getenv("META_APP_SECRET")
        if app_id and app_secret:
            r = requests.get(
                f"https://graph.facebook.com/{GRAPH_VERSION}/oauth/access_token",
                params={
                    "grant_type": "fb_exchange_token",
                    "client_id": app_id,
                    "client_secret": app_secret,
                    "fb_exchange_token": ll,
                },
                timeout=30,
            )
            if r.ok:
                ll = r.json()["access_token"]
                LOG.info("Meta long-lived token refresh ho gaya")
            else:
                LOG.warning("Meta token refresh fail: %s — purana token try kar rahe hain",
                            r.text[:200])
        pages = requests.get(
            f"https://graph.facebook.com/{GRAPH_VERSION}/me/accounts",
            params={"access_token": ll, "limit": 100},
            timeout=30,
        ).json()
        for p in pages.get("data", []):
            if str(p.get("id")) == str(page_id):
                return p["access_token"]
        raise RuntimeError(
            f"Page ID {page_id} ka token nahi mila. META_PAGE_ID check karo ya "
            "meta_auth.py dobara chalao (SETUP_GUIDE.md Part 3)"
        )
    tok = os.getenv("META_PAGE_TOKEN")
    if not tok:
        raise RuntimeError(
            "Meta credentials missing: META_LONG_LIVED_TOKEN + META_PAGE_ID set karo "
            "(SETUP_GUIDE.md Part 3 dekho)"
        )
    LOG.warning("META_PAGE_TOKEN use kar rahe ho — ye ~60 din mein expire ho jata hai. "
                "Behtar hai META_LONG_LIVED_TOKEN + META_PAGE_ID set karo.")
    return tok


def ig_wait_container(creation_id: str, token: str, timeout_min: int = 5) -> None:
    """IG container 'FINISHED' hone tak wait karta hai."""
    deadline = time.time() + timeout_min * 60
    while time.time() < deadline:
        s = requests.get(
            f"https://graph.facebook.com/{GRAPH_VERSION}/{creation_id}",
            params={"fields": "status_code", "access_token": token},
            timeout=30,
        ).json()
        code = s.get("status_code")
        if code == "FINISHED":
            return
        if code == "ERROR":
            raise RuntimeError(f"IG container error: {s}")
        time.sleep(5)
    raise RuntimeError("IG container processing timeout (5 min)")


def ig_publish_single(page_id: str, token: str, image_url: str, caption: str) -> str:
    r = requests.post(
        f"https://graph.facebook.com/{GRAPH_VERSION}/{page_id}/media",
        data={"image_url": image_url, "caption": caption, "access_token": token},
        timeout=60,
    )
    if not r.ok:
        raise RuntimeError(f"IG container create fail: {r.text[:300]}")
    cid = r.json()["id"]
    ig_wait_container(cid, token)
    r2 = requests.post(
        f"https://graph.facebook.com/{GRAPH_VERSION}/{page_id}/media_publish",
        data={"creation_id": cid, "access_token": token},
        timeout=60,
    )
    if not r2.ok:
        raise RuntimeError(f"IG publish fail: {r2.text[:300]}")
    return r2.json().get("id", "")


def ig_publish_carousel(page_id: str, token: str, image_urls: list, caption: str) -> str:
    if not (1 < len(image_urls) <= 10):
        raise RuntimeError("Carousel mein 2-10 images hone chahiye")
    children = []
    for url in image_urls:
        r = requests.post(
            f"https://graph.facebook.com/{GRAPH_VERSION}/{page_id}/media",
            data={"image_url": url, "is_carousel_item": "true", "access_token": token},
            timeout=60,
        )
        if not r.ok:
            raise RuntimeError(f"IG carousel child fail ({url}): {r.text[:300]}")
        children.append(r.json()["id"])
    for cid in children:
        ig_wait_container(cid, token)
    r = requests.post(
        f"https://graph.facebook.com/{GRAPH_VERSION}/{page_id}/media",
        data={
            "media_type": "CAROUSEL",
            "children": ",".join(children),
            "caption": caption,
            "access_token": token,
        },
        timeout=60,
    )
    if not r.ok:
        raise RuntimeError(f"IG carousel parent fail: {r.text[:300]}")
    parent_id = r.json()["id"]
    ig_wait_container(parent_id, token)
    r2 = requests.post(
        f"https://graph.facebook.com/{GRAPH_VERSION}/{page_id}/media_publish",
        data={"creation_id": parent_id, "access_token": token},
        timeout=60,
    )
    if not r2.ok:
        raise RuntimeError(f"IG carousel publish fail: {r2.text[:300]}")
    return r2.json().get("id", "")


# ------------------------------------------------------------------ main loop
def post_linkedin(item: dict, cfg: dict) -> str:
    token = li_access_token()
    img = None
    if cfg.get("image"):
        p = ROOT / "images" / item["id"] / "linkedin.png"
        if p.exists():
            img = p
        else:
            LOG.warning("[%s] LinkedIn image nahi mili (%s) — text-only post hoga",
                        item["id"], p)
    try:
        return li_post(token, cfg["text"], img)
    except RuntimeError as e:
        if img:  # image wajah se fail hua? text-only retry — post kabhi miss na ho
            LOG.warning("Image post fail (%s) — text-only retry...", str(e)[:120])
            return li_post(token, cfg["text"], None)
        raise


def post_instagram(item: dict, cfg: dict) -> str:
    token = ig_page_token()
    page_id = os.getenv("META_PAGE_ID", "")
    base = image_base_url()
    img_dir = ROOT / "images" / item["id"]

    if cfg.get("carousel"):
        n = len(cfg["carousel"])
        missing = [f"ig_{i}.png" for i in range(1, n + 1) if not (img_dir / f"ig_{i}.png").exists()]
        if missing:
            raise RuntimeError(f"Carousel images missing: {missing} — 'python make_image.py' chalao")
        urls = [f"{base}/{item['id']}/ig_{i}.png" for i in range(1, n + 1)]
        return ig_publish_carousel(page_id, token, urls, cfg["caption"])

    if not (img_dir / "ig_1.png").exists():
        raise RuntimeError(f"Image missing: {img_dir / 'ig_1.png'} — 'python make_image.py' chalao")
    return ig_publish_single(page_id, token, f"{base}/{item['id']}/ig_1.png", cfg["caption"])


def li_token_expiry_check() -> None:
    """LinkedIn token expiry paas ho toh Telegram pe reminder bhejo."""
    exp_raw = os.getenv("LINKEDIN_TOKEN_EXPIRY", "")
    if not exp_raw or DRY_RUN:
        return
    try:
        exp = datetime.fromisoformat(exp_raw)
        if exp.tzinfo is None:
            exp = exp.replace(tzinfo=IST)  # .env mein local (IST) time hota hai
        days = (exp - now_ist()).days
        if days <= 7:
            tg_notify(
                f"⚠️ REMINDER: LinkedIn token {days} din mein expire ho raha hai "
                f"({exp:%d %b ko}).\n\nFix (2 min): linkedin_auth.py dobara chalao, "
                "naya LINKEDIN_ACCESS_TOKEN + LINKEDIN_TOKEN_EXPIRY GitHub Secrets "
                "mein update kar do.\n\nTab tak LinkedIn posts post NAHI hongi!"
            )
            LOG.warning("LinkedIn token expiry paas: %d din baaki", days)
    except ValueError:
        LOG.warning("LINKEDIN_TOKEN_EXPIRY parse nahi hua: %s", exp_raw[:50])


def main() -> int:
    queue = load_json(QUEUE_PATH, {"posts": []})
    t = now_ist()
    LOG.info("Arjun Auto-Poster started @ %s | DRY_RUN=%s", t.isoformat(), DRY_RUN)
    li_token_expiry_check()

    state = load_json(STATE_PATH, {})
    posted = state.setdefault("posted", {})
    did_something = False
    results = []

    for item in queue.get("posts", []):
        pid = item["id"]
        st = posted.setdefault(pid, {})

        for platform in ("linkedin", "instagram"):
            cfg = item.get(platform)
            if not cfg or st.get(platform, "").startswith(("POSTED", "MISSED")):
                continue
            sched_raw = cfg.get("schedule")
            if not sched_raw:
                continue
            due = datetime.fromisoformat(sched_raw)
            if due.tzinfo is None:
                due = due.replace(tzinfo=IST)

            if due > t:
                continue  # abhi time nahi hua
            if t > due + timedelta(hours=GRACE_HOURS):
                st[platform] = f"MISSED @ {t.isoformat()}"
                LOG.warning("[%s/%s] posting window (%dh) nikal gaya — skip. "
                            "Actions disabled toh check karo!", pid, platform, int(GRACE_HOURS))
                continue

            try:
                if DRY_RUN:
                    LOG.info("[DRY-RUN] %s/%s post hota (schedule: %s)", pid, platform, sched_raw)
                    continue
                if platform == "linkedin":
                    ref = post_linkedin(item, cfg)
                else:
                    ref = post_instagram(item, cfg)
                st[platform] = f"POSTED @ {t.isoformat()} ref={ref}"
                did_something = True
                LOG.info("[OK] %s/%s posted successfully 🎉", pid, platform)
            except Exception as e:  # noqa: BLE001
                LOG.error("[FAIL] %s/%s: %s", pid, platform, e)
                did_something = True  # error log save karne ke liye state commit hogi

    if DRY_RUN:
        LOG.info("DRY-RUN complete — kuch bhi post nahi hua, state save nahi hua.")
        return 0

    STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    LOG.info("State saved. Done.")
    if results:
        tg_notify("🤖 Arjun Auto-Poster — update\n" + "\n".join(results))
    return 0


if __name__ == "__main__":
    sys.exit(main())
