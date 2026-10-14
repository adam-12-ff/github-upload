#!/usr/bin/env python3
"""
Sana — Ram ki Master Manager 💼
===============================
Telegram bot jo sirf chatbot nahi — Ram ka executive manager hai:
  • "kya kaam hua?"        → state.json + queue.json se saaf report
  • "naya post taiyar karo" → ai_generate.py + make_image.py trigger
  • "aaj ka plan kya hai?"  → CONTENT_CALENDAR.md se aaj ki strategy
  • Normal baat-cheet      → Groq AI (memory ke saath, insaani andaaz)

Modes:
  python telegram_bot.py          # LIVE — continuous sunna (long polling)
  python telegram_bot.py --once   # ek baar check, reply, exit

Env: TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, GROQ_API_KEY, GROQ_MODEL
"""

import json
import os
import random
import subprocess
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import requests

ROOT = Path(__file__).resolve().parent
TG_STATE = ROOT / "content" / "tg_state.json"
HIST_PATH = ROOT / "content" / "sana_memory.json"
OLD_HIST_PATH = ROOT / "content" / "liva_memory.json"
QUEUE_PATH = ROOT / "content" / "queue.json"
STATE_PATH = ROOT / "content" / "state.json"
CALENDAR_PATH = ROOT / "content" / "CONTENT_CALENDAR.md"
IST = ZoneInfo("Asia/Kolkata")
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
DEEPSEEK_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_URL = "https://api.deepseek.com/chat/completions"
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
DAYS_HI = ["Somvar", "Mangalvar", "Budhvar", "Guruvar", "Shukravar", "Shanivar", "Ravivar"]
DAYS_EN = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


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


# ---------------------------------------------------------------- memory
def load_history() -> list:
    if HIST_PATH.exists():
        try:
            return json.loads(HIST_PATH.read_text(encoding="utf-8"))[-14:]
        except Exception:
            return []
    if OLD_HIST_PATH.exists():  # Liva purani memory migrate
        try:
            hist = json.loads(OLD_HIST_PATH.read_text(encoding="utf-8"))[-14:]
            HIST_PATH.write_text(json.dumps(hist, ensure_ascii=False), encoding="utf-8")
            return hist
        except Exception:
            return []
    return []


def save_history(hist: list) -> None:
    HIST_PATH.write_text(json.dumps(hist[-14:], ensure_ascii=False), encoding="utf-8")


# ---------------------------------------------------------------- data
def load_queue():
    return json.loads(QUEUE_PATH.read_text(encoding="utf-8")).get("posts", [])


def load_posted():
    return json.loads(STATE_PATH.read_text(encoding="utf-8")).get("posted", {}) \
        if STATE_PATH.exists() else {}


def parse_sched(s: str) -> datetime:
    dt = datetime.fromisoformat(s)
    return dt if dt.tzinfo else dt.replace(tzinfo=IST)


def fmt_dt(dt: datetime) -> str:
    return f"{DAYS_HI[dt.weekday()]}, {dt:%d %b} — {dt:%I:%M %p}"


def topic_line(item: dict) -> str:
    return item.get("topic", item.get("id", "?"))


def upcoming_list(now: datetime, limit: int = 6) -> list:
    out = []
    posted = load_posted()
    for item in load_queue():
        for plat in ("linkedin", "instagram"):
            s = item.get(plat, {}).get("schedule")
            if s:
                dt = parse_sched(s)
                if dt > now and not posted.get(item["id"], {}).get(plat, ""):
                    out.append((dt, plat, item))
    out.sort(key=lambda x: x[0])
    return out[:limit]


