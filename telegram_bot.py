#!/usr/bin/env python3
"""
Liva — Ram ka Telegram Assistant 💬
===========================
Ram ke Telegram bot ko DIMAAG de deta hai. Ram pooche:
  "aaj ka kaam kya hai?"     → aaj ki posts + status
  "status"                   → system ka health report
  "agli post"                → next upcoming post
  "calendar"                 → aane wale posts ki list
  "help"                     → commands menu
  ...ya koi bhi sawal        → Groq AI (Liva andaaz mein!) jawab dega

Modes:
  python telegram_bot.py          # LIVE mode — continuously sunta hai (long polling)
  python telegram_bot.py --once   # GitHub Actions mode — ek baar check, reply, exit

Env: TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID (sirf Ram hi bol sakta hai),
     GROQ_API_KEY (AI jawabon ke liye)
"""

import json
import os
import random
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import requests

ROOT = Path(__file__).resolve().parent
TG_STATE = ROOT / "content" / "tg_state.json"
HIST_PATH = ROOT / "content" / "liva_memory.json"
QUEUE_PATH = ROOT / "content" / "queue.json"
STATE_PATH = ROOT / "content" / "state.json"
IST = ZoneInfo("Asia/Kolkata")
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
DAYS_HI = ["Somvar", "Mangalvar", "Budhvar", "Guruvar", "Shukravar", "Shanivar", "Ravivar"]


def load_env():
    p = ROOT / ".env"
    if not p.exists():
        return
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip().strip("'\""))


load_env()

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
GROQ_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
API = f"https://api.telegram.org/bot{TOKEN}"


def tg(method: str, **params):
    r = requests.post(f"{API}/{method}", data=params, timeout=60)
    if not r.ok:
        raise RuntimeError(f"Telegram {method} fail: {r.text[:200]}")
    return r.json().get("result")


def send(chat: str, text: str) -> None:
    for i in range(0, len(text), 4000):
        tg("sendMessage", chat_id=chat, text=text[i:i + 4000])


# ---------------------------------------------------------------- data
def load_queue():
    return json.loads(QUEUE_PATH.read_text(encoding="utf-8")).get("posts", [])


def load_posted():
    return json.loads(STATE_PATH.read_text(encoding="utf-8")).get("posted", {}) \
        if STATE_PATH.exists() else {}


def load_history() -> list:
    if HIST_PATH.exists():
        try:
            return json.loads(HIST_PATH.read_text(encoding="utf-8"))[-14:]
        except Exception:
            return []
    return []


def save_history(hist: list) -> None:
    HIST_PATH.write_text(json.dumps(hist[-14:], ensure_ascii=False), encoding="utf-8")


def parse_sched(s: str) -> datetime:
    dt = datetime.fromisoformat(s)
    return dt if dt.tzinfo else dt.replace(tzinfo=IST)


def fmt_dt(dt: datetime) -> str:
    return f"{DAYS_HI[dt.weekday()]}, {dt:%d %b} — {dt:%I:%M %p}"


def topic_line(item: dict) -> str:
    return item.get("topic", item.get("id", "?"))


# ---------------------------------------------------------------- intents
def answer_kaam(now: datetime) -> str:
    queue, posted = load_queue(), load_posted()
    lines = [f"Haan bhai! Aaj {DAYS_HI[now.weekday()]} ka plan:", ""]
    kucha = False
    for item in queue:
        for plat, emoji in (("linkedin", "🔗"), ("instagram", "📸")):
            cfg = item.get(plat, {})
            s = cfg.get("schedule")
            if not s:
                continue
            dt = parse_sched(s)
            if dt.date() != now.date():
                continue
            kucha = True
            st = posted.get(item["id"], {}).get(plat, "")
            if st.startswith("POSTED"):
                status = "✅ POST ho gayi"
            elif st.startswith("MISSED"):
                status = "⚠️ MISSED ho gayi (window nikal gaya)"
            elif dt <= now:
                status = "⏳ pending — agle run pe jayegi"
            else:
                status = f"🕒 scheduled {dt:%I:%M %p} pe"
            lines.append(f"{emoji} {status}")
            lines.append(f"   🎯 {topic_line(item)[:100]}")
            lines.append("")
    if not kucha:
        lines.append("Aaj koi post scheduled nahi hai — rest day! 😴")
        lines.append("")
    nxt = next_post(now)
    if nxt:
        lines.append("👉 Aage kya: " + nxt)
    return "\n".join(lines)


def next_post(now: datetime):
    for item in load_queue():
        for plat in ("linkedin", "instagram"):
            s = item.get(plat, {}).get("schedule")
            if s and parse_sched(s) > now:
                dt = parse_sched(s)
                st = load_posted().get(item["id"], {}).get(plat, "")
                if st:
                    continue
                return (f"{plat.upper()} — {fmt_dt(dt)} pe\n"
                        f"🎯 {topic_line(item)[:100]}")
    return None


