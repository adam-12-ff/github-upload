#!/usr/bin/env python3
"""
Arjun AI Content Generator (Groq powered) 🤖✍️
==============================================
Agli hafte ka content KHUD likhta hai aur queue.json mein add kar deta hai.
Aapka kaam: bas chalana. (Arjun ke content rules — 4 pillars, Hinglish,
storytelling, DM CTAs — system prompt mein baked hain.)

Usage:
  python ai_generate.py              # agli week ka content (4 posts)
  python ai_generate.py --weeks 2    # 2 hafte ka content (8 posts)
  python ai_generate.py --start 2026-10-12

Env: GROQ_API_KEY (zaroori), GROQ_MODEL (default: llama-3.3-70b-versatile)
"""

import argparse
import json
import os
import re
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import requests

ROOT = Path(__file__).resolve().parent
QUEUE_PATH = ROOT / "content" / "queue.json"
IST = ZoneInfo("Asia/Kolkata")
API_URL = "https://api.groq.com/openai/v1/chat/completions"
PILLAR_DAY = {1: 0, 2: 2, 3: 4, 4: 6}  # Mon, Wed, Fri, Sun


def load_env():
    p = Path(__file__).resolve().parent / ".env"
    if not p.exists():
        return
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip().strip("'\""))


SYSTEM_PROMPT = """Tum "Arjun" ho — Ram ka AI content writer. Ram India-based freelance \
full-stack developer + AI agent builder hai (3+ saal experience). Content ka GOAL: reader \
impress ho kar DM kare website/app/AI-bot banwane ke liye (Content > Trust > DM > Client).

AUDIENCE: Indian SMB owners, startup founders, agency owners, coaches/creators, local \
businesses (restaurant, gym, clinic, real estate, salon), e-commerce owners.

WEEKLY PILLARS:
- Monday = Pillar 1 "AI Agent ka Jaadoo" (AI/automation case studies, ROI, competitors using AI)
- Wednesday = Pillar 2 "Website & App Secrets" (speed, design, landing pages, cost farak)
- Friday = Pillar 3 "Problem vs Solution" (emotional problem pehle, logical solution baad mein)
- Sunday = Pillar 4 "Direct Pitch & Proof" (deliveries, limited slots, client reviews, offers)

LINKEDIN POST FORMAT: Pehli line strong HOOK (scroll-stopping). Short paragraphs (1-2 lines \
each, blank lines ke beech). Numbers/data use karo (53%, 3x, ₹2 lakh). Storytelling \
("Ek client tha..."). Emojis sirf 2-4. End mein clear CTA with keyword (jaise DM karo \
"AUTOMATE" / "AUDIT" / "BUILD") + 3-5 hashtags. Length 900-1500 characters.

INSTAGRAM FORMAT: Emoji-rich HOOK first line. Short punchy caption (100-150 words). CTA + \
15-18 hashtags (big+niche+Indian mix). "carousel" = 5-8 slides, har slide "Title | short \
body" format, slide 1 = cover hook, last slide = CTA.

RULES: Hinglish (Hindi + English natural mix). Simple language (12 saal ke bacche ko samjhao). \
Indian examples (kirana store, chai tapri, local gym, coaching institute). Confident + \
empathetic tone. FALSE CLAIMS KABHI NAHI (guaranteed 10x type). Competitor ki burai nahi. \
Generic opening lines nahi ("In today's digital world..." type kabhi nahi). Har post ka \
angle unique ho. Technical terms simple bhasha mein explain karo.

OUTPUT: SIRF valid JSON array return karo — koi explanation nahi, koi markdown fence nahi, \
koi text before/after nahi. Schema (4 posts):
[{"pillar": <1-4 number>, "topic": "<60-90 chars summary>", "visual_suggestion": "<1 line>", \
"expected_engagement": "<1 line>", "linkedin": {"image": true, "image_headline": "<max 55 \
chars, NO emojis, no quotes pipe char>", "text": "<full LinkedIn post>"}, "instagram": \
{"caption": "<full IG caption>", "carousel": ["<5-8 slide strings>"]}}]"""


