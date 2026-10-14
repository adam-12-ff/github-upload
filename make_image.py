#!/usr/bin/env python3
"""
Arjun Auto-Poster — Branded image generator
===========================================
queue.json ke posts ke liye professional text-card images banata hai:
  - LinkedIn card:   1200x628 (images/{id}/linkedin.png)
  - IG single card:  1080x1350 (images/{id}/ig_1.png)
  - IG carousel:     1080x1350 slides (images/{id}/ig_1.png ... ig_N.png)

Usage:
  python make_image.py          # due/aaane wale posts ki missing images banao
  python make_image.py --all    # sab missing images banao
  python make_image.py --id 2026-09-28-p1
"""

import json
import os
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from PIL import Image, ImageDraw, ImageFont

IST = ZoneInfo("Asia/Kolkata")
ROOT = Path(__file__).resolve().parent
QUEUE_PATH = Path(os.getenv("QUEUE_PATH", ROOT / "content" / "queue.json"))
IMAGES = ROOT / "images"

BOSS_HANDLE = os.getenv("BOSS_HANDLE", "Ram • Freelance Dev & AI Builder")
GEN_AHEAD_DAYS = float(os.getenv("GEN_AHEAD_DAYS", "3"))

# Brand colors
BG_TOP = (11, 18, 32)
BG_BOT = (16, 27, 51)
ACCENT = (34, 211, 238)      # cyan
VIOLET = (167, 139, 250)
WHITE = (240, 244, 255)
MUTED = (148, 163, 184)
DARK = (7, 12, 22)

FONT_BOLD_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
FONT_REG_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"

PILLAR_KICKERS = {
    1: "AI AGENT KA JAADOO",
    2: "WEBSITE & APP SECRETS",
    3: "PROBLEM → SOLUTION",
    4: "BUILD • SHIP • DELIVER",
}

EMOJI_RE = re.compile(
    "[\U0001F000-\U0001FAFF\u2600-\u26FF\u2700-\u27BF\uFE0F\u2190-\u21FF\u2B00-\u2BFF]"
)


def strip_emoji(s: str) -> str:
    return EMOJI_RE.sub("", s).replace("  ", " ").strip()


def font(size: int, bold: bool = True):
    try:
        return ImageFont.truetype(FONT_BOLD_PATH if bold else FONT_REG_PATH, size)
    except Exception:
        return ImageFont.load_default()


def gradient(w: int, h: int) -> Image.Image:
    img = Image.new("RGB", (w, h))
    for y in range(h):
        t = y / h
        img.paste(tuple(int(a + (b - a) * t) for a, b in zip(BG_TOP, BG_BOT)), (0, y, w, y + 1))
    return img


def wrap_text(draw, text: str, fnt, max_w: int) -> list:
    lines, cur = [], ""
    for word in text.split():
        trial = (cur + " " + word).strip()
        if draw.textlength(trial, font=fnt) <= max_w or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    return lines


def draw_footer(d, W, H, handle, chip=None):
    f = font(int(W * 0.024), bold=False)
    y = int(H * 0.93)
    d.text((int(W * 0.075), y), handle, font=f, fill=MUTED)
    if chip:
        cf = font(int(W * 0.026))
        tw = d.textlength(chip, font=cf)
        pad = int(W * 0.015)
        x1 = int(W * 0.925) - tw - pad * 2
        y1 = y - pad + 2
        d.rounded_rectangle([x1, y1, int(W * 0.925), y1 + tw + pad * 2],
                            radius=8, fill=ACCENT)
        d.text((x1 + pad, y1 + pad - 2), chip, font=cf, fill=DARK)