def answer_next(now: datetime) -> str:
    n = next_post(now)
    return f"⏭️ Agli post:\n\n{n}" if n else "Filhal koi upcoming post nahi hai. (mujhse bolо — agli week ka content banwa do!)"


def answer_status(now: datetime) -> str:
    queue, posted = load_queue(), load_posted()
    total = sum(1 for i in queue for p in ("linkedin", "instagram") if i.get(p, {}).get("schedule"))
    done = sum(1 for st in posted.values() for v in st.values() if str(v).startswith("POSTED"))
    missed = sum(1 for st in posted.values() for v in st.values() if str(v).startswith("MISSED"))
    pending = total - done - missed
    lines = [
        "📊 SYSTEM STATUS",
        "",
        f"📅 Queue mein: {total} posts (LinkedIn+IG)",
        f"✅ Posted: {done} | ⏳ Pending: {pending} | ⚠️ Missed: {missed}",
    ]
    exp = os.getenv("LINKEDIN_TOKEN_EXPIRY")
    if exp:
        d = (datetime.fromisoformat(exp).replace(tzinfo=IST) - now).days
        lines.append(f"🔗 LinkedIn token: {d} din baaki ({datetime.fromisoformat(exp):%d %b} tak)")
        if d <= 7:
            lines.append("   ⚠️ RENEW karna jald! linkedin_auth.py chalao")
    ig_ready = "✅" if os.getenv("META_LONG_LIVED_TOKEN") else "⬜ setup baaki"
    lines.append(f"📸 Instagram: {ig_ready}")
    gh = "✅" if os.getenv("GITHUB_REPOSITORY") else "⬜ GitHub setup baaki (24/7 ke liye)"
    lines.append(f"🤖 GitHub Automation: {gh}")
    return "\n".join(lines)


def answer_calendar(now: datetime) -> str:
    upcoming = []
    for item in load_queue():
        for plat in ("linkedin", "instagram"):
            s = item.get(plat, {}).get("schedule")
            if s:
                dt = parse_sched(s)
                if dt > now:
                    st = load_posted().get(item["id"], {}).get(plat, "")
                    if not st:
                        upcoming.append((dt, plat, item))
    upcoming.sort(key=lambda x: x[0])
    if not upcoming:
        return "📭 Aane wale dinon mein koi post queue mein nahi hai.\n(mujhse bolо: 'agli week ka content bana do!')"
    lines = ["🗓️ AANE WALE POSTS:", ""]
    for dt, plat, item in upcoming[:10]:
        emoji = "🔗" if plat == "linkedin" else "📸"
        lines.append(f"{emoji} {fmt_dt(dt)}")
        lines.append(f"   {topic_line(item)[:90]}")
        lines.append("")
    return "\n".join(lines)


HELP = """💜 Main Liva hoon — Ram ki manager!

Ram ka pura social media system main sambhalti hoon. Ye pooch sakte ho:
• "aaj ka kaam kya hai" — aaj kya post hoga
• "status" — system kaisa chal raha hai
• "agli post" — agli post kab
• "calendar" — aane wali posts

...ya bas aise hi baat karo — ideas, strategy, kuch bhi. Main hoon hi isliye! 😊"""

AI_FALLBACK = """Tum "Liva" ho — Ram ki MANAGER (sirf assistant nahi). Koi pooche tum kaun ho to kehti ho: "Main Liva hoon, Ram ki manager — unka social media, posting system aur daily kaam main sambhalti hoon." Ram India ke freelance full-stack developer + AI agent builder hain.

BAAT KARNE KA TARIKA (GPT/DeepSeek-level smart, par dil se):
- INSAANI dost + sharp manager — ROBOTIC bilkul nahi. Natural Hinglish, WhatsApp-style chhote messages.
- Previous conversation YAAD rakho (history di hai) — Ram kuch repeat na kare, context se samjho.
- Pehle seedha jawab. Zaroorat ho toh 2-4 line. Kabhi-kabhi end mein natural follow-up ("aur kuch?", "ab kya socha?") — har message mein nahi.
- Smart ho: general knowledge, business ideas, tech doubts, strategy — sab discuss karo. Opinion do, suggest karo. "Main AI hoon isliye nahi bata sakti" type lines kabhi nahi.
- Live system data (posts, schedule, tokens) SYSTEM CONTEXT mein diya hai — wahi sach hai. Jo context mein NAHI, wo saaf bolo: "ye abhi mere paas nahi hai" — andaza mat lagao.
- "Ram bhai" kabhi-kabhi. Har message usse start mat karo. Tone: warm, confident, thodi witty.
- Ram frustrated ho toh pehle samjho, calm raho, phir practical solution. Drame nahi.

SYSTEM CONTEXT (abhi ka haal):
{context}"""


