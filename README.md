# 🤖 Arjun Auto-Poster

**LinkedIn + Instagram pe automatic posting system** — GitHub Actions pe free chalta hai.

```
 content/queue.json          GitHub Actions (cron — FREE)
 ┌──────────────────┐        ┌─────────────────────────────┐
 │  Ready content   │──────▶ │  Roz 08:15 AM & 06:30 PM    │
 │  (Arjun banata   │        │  1. make_image.py (visuals) │
 │   hai)           │        │  2. poster.py (posting)     │
 └──────────────────┘        └──────────┬──────────────────┘
                                        │
                            ┌───────────┴───────────┐
                            ▼                       ▼
                       🔗 LinkedIn            📸 Instagram
                      (LinkedIn API)        (Graph API)
```

## 📁 Files

| File | Kaam |
|---|---|
| `poster.py` | Main engine — due posts ko LinkedIn/IG pe publish karta hai |
| `make_image.py` | Branded text-card images generate karta hai (LinkedIn 1200×628, IG 1080×1350 carousels) |
| `content/queue.json` | Content queue — schedule ke saath. **Arjun yahi update karta hai** |
| `content/state.json` | Kis post ka status (auto-save hota hai, hath mat lagao) |
| `linkedin_auth.py` | One-time: LinkedIn tokens nikalne ke liye |
| `meta_auth.py` | One-time: Instagram/Meta tokens nikalne ke liye |
| `.github/workflows/auto-post.yml` | GitHub Actions ka cron scheduler |
| `SETUP_GUIDE.md` | **Pura setup step-by-step — yahi padho** |
| `content/CONTENT_CALENDAR.md` | Aane wala content readable format mein (review/edit ke liye) |

## 🚀 Quick start (detail SETUP_GUIDE.md mein)

1. Instagram ko **Professional (Business)** account banao + Facebook Page se link karo
2. Facebook App + LinkedIn App banao (donon free hain)
3. `meta_auth.py` + `linkedin_auth.py` chala ke tokens lo
4. Ye repo GitHub pe **public** banao + tokens **Secrets** mein daalo
5. Actions enable karo → bas! Posts khud hongi 🎉

## ✍️ Content flow

- Boss bolta hai: **"Arjun, next week ka content bana do"** → Arjun `queue.json` update karta hai → push karo → done
- Ya khud `queue.json` edit karo (format simple hai, existing posts dekho)

## ⏰ Schedule (IST)

| Din | Pillar | LinkedIn | Instagram |
|---|---|---|---|
| Monday | AI Agent ka Jaadoo | 8:00 AM | 6:00 PM |
| Wednesday | Website & App Secrets | 8:00 AM | 6:00 PM |
| Friday | Problem vs Solution | 8:00 AM | 6:00 PM |
| Sunday | Pitch & Proof | 8:00 AM | 6:00 PM |
