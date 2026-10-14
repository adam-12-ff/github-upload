# 🛠️ SETUP GUIDE — Arjun Auto-Poster (Ek baar karo, hamesha ke liye chalo)

Total time: ~45-60 minute (one-time). Uske baad **zero manual kaam** — posts khud hongi.

> ⚠️ Important: GitHub repo **PUBLIC** banana hoga (Instagram ko images publicly
> accessible URL chahiye hote hain). Aapka content toh waise bhi public hai, isliye
> koi problem nahi. **Tokens kabhi repo files mein nahi — sirf Secrets mein.**

---

## PART 1 — Instagram Professional Account (5 min)

### Pehle CHECK karo (aapko pata nahi tha toh):
1. Instagram app kholo → **Profile** → ☰ menu → **Settings and activity**
2. Neeche scroll → **Account type and tools** kholo
3. Ab dekho:
   - Agar likha hai **"Switch to professional account"** → aapka account abhi PERSONAL hai (convert karna padega)
   - Agar **"Add new professional account"** / account type mein **Business/Creator** dikh raha hai → already professional hai ✅
   - Shortcut: Apni profile pe **Category label** (jaise "Digital creator", "Business") dikh raha hai = professional hai

### Convert karna hai (personal → Business):
1. **Settings and activity → Account type and tools → Switch to professional account**
2. Category choose karo: **Digital creator** ya **Internet marketing service**
3. Type: **Business** (Creator bhi chalega, Business recommended)
4. Done ✅

### Facebook Page se link karo (ZAROORI — API isi se chalta hai):
1. Facebook pe ek **Page** banao (agar nahi hai) — apne brand ke naam ka
2. Instagram → **Settings → Business tools and contacts** (ya desktop pe instagram.com → Edit profile) → **Connect a Facebook Page** → apna page select karo
3. ✅ Ab Instagram Graph API use kar sakte hain

---

## PART 2 — Facebook App banao (10 min)

1. **developers.facebook.com** pe jao → Facebook account se login
2. Top-right **Get Started / My Apps** → **Create App**
3. Use case: **Business** type select karo → App name: "Social Auto Poster" → Create
4. App dashboard → **Add Product** → **Facebook Login** add karo
5. Facebook Login → **Settings**:
   - **Valid OAuth Redirect URIs**: `http://localhost:8080/callback`
   - Save
6. **Settings → Basic** se copy karo:
   - **App ID** → ye `META_APP_ID` hai
   - **App Secret** → ye `META_APP_SECRET` hai

> Note: App **Development mode** mein hi rahega — apne khud ke accounts pe kaam karta
> hai, review ki zaroorat nahi. Perfect for personal automation.

---

## PART 3 — Meta tokens lo (5 min)

Apne PC pe (Python 3.10+ installed hona chahiye):

```bash
pip install requests
python meta_auth.py
```

- Browser khulega → Facebook login → **Allow**
- Script apke Pages dikhayega → apna brand page choose karo
- Script print karegi:
  - `META_APP_ID`, `META_APP_SECRET`
  - `META_LONG_LIVED_TOKEN` ✅
  - `META_PAGE_ID` ✅

**Ye 4 values kahin save kar lo** — Step Part 5 mein Secrets mein daalenge.

> Token ka sach: `META_LONG_LIVED_TOKEN` ~60 din ka hota hai, LEKIN `poster.py`
> har run pe ise khud refresh karta hai — aapko kabhi kuch nahi karna.
> (Sirf agar 2+ mahine system band raha, toh `meta_auth.py` dobara chalana.)

---

## PART 4 — LinkedIn App + tokens (15 min)

### Step 4.1 — LinkedIn Page banao (agar nahi hai) — 3 min
App banate waqt LinkedIn Page DENA zaroori hai (bina page app nahi banta):
1. **linkedin.com** → login → top-right **"For Business"** grid icon → **Create a Company Page** (+)
2. Type: **Company** select karo (freelancer ke liye bhi yahi theek hai)
3. Details bharo: Name (jaise "Ram — Web & AI Solutions"), Industry: **Software Development**, Size: **1-10**
4. Page live ✅ — aap uske **Admin** ho (yahi zaroori hai)

### Step 4.2 — App banao — 5 min
1. **developer.linkedin.com** → login → **Create App**
2. Form bharo:
   - App name: "Ram Auto Poster"
   - **LinkedIn Page**: apna naya page search karke select karo
   - Logo: koi bhi square image (apni profile photo chalegi)
   - Legal agreement ✅ → **Create app**
3. **App VERIFY karo (zaroori)**: App kholo → **Settings** tab → **"Verify App"** section → verification **link copy** karo → **usi browser mein kholo** (aap page admin ho) → **Verify** dabao ✅
   - Ye step na ho toh API reject hota hai!

### Step 4.3 — Products add karo — 2 min
App → **Products** tab → dono add karo (dono INSTANT milte hain, koi review nahi):
   - ✅ **"Share on LinkedIn"** → Request access → terms accept
   - ✅ **"Sign In with LinkedIn using OpenID Connect"** → Request access

### Step 4.4 — Auth tab — 2 min
1. **Auth** tab → neeche **OAuth 2.0 settings → Redirect URLs** → edit → ye daalo:
   `http://localhost:8000/callback` → Save
2. Upar hi: **Client ID** + **Client Secret** copy kar lo

### Step 4.5 — Tokens lo — 3 min
Apne PC pe (Python installed hona chahiye):