def render(path: Path, W: int, H: int, kicker: str, headline: str,
           body: str = "", chip: str = None, cover: bool = False):
    img = gradient(W, H)
    d = ImageDraw.Draw(img)
    m = int(W * 0.075)

    # subtle decorative circles (top-right)
    d.ellipse([W - int(W * 0.18), -int(W * 0.10), W + int(W * 0.06), int(W * 0.14)],
              outline=ACCENT, width=2)
    d.ellipse([W - int(W * 0.12), -int(W * 0.06), W + int(W * 0.02), int(W * 0.08)],
              outline=VIOLET, width=2)

    # kicker + accent bar
    d.rectangle([m, m, m + 70, m + 8], fill=ACCENT)
    kf = font(int(W * 0.026))
    d.text((m, m + 22), kicker.upper()[:60], font=kf, fill=ACCENT)

    # auto-fit headline
    y = int(H * 0.22 if body else H * 0.26)
    max_h = int(H * (0.44 if body else 0.55))
    size = int(W * (0.115 if cover else 0.082))
    while size > int(W * 0.04):
        hf = font(size)
        lines = wrap_text(d, headline, hf, W - 2 * m)
        if len(lines) * size * 1.18 <= max_h:
            break
        size -= 3
    for line in lines:
        d.text((m, y), line, font=hf, fill=WHITE)
        y += int(size * 1.18)

    # body
    if body:
        y += int(H * 0.03)
        bf = font(int(W * 0.034), bold=False)
        for line in wrap_text(d, body, bf, W - 2 * m)[:8]:
            d.text((m, y), line, font=bf, fill=MUTED)
            y += int(W * 0.046)

    draw_footer(d, W, H, BOSS_HANDLE[:70], chip=chip)
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path, "PNG")
    print(f"  [img] {path.relative_to(ROOT)}")


def split_headline_body(text: str) -> tuple:
    text = strip_emoji(text)
    if " | " in text:
        h, b = text.split(" | ", 1)
        return h.strip(), b.strip()
    return text, ""


def make_images_for(item: dict) -> None:
    pid, pillar = item["id"], item.get("pillar", 1)
    kicker = PILLAR_KICKERS.get(pillar, "GROW YOUR BUSINESS")

    li = item.get("linkedin", {})
    out = IMAGES / pid / "linkedin.png"
    if li.get("image") and not out.exists():
        render(out, 1200, 628, kicker, strip_emoji(li.get("image_headline", item["topic"])).replace(" | ", " — "))

    ig = item.get("instagram", {})
    if ig.get("carousel"):
        n = len(ig["carousel"])
        for i, slide_text in enumerate(ig["carousel"], start=1):
            p = IMAGES / pid / f"ig_{i}.png"
            if p.exists():
                continue
            h, b = split_headline_body(slide_text)
            render(p, 1080, 1350, kicker, h, body=b,
                   chip=f"{i}/{n}", cover=(i == 1))
    elif ig.get("image") or ig.get("caption"):
        p = IMAGES / pid / "ig_1.png"
        if not p.exists():
            h = strip_emoji(ig.get("image_headline", item["topic"])).replace(" | ", " — ")
            b = strip_emoji(ig.get("image_body", ""))
            render(p, 1080, 1350, kicker, h, body=b, cover=True)


def posts_to_process(posts, mode, only_id=None):
    now = datetime.now(IST)
    for item in posts:
        if only_id and item["id"] != only_id:
            continue
        if mode == "all":
            yield item
            continue
        scheds = []
        for plat in ("linkedin", "instagram"):
            s = item.get(plat, {}).get("schedule")
            if s:
                dt = datetime.fromisoformat(s)
                scheds.append(dt if dt.tzinfo else dt.replace(tzinfo=IST))
        if not scheds:
            continue
        earliest = min(scheds)
        latest = max(scheds)
        # due hai ya agle GEN_AHEAD_DAYS din mein hai
        if (earliest - timedelta(days=GEN_AHEAD_DAYS)) <= now <= (latest + timedelta(hours=48)):
            yield item


def main() -> int:
    args = sys.argv[1:]
    mode = "due"
    only_id = None
    if "--all" in args:
        mode = "all"
    if "--id" in args:
        only_id = args[args.index("--id") + 1]

    queue = json.loads(QUEUE_PATH.read_text(encoding="utf-8"))
    posts = queue.get("posts", [])
    print(f"Arjun Image Generator — mode: {mode}")
    count = 0
    for item in posts_to_process(posts, mode, only_id):
        print(f"[{item['id']}] {item['topic'][:60]}")
        make_images_for(item)
        count += 1
    print(f"Done. {count} post(s) ke images ready: {IMAGES}/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