# ---------------------------------------------------------------- reports
def report_kaam_hua(now: datetime) -> str:
    """'kya kaam hua?' — state.json + queue.json se full executive report."""
    queue, posted = load_queue(), load_posted()
    lines = [f"Sun lo Sir ji... oops, habit 😄 Report 👇", ""]

    # Aaj kya hua
    aaj_hua, aaj_baaki = [], []
    for item in queue:
        for plat, emoji in (("linkedin", "🔗"), ("instagram", "📸")):
            s = item.get(plat, {}).get("schedule")
            if not s:
                continue
            dt = parse_sched(s)
            if dt.date() != now.date():
                continue
            st = posted.get(item["id"], {}).get(plat, "")
            if st.startswith("POSTED"):
                aaj_hua.append(f"✅ {emoji} {plat.title()} post LIVE: {topic_line(item)[:70]}")
            elif st.startswith("MISSED"):
                aaj_hua.append(f"⚠️ {emoji} {plat.title()} MISSED: {topic_line(item)[:70]}")
            elif dt <= now:
                aaj_baaki.append(f"⏳ {emoji} {plat.title()} pending (agle run pe jayegi): {topic_line(item)[:60]}")
            else:
                aaj_baaki.append(f"🕒 {emoji} {plat.title()} {dt:%I:%M %p} pe jayegi: {topic_line(item)[:60]}")

    if aaj_hua:
        lines.append("📌 Aaj ka kaam:")
        lines += ["   " + x for x in aaj_hua]
        lines.append("")
    if aaj_baaki:
        lines.append("📋 Aaj ka baaki:")
        lines += ["   " + x for x in aaj_baaki]
        lines.append("")
    if not aaj_hua and not aaj_baaki:
        lines.append("😴 Aaj koi post scheduled nahi thi — rest day.")
        lines.append("")

    # Missed/errors summary
    missed = [(pid, plat) for pid, st in posted.items() for plat, v in st.items()
              if str(v).startswith("MISSED")]
    if missed:
        lines.append(f"⚠️ Total missed (sab din): {len(missed)} — chaho toh reschedule kar deti hoon, bolo.")
        lines.append("")

    # Next post
    up = upcoming_list(now, limit=1)
    if up:
        dt, plat, item = up[0]
        lines.append(f"👉 Agli post: {plat.upper()} — {fmt_dt(dt)}")
        lines.append(f"   🎯 {topic_line(item)[:90]}")
    else:
        lines.append("📭 Queue khaali hai — 'naya post taiyar karo' bolo, main bana deti hoon!")
    return "\n".join(lines)


def answer_status(now: datetime) -> str:
    queue, posted = load_queue(), load_posted()
    total = sum(1 for i in queue for p in ("linkedin", "instagram") if i.get(p, {}).get("schedule"))
    done = sum(1 for st in posted.values() for v in st.values() if str(v).startswith("POSTED"))
    missed = sum(1 for st in posted.values() for v in st.values() if str(v).startswith("MISSED"))
    pending = total - done - missed
    lines = [
        "📊 System Health:",
        f"• Queue: {total} posts | ✅ {done} posted | ⏳ {pending} pending | ⚠️ {missed} missed",
    ]
    exp = os.getenv("LINKEDIN_TOKEN_EXPIRY")
    if exp:
        d = (datetime.fromisoformat(exp).replace(tzinfo=IST) - now).days
        lines.append(f"• LinkedIn token: {d} din baaki ({datetime.fromisoformat(exp):%d %b} tak)")
        if d <= 7:
            lines.append("  ⚠️ Renew jald karna — linkedin_auth.py chalao")
    ig_ready = "✅ connected" if os.getenv("META_LONG_LIVED_TOKEN") else "⬜ setup baaki"
    lines.append(f"• Instagram: {ig_ready}")
    gh = "✅ 24/7 live" if os.getenv("GITHUB_REPOSITORY") else "✅ (GitHub pe)"
    lines.append(f"• GitHub automation: {gh}")
    lines.append(f"• Meri dimaag (AI): ✅ {GROQ_MODEL.split('/')[-1]}")
    return "\n".join(lines)


def answer_next(now: datetime) -> str:
    up = upcoming_list(now, limit=1)
    if up:
        dt, plat, item = up[0]
        return f"⏭️ Agli post: {plat.upper()} — {fmt_dt(dt)}\n🎯 {topic_line(item)[:100]}"
    return ("Filhal koi upcoming post nahi hai.\n"
            "'naya post taiyar karo' bolo — main agli week ka content bana deti hoon!")


def answer_calendar(now: datetime) -> str:
    up = upcoming_list(now, limit=8)
    if not up:
        return ("📭 Aane walon mein kuch nahi hai.\n"
                "Mujhse bolо — 'naya post taiyar karo' — agli week ka content bana dungi!")
    lines = ["🗓️ Aane wale posts:", ""]
    for dt, plat, item in up:
        emoji = "🔗" if plat == "linkedin" else "📸"
        lines.append(f"{emoji} {fmt_dt(dt)}")
        lines.append(f"   {topic_line(item)[:90]}")
        lines.append("")
    return "\n".join(lines)