```bash
pip install requests

# Windows CMD:
set LINKEDIN_CLIENT_ID=apna_client_id
set LINKEDIN_CLIENT_SECRET=apna_client_secret
python linkedin_auth.py

# PowerShell:
$env:LINKEDIN_CLIENT_ID="apna_client_id"
$env:LINKEDIN_CLIENT_SECRET="apna_client_secret"
python linkedin_auth.py

# Mac/Linux:
export LINKEDIN_CLIENT_ID=apna_client_id
export LINKEDIN_CLIENT_SECRET=apna_client_secret
python linkedin_auth.py
```

- Browser khulega → LinkedIn login → **Allow**
- Script print karegi:
  - `LINKEDIN_REFRESH_TOKEN` ✅ (365 din valid — auto-refresh)
  - `LINKEDIN_MEMBER_URN` ✅

> Token ka sach: Refresh token se `poster.py` har run pe naya access token le
> leta hai — expiry ki tension khatam. Agar refresh token na mile toh access
> token 60 din ka hota hai — phone mein reminder lagao, 55 din baad script
> dobara chalana (2 min ka kaam).

---

## PART 5 — GitHub pe sab setup (10 min)

1. **github.com** → New repository → naam: `auto-poster` → **Public** ✅ → Create
2. Ye pura `auto-poster` folder upload karo (ya `git push`)
3. Repo → **Settings → Secrets and variables → Actions** → **New repository secret**

Ye secrets add karo (Part 3 + 4 se mile the):

| Secret name | Value |
|---|---|
| `LINKEDIN_CLIENT_ID` | Part 4 se |
| `LINKEDIN_CLIENT_SECRET` | Part 4 se |
| `LINKEDIN_REFRESH_TOKEN` | Part 4 se (ya `LINKEDIN_ACCESS_TOKEN`) |
| `META_APP_ID` | Part 3 se |
| `META_APP_SECRET` | Part 3 se |
| `META_LONG_LIVED_TOKEN` | Part 3 se |
| `META_PAGE_ID` | Part 3 se |
| `BOSS_HANDLE` *(optional)* | Image footer text, default: `Ram • Freelance Dev & AI Builder` (Instagram handle ho toh wo daalo, jaise `@ram.builds`) |

4. Repo → **Actions** tab → agar notification hai "Workflows aren't being run" → **Enable** karo

---

## PART 6 — Test karo (5 min)

### DRY RUN (safe — kuch post nahi hoga):
1. Repo → **Actions** → **Auto-Post (Arjun)** → **Run workflow**
2. `dry_run = true` select karo → **Run workflow**
3. Log kholo — dikhna chahiye:
   ```
   [DRY-RUN] 2026-09-28-p1/linkedin post hota (schedule: 2026-09-28T08:00:00+05:30)
   ```
   ✅ Matlab system sab sahi detect kar raha hai

### Real test (ek dummy post se):
1. `content/queue.json` mein ek test post daalo — `schedule` aaj ke ~10 min baad ka time
2. Actions → Run workflow (dry_run = false)
3. LinkedIn/Instagram pe post aayi? 🎉 **SYSTEM LIVE HAI!**
4. Test post queue se hata do

---

## PART 7 — Roz ka usage (2 min bhi nahi lagta)

System ke baad **sab automatic**:
- **Mon/Wed/Fri/Sun** — LinkedIn 8:00 AM, Instagram 6:00 PM pe khud post hoga
- Aapko sirf notifications milenge "posted successfully 🎉"

### Naya content chahiye?
Mujhe (Arjun) bolo: **"Next week ka content bana do"** — main fresh posts likh ke
`queue.json` update kar dunga. Aap bas pull karke push kar dena.

### Khud edit karna ho?
`content/queue.json` kholo — har post ka text/caption/schedule simple JSON hai.
Schedule change = sirf date-time badlo. Post hatana = us object ko delete karo.

### Content manually check karna?
`content/CONTENT_CALENDAR.md` mein sab posts readable format mein hain.

---

## PART 8 — Troubleshooting

| Problem | Fix |
|---|---|
| `Instagram: image fetch fail` | Repo public hai? `IMAGE_BASE_URL` secret set karo (koi public image host) |
| `Meta: code 190` (token invalid) | `meta_auth.py` dobara chalao, naya token Secrets mein daalo |
| `LinkedIn 403/422` | LinkedIn app mein dono Products added hain? Refresh token sahi hai? |
| Posts due thi par post nahi hui (MISSED) | Actions tab mein check karo workflow disabled toh nahi. Repo mein koi activity nahi hoti 60 din toh GitHub cron band kar deta hai — state.json commits isse bachate hain |
| Carousel images missing | Locally ya Actions mein `make_image.py` run hota hai hi — manually: `python make_image.py --id POST_ID` |
| Schedule time alag chahiye | `queue.json` mein `schedule` edit karo. Workflow cron bhi badal sakte ho (UTC mein hai — IST = UTC + 5:30) |

---

## 🔐 Token expiry ka sach (dhyaan rakho)

- **LinkedIn**: refresh token → automatic ✅
- **Meta/IG**: long-lived token → automatic refresh har run pe ✅
- **Kabhi-kabhi** (2+ mahine system off, password change, app deleted): auth scripts dobara chalao
- Tokens **kabhi** repo files mein commit mat karo — sirf GitHub Secrets 🙏