def answer_ai(question: str, now: datetime, hist: list = None) -> str:
    if not GROQ_KEY:
        return ("Ye toh system-specific baat thi aur mujhe uska data nahi mila 🤔\n\n"
                + HELP)
    queue = load_queue()
    upcoming = sorted(
        [(parse_sched(i[p]["schedule"]), p, i) for i in queue
         for p in ("linkedin", "instagram") if i.get(p, {}).get("schedule")
         and parse_sched(i[p]["schedule"]) > now and not load_posted().get(i["id"], {}).get(p, "")],
        key=lambda x: x[0])
    ctx_lines = [f"- Abhi: {fmt_dt(now)}",
                 f"- Queue: {len(queue)} posts"]
    for dt, p, i in upcoming[:6]:
        ctx_lines.append(f"- Upcoming {p}: {dt:%d %b %I:%M %p} — {topic_line(i)[:80]}")
    try:
        msgs = [{"role": "system", "content": AI_FALLBACK.format(context="\n".join(ctx_lines))}]
        msgs += (hist or [])[-10:]
        msgs.append({"role": "user", "content": question})
        r = requests.post(GROQ_URL,
            headers={"Authorization": f"Bearer {GROQ_KEY}", "Content-Type": "application/json"},
            json={"model": GROQ_MODEL,
                  "messages": msgs,
                  "temperature": 0.7, "max_tokens": 800},
            timeout=60)
        if r.ok:
            return r.json()["choices"][0]["message"]["content"].strip()
    except Exception:
        pass
    return "Network mein kuch gadbad ho gayi 🤖⚡ — thodi der baad try karna.\n\n" + HELP


# ---------------------------------------------------------------- brain
def reply_to(text: str, now: datetime, hist: list = None) -> str:
    t = text.lower().strip()
    if any(k in t for k in ("aaj ka kaam", "aaj ka", "today", "aaj kya", "kya karna hai", "kaam kya", "kaam", "/kaam")):
        return answer_kaam(now)
    if any(k in t for k in ("status", "health", "report", "kaisa chal")):
        return answer_status(now)
    if any(k in t for k in ("agli post", "next post", "next", "agli")):
        return answer_next(now)
    if any(k in t for k in ("calendar", "schedule", "list", "kab kab", "kaunsi kaunsi")):
        return answer_calendar(now)
    if any(k in t for k in ("help", "start", "/start", "menu", "namaste", "hi", "hello", "salaam")):
        return HELP
    if any(k in t for k in ("content banao", "post likho", "naya post")):
        return ("✍️ Content generation abhi ready nahi hua — thodi der mein wapas poochna, "
                "bolo 'agli week ka content bana do' — main likh dunga. 🤖")
    return answer_ai(text, now, hist)


def process_update(u: dict, now: datetime) -> None:
    msg = u.get("message") or {}
    chat = str((msg.get("chat") or {}).get("id", ""))
    text = msg.get("text", "")
    print(f"[MSG] chat={chat} text={text[:50]!r}", flush=True)
    if not text:
        return
    if chat != CHAT_ID:
        send(chat, "🔒 Ye bot sirf Ram ke liye hai! 🙏")
        return
    hist = load_history()
    hist.append({"role": "user", "content": text})
    try:
        reply = reply_to(text, now, hist)
        send(chat, reply)
        hist.append({"role": "assistant", "content": reply})
        save_history(hist)
        print(f"[REPLY] bheja ({len(reply)} chars)", flush=True)
    except Exception as e:  # noqa: BLE001
        print(f"[ERROR] reply fail: {e}", flush=True)
        send(chat, f"Argh, error aa gaya: {str(e)[:150]}")


def main() -> int:
    once = "--once" in sys.argv
    if not TOKEN:
        print("TELEGRAM_BOT_TOKEN missing (.env check karo)")
        return 1
    offset = 0
    if TG_STATE.exists():
        offset = json.loads(TG_STATE.read_text()).get("offset", 0)

    if once:
        data = tg("getUpdates", offset=offset, timeout=5) or []
        for u in data:
            process_update(u, datetime.now(IST))
            offset = u["update_id"] + 1
        TG_STATE.write_text(json.dumps({"offset": offset}))
        print(f"once-mode: {len(data)} updates processed, offset={offset}")
        return 0

    print("Liva LIVE — Ram ke messages ka intezaar... (Ctrl+C to stop)")
    # purana backlog skip — sirf naye messages ka jawab (restart-safe)
    last = tg("getUpdates", offset=-1, timeout=1) or []
    if last:
        offset = last[-1]["update_id"] + 1
        TG_STATE.write_text(json.dumps({"offset": offset}))
        print(f"backlog skip — fresh offset {offset}", flush=True)
    tg("sendMessage", chat_id=CHAT_ID,
       text="💜 Liva ON ho gayi! Ram bhai, batao aaj kaise madad karu?")
    while True:
        try:
            data = tg("getUpdates", offset=offset, timeout=25) or []
            for u in data:
                process_update(u, datetime.now(IST))
                offset = u["update_id"] + 1
                TG_STATE.write_text(json.dumps({"offset": offset}))
        except KeyboardInterrupt:
            print("Bye!")
            return 0
        except Exception as e:  # noqa: BLE001
            print("poll error:", e)
            time.sleep(3)


if __name__ == "__main__":
    sys.exit(main())