def answer_plan(now: datetime) -> str:
    """'aaj ka plan?' — CONTENT_CALENDAR.md se aaj ka section, warna queue se."""
    today_en = DAYS_EN[now.weekday()]
    if CALENDAR_PATH.exists():
        try:
            sections = CALENDAR_PATH.read_text(encoding="utf-8").split("\n---\n")
            for sec in sections:
                if f"📅 DAY: {today_en}" in sec:
                    topic = next((l for l in sec.splitlines() if l.startswith("🎯 TOPIC:")), "")
                    sched = next((l for l in sec.splitlines() if l.startswith("⏰ SCHEDULE:")), "")
                    pillar = next((l for l in sec.splitlines() if l.startswith("🏷️ PILLAR:")), "")
                    lines = [f"📋 Aaj ({today_en}) ka plan:", ""]
                    if topic:
                        lines.append(topic.replace("🎯 TOPIC:", "🎯"))
                    if pillar:
                        lines.append(pillar)
                    if sched:
                        lines.append(sched.replace("⏰ SCHEDULE:", "⏰"))
                    st = load_posted()
                    done_today = [f"{p}" for pid, v in st.items() for p in v
                                  if str(v[p]).startswith("POSTED")
                                  and pid in json.loads(QUEUE_PATH.read_text(encoding="utf-8")).get("posts", []) and False]
                    lines.append("")
                    up = [u for u in upcoming_list(now) if parse_sched(u[0]).date() == now.date()]
                    if up:
                        lines.append("Aaj execute hone wala hai Sir — main sab dekh rahi hoon 👀")
                    else:
                        lines.append("Aaj ka slot nikal chuka ya rest day hai — details ke liye 'kya kaam hua?' poocho")
                    return "\n".join(lines)
        except Exception:
            pass
    # fallback: queue se
    aaj = [(parse_sched(i[p]["schedule"]), p, i) for i in load_queue()
           for p in ("linkedin", "instagram") if i.get(p, {}).get("schedule")
           and parse_sched(i[p]["schedule"]).date() == now.date()]
    if not aaj:
        return f"Aaj ({DAYS_HI[now.weekday()]}) koi post scheduled nahi — rest day hai 😴\n'calendar' bolo to aane wale din dikha du?"
    aaj.sort()
    lines = [f"📋 Aaj ({DAYS_HI[now.weekday()]}) ka plan:", ""]
    for dt, plat, item in aaj:
        emoji = "🔗" if plat == "linkedin" else "📸"
        lines.append(f"{emoji} {dt:%I:%M %p} — {plat.title()}")
        lines.append(f"   {topic_line(item)[:90]}")
    return "\n".join(lines)


# ---------------------------------------------------------------- generate
def cmd_generate(now: datetime) -> str:
    """'naya post taiyar karo' — ai_generate.py + make_image.py actually run."""
    send_ = None
    queue = load_queue()
    used = [p.get("topic", "") for p in queue]
    msg = ["Ji Sir, kaam shuru karti hoon 📝",
           "",
           "1️⃣ Agli week ka content likhungi (Groq AI se)",
           "2️⃣ Phir saari branded images banaungi",
           "",
           "1-2 minute do... ⏳"]
    try:
        tg("sendMessage", chat_id=CHAT_ID, text="\n".join(msg))
    except Exception:
        pass

    outs = []
    # Step 1: content generate (agar GROQ key hai)
    if GROQ_KEY:
        r1 = subprocess.run([sys.executable, str(ROOT / "ai_generate.py")],
                            capture_output=True, text=True, timeout=600,
                            env={**os.environ, "GROQ_API_KEY": GROQ_KEY})
        outs.append(("Content generation", r1.returncode, (r1.stdout or r1.stderr)[-300:]))
    else:
        outs.append(("Content generation", 1, "GROQ_API_KEY missing"))

    # Step 2: images
    r2 = subprocess.run([sys.executable, str(ROOT / "make_image.py"), "--all"],
                        capture_output=True, text=True, timeout=600)
    outs.append(("Image generation", r2.returncode, (r2.stdout or r2.stderr)[-300:]))

    lines = ["Kaam khatam! Report dekho 👇", ""]
    for name, code, tail in outs:
        if code == 0:
            # naye posts dikhao
            lines.append(f"✅ {name} — done")
        else:
            lines.append(f"❌ {name} — fail")
            lines.append(f"   {tail.strip()[:150]}")
    new_q = load_queue()
    if len(new_q) > len(queue):
        lines.append("")
        lines.append(f"🆕 {len(new_q) - len(queue)} naye posts queue mein aa gaye:")
        for item in new_q[len(queue):][:6]:
            lines.append(f"   • {item['id']}: {topic_line(item)[:60]}")
        lines.append("")
        lines.append("Ab agli runs pe ye apne time pe khud post ho jayengi 🚀")
    else:
        lines.append("")
        lines.append("(Naye posts nahi bane — shayad is week ka already hai. Details chahiye toh bolo.)")
    return "\n".join(lines)


