---
name: youtube_competitor_analysis
description: Fetches YouTube channel data using the YouTube Data API v3 with Google OAuth, saves video data as CSV, and generates AI-powered content creation suggestions by analyzing trending competitor videos vs the user's own channel. Use when the user wants to spy on YouTube competitors, find what's trending in their niche, or get specific video ideas backed by real performance data.
metadata: {"openclaw": {"requires": {"bins": ["uv"]}}}
---

# YouTube Competitor Analysis

IMPORTANT: Use only the exec tool. Never use sessions or sub-agents.

Scripts live in `{baseDir}/scripts/`. All exec calls use that path.
Script filenames are lowercase: `fetch.py` and `analyze.py`.
Always invoke scripts with `uv run --script` so dependencies are installed automatically — never call them with `python3` directly.

---

## Authentication

Before fetching any data, check if the user is authenticated by running fetch.py without arguments. If output contains `auth_url`:

1. Send the user this message:
   "Please open this link to connect your Google account: <auth_url>"

2. Wait for the user to paste back the code Google shows them.

3. Run:
   ```
   uv run --script {baseDir}/scripts/fetch.py --auth-code <CODE_FROM_USER>
   ```

4. On success (`"status": "authenticated"`), continue to data fetching.

If the output contains `"error": "no_credentials"`, tell the user:

> To use this skill, you need a Google OAuth Client ID. Here's how to get one:
> 1. Go to https://console.cloud.google.com/apis/credentials
> 2. Create a project, enable **YouTube Data API v3**
> 3. Create an **OAuth 2.0 Client ID** → Desktop app
> 4. Add `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET` to `~/.openclaw/openclaw.json` under `skills.entries.youtube_competitor_analysis.env`
> Or place the downloaded `credentials.json` directly in `{baseDir}/`

---

## Step 1 — Load or create config

Check if `{baseDir}/analyze_input.txt` exists.

**If it does NOT exist**, ask the user for:
- **Their own channel** — channel ID (`UC...`) or `@handle`
- **Competitor channels** — one or more `@handle`s or channel IDs (comma-separated)
- **Their niche** — e.g. "gaming", "horror games", "cooking"

Then create `{baseDir}/analyze_input.txt` with this exact format:

```
niche: gaming
my_channel: @MrBeast
competitors: @markiplier, @jacksepticeye, @PewDiePie
```

Tell the user:
> ✅ Config saved to `{baseDir}/analyze_input.txt`
> If you ever want to change your channel or competitors, just edit that file directly and trigger the skill again.

**If it exists**, read it and parse the three fields: `niche`, `my_channel`, `competitors` (split by comma). Proceed silently without asking the user anything.

---

## Step 2 — Fetch user's own channel (last 30 days)

Using `my_channel` from the config:

```
uv run --script {baseDir}/scripts/fetch.py --channel <my_channel> --days 30 --label my_channel
```

---

## Step 3 — Fetch each competitor (last 7 days)

Run once per entry in `competitors` from the config. Derive the label from the handle (strip `@`, lowercase):

```
uv run --script {baseDir}/scripts/fetch.py --channel <competitor> --days 7 --label comp_<short_name>
```

---

## Step 4 — Run the analyzer

Using `niche` from the config:

```
uv run --script {baseDir}/scripts/analyze.py --niche "<niche>"
```

This prints a JSON report with top videos by views for each channel.

---

## Step 5 — Generate content suggestions

After reading the JSON, produce a response in this format:

---
**📊 OpenClaw Analysis — [Niche]**

**Your channel (last 30 days)**
Videos: X | Avg views: X
Top video: "[title]" — X views

**Competitor pulse (last 7 days)**
- [label]: X videos | Avg X views | Top: "[title]" (X views)

**🔥 Trending right now**
- [specific topic, game, format, or hook dominating competitors this week]
- ...

**💡 Content ideas for you**
1. **[Concrete video title]** — [why: which competitor, what performance, what angle]
2. **[Concrete video title]** — [why: ...]
3. **[Concrete video title]** — [why: ...]

**📌 Title formulas working right now**
- "[Pattern from top videos]"

**🚀 Untapped opportunities**
[Topics competitors haven't covered well that could be an opening]

---

Be specific. Instead of "make a horror game video", say:
"Play Layers of Fear — comp_ign's walkthrough hit 340K views this week and nobody in your niche has covered it."

---

## Error reference

| Error | Fix |
|---|---|
| `not_authenticated` | Run setup flow — send user the auth_url |
| `no_credentials` | User needs to add Google OAuth credentials (see Authentication section) |
| `channel_not_found` | Try the raw `UC...` channel ID from the YouTube URL |
| `quotaExceeded` | Free quota is 10,000 units/day. Wait 24h or use a second Google Cloud project. |