def next_monday(d: date) -> date:
    while d.weekday() != 0:
        d += timedelta(days=1)
    return d


def extract_json_array(text: str):
    text = re.sub(r"^```(json)?\s*|\s*```$", "", text.strip())
    i, j = text.find("["), text.rfind("]")
    if i == -1 or j == -1:
        raise ValueError(f"Model output mein JSON array nahi mila: {text[:200]}")
    return json.loads(text[i:j + 1])


def generate_week(monday: date, used_topics: list) -> list:
    key = os.getenv("GROQ_API_KEY")
    if not key:
        raise RuntimeError("GROQ_API_KEY set nahi hai (.env ya env var mein daalo)")
    model = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
    days = {p: monday + timedelta(days=o) for p, o in PILLAR_DAY.items()}
    user = f"""Agli week ke 4 posts likho (Monday {days[1]}, Wednesday {days[2]}, \
Friday {days[3]}, Sunday {days[4]} — pillar 1,2,3,4 respectively).

Ye topics PEHLE use ho chuke hain — inhe BILKUL repeat mat karna, naya angle/industry lo:
{chr(10).join('- ' + t for t in used_topics) or '(abhi kuch nahi)'}

4 posts ka strict JSON array do (sirf JSON, schema system prompt mein hai)."""

    r = requests.post(
        API_URL,
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        json={
            "model": model,
            "messages": [{"role": "system", "content": SYSTEM_PROMPT},
                         {"role": "user", "content": user}],
            "temperature": 0.85,
            "max_tokens": 8000,
        },
        timeout=120,
    )
    if not r.ok:
        raise RuntimeError(f"Groq API error {r.status_code}: {r.text[:300]}")
    posts = extract_json_array(r.json()["choices"][0]["message"]["content"])
    if not isinstance(posts, list) or len(posts) != 4:
        raise ValueError("4 posts nahi mile")
    return posts


def finalize(posts: list, monday: date, existing_ids: set) -> list:
    for p in posts:
        pillar = int(p.get("pillar", 1))
        d = monday + timedelta(days=PILLAR_DAY.get(pillar, 0))
        pid = f"{d.isoformat()}-p{pillar}"
        while pid in existing_ids:
            pid += "-b"
        existing_ids.add(pid)
        p["id"] = pid
        p.setdefault("linkedin", {})
        p.setdefault("instagram", {})
        p["linkedin"].setdefault("image", True)
        p["linkedin"]["schedule"] = f"{d.isoformat()}T08:00:00+05:30"
        p["instagram"].setdefault("caption", "")
        p["instagram"]["schedule"] = f"{d.isoformat()}T18:00:00+05:30"
    return posts


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--weeks", type=int, default=1)
    ap.add_argument("--start", type=str, default="", help="YYYY-MM-DD (us week ka Monday ya koi bhi din)")
    args = ap.parse_args()

    load_env()
    if args.start:
        start = datetime.strptime(args.start, "%Y-%m-%d").date()
    else:
        start = datetime.now(IST).date() + timedelta(days=1)

    queue = json.loads(QUEUE_PATH.read_text(encoding="utf-8"))
    existing_ids = {p["id"] for p in queue["posts"]}
    used_topics = [p.get("topic", "") for p in queue["posts"]]

    monday = next_monday(start)
    total = 0
    for w in range(args.weeks):
        wk = monday + timedelta(weeks=w)
        print(f"\n✍️ Week of {wk} ka content generate ho raha hai...")
        posts = finalize(generate_week(wk, used_topics), wk, existing_ids)
        queue["posts"].extend(posts)
        total += len(posts)
        for p in posts:
            print(f"  [+{p['id']}] P{p['pillar']}: {p['topic'][:70]}")
        used_topics.extend(p["topic"] for p in posts)

    QUEUE_PATH.write_text(json.dumps(queue, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n✅ {total} naye posts queue.json mein add ho gaye!")
    print("Images banane ke liye: python make_image.py --all")
    return 0


if __name__ == "__main__":
    sys.exit(main())