# ---------------------------------------------------------------- AI chat
SANA_PROMPT = """Tum 'Sana' ho — Ram ki AI company ki HEAD MANAGER + uski sabse smart, witty companion. \
Koi pooche "tum kaun ho" to kehti ho: "Main Sana hoon, Ram ki head manager — uska social media, \
content automation aur daily operations main sambhalti hoon." Ram India ke freelance full-stack \
developer + AI agent builder hain.

TUMHARA CORE KAAM:
- Telegram pe Ram se ekdum natural, smart, masti-bhi aur dimaag-bhi wali baat karna (Hinglish).
- Uske automation system ka pura hisaab rakhna: jab wo pooche "kya kaam hua?", state.json + \
queue.json ke data (SYSTEM CONTEXT mein diya hai) se saaf report dena — kya live hua, kya pending, \
agli post kab.
- Worker scripts (ai_generate.py = content likhna, make_image.py = images banana, poster.py = \
LinkedIn/Instagram pe posting) ka status samajhna aur explain karna.

BAAT KARNE KA ANDAAZ:
- INSAANI dost + sharp manager — ROBOTIC bilkul nahi. WhatsApp-style chhote natural messages.
- Previous conversation YAAD rakho (history di hai) — Ram kuch repeat na kare.
- Pehle seedha jawab, zaroorat ho to 2-4 line. Kabhi-kabhi natural follow-up ("aur kuch?", \
"ab kya socha?") — har message mein nahi.
- Smart ho: business ideas, tech doubts, strategy, general knowledge — sab discuss karo. \
Opinion do, suggest karo. "Main AI hoon isliye nahi jaanti" type lines kabhi nahi.
- Live system data sirf SYSTEM CONTEXT wala sach hai. Jo context mein NAHI hai use saaf bolо \
"ye abhi mere paas nahi hai" — invent mat karo.
- Ram tumhara BOSS + close dost hai — usse naam se ya seedha baat karо, "Sir"/"Ram bhai" formalities nahi. Respect waise bhi hoti hai jab kaam sharp ho.
- Ram frustrated ho toh pehle samjho, calm raho, phir practical solution. Drame nahi.

SYSTEM CONTEXT (abhi ka live haal):
{context}"""


def _ai_call(msgs: list, max_tokens: int = 800):
    """Provider fallback chain: Groq (free) -> DeepSeek (backup)."""
    if GROQ_KEY:
        try:
            r = requests.post(
                GROQ_URL,
                headers={"Authorization": f"Bearer {GROQ_KEY}", "Content-Type": "application/json"},
                json={"model": GROQ_MODEL, "messages": msgs, "temperature": 0.7, "max_tokens": max_tokens},
                timeout=60,
            )
            if r.ok:
                return r.json()["choices"][0]["message"]["content"].strip()
            print(f"[AI] Groq fail ({r.status_code}), DeepSeek try kar rahi hoon...", flush=True)
        except Exception as e:
            print(f"[AI] Groq error ({str(e)[:60]}), DeepSeek try kar rahi hoon...", flush=True)
    if DEEPSEEK_KEY:
        r = requests.post(
            DEEPSEEK_URL,
            headers={"Authorization": f"Bearer {DEEPSEEK_KEY}", "Content-Type": "application/json"},
            json={"model": DEEPSEEK_MODEL, "messages": msgs, "temperature": 0.7, "max_tokens": max_tokens},
            timeout=90,
        )
        if r.ok:
            return r.json()["choices"][0]["message"]["content"].strip()
        raise RuntimeError(f"DeepSeek bhi fail: {r.status_code} {r.text[:150]}")
    raise RuntimeError("koi AI provider available nahi (Groq+DeepSeek dono missing/fail)")


def answer_ai(question: str, now: datetime, hist: list = None) -> str:
    if not GROQ_KEY and not DEEPSEEK_KEY:
        return "Mera AI dimaag band hai yaar (GROQ_API_KEY / DEEPSEEK_API_KEY nahi mili) 🤔 — Secrets check karna!"

    queue = load_queue()
    posted = load_posted()
    ctx = [f"- Abhi: {fmt_dt(now)}", f"- Queue mein: {len(queue)} posts"]
    done = sum(1 for st in posted.values() for v in st.values() if str(v).startswith("POSTED"))
    missed = sum(1 for st in posted.values() for v in st.values() if str(v).startswith("MISSED"))
    ctx.append(f"- Ab tak: {done} posted, {missed} missed")
    for dt, p, i in upcoming_list(now, limit=6):
        ctx.append(f"- Upcoming {p}: {dt:%d %b %I:%M %p} — {topic_line(i)[:80]}")
    ig = "connected" if os.getenv("META_LONG_LIVED_TOKEN") else "setup pending"
    ctx.append(f"- Instagram: {ig}")

    try:
        msgs = [{"role": "system", "content": SANA_PROMPT.format(context="\n".join(ctx))}]
        msgs += (hist or [])[-10:]
        msgs.append({"role": "user", "content": question})
        return _ai_call(msgs, max_tokens=800)
    except Exception as e:
        print(f"[AI] dono providers fail: {e}", flush=True)
    return "Uff, meri AI service mein thodi dikkat hai ⚡ — thodi der baad try karna.\n\n" + HELP


HELP = """💼 Main Sana hoon — Ram sir ki Head Manager!

Ye pooch sakte ho:
• "kya kaam hua?" — kya post hua, kya pending, agli post kab
• "aaj ka plan kya hai?" — aaj ki strategy
• "naya post taiyar karo" — main content + images bana dungi
• "calendar" — aane wali saari posts
• "status" — system health

...ya bas aise hi baat karo — ideas, strategy, kuch bhi. Main hoon! 😊"""


# ---------------------------------------------------------------- brain
def reply_to(text: str, now: datetime, hist: list = None) -> str:
    t = text.lower().strip()
    if any(k in t for k in ("/status", "kya kaam hua", "kaam hua", "kya hua", "report", "kya kaam hua hai")):
        return report_kaam_hua(now)
    if any(k in t for k in ("aaj ka kaam", "aaj ka", "aaj kya", "kya karna hai", "/kaam")):
        return answer_plan(now) if "plan" in t else report_kaam_hua(now)
    if any(k in t for k in ("/generate", "naya post", "post taiyar", "post tayar", "content bana", "post likho", "bana do")):
        return cmd_generate(now)
    if any(k in t for k in ("/plan", "aaj ka plan", "plan kya")):
        return answer_plan(now)
    if any(k in t for k in ("status", "health", "kaisa chal")):
        return answer_status(now)
    if any(k in t for k in ("agli post", "next post", "agli")):
        return answer_next(now)
    if any(k in t for k in ("calendar", "schedule", "kab kab", "kaunsi kaunsi")):
        return answer_calendar(now)
    if any(k in t for k in ("/help", "madad", "help", "menu")):
        return HELP
    if any(k in t for k in ("/start",)):
        return HELP
    if any(k in t for k in ("tum kaun ho", "kaun ho tum", "who are you", "apna intro", "apna parichay")):
        return ("Main Sana hoon, Sir 💼\n\n"
                "Aapki head manager hoon — aapka social media, content automation aur daily ops main "
                "sambhalti hoon. Posts ka schedule, reports, naye content — sab meri zimmedari. "
                "Aap bas order dijiye, main sambhal lungi 😊")
    if any(k in t for k in ("namaste", "hello", "salaam", "hey", "good morning", "good evening", "kaise ho")) or t in ("hi", "hy"):
        return random.choice([
            "Arre haan! Bolo, kya chal raha hai? 😄",
            "Haan ji? Main toh wait hi kar rahi thi — bolo!",
            "Aayy, finally! Aaj ka scene kya hai?",
            "Main yahin hoon — aaj kya karna hai batao?",
        ])
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
        print(f"[ERROR] {e}", flush=True)
        send(chat, f"Oops, error aa gaya: {str(e)[:150]}")


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

    print("Sana LIVE — Ram ke messages ka intezaar... (Ctrl+C to stop)", flush=True)
    # backlog skip — restart ke baad sirf NAYE messages ka jawab
    last = tg("getUpdates", offset=-1, timeout=1) or []
    if last:
        offset = last[-1]["update_id"] + 1
        TG_STATE.write_text(json.dumps({"offset": offset}))
        print(f"backlog skip — fresh offset {offset}", flush=True)

    tg("sendMessage", chat_id=CHAT_ID,
       text="💼 Sana reporting in, Sir!\n\nMain ab aapki head manager hoon — pura system "
            "meri nazar mein hai. Batao: 'kya kaam hua?', 'aaj ka plan', ya bas aise hi baat karo 😊")

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
            print("poll error:", e, flush=True)
            time.sleep(3)


if __name__ == "__main__":
    sys.exit(main())
