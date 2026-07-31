# AI Second Brain — Inbox Digest

A small Claude Code project that turns Gmail inbox activity into three
things a person actually wants each day: a plain-English summary, reply
drafts in your own writing voice, and Google Calendar events for anything
actionable. Runs on demand as a Claude Code skill — no server, no
database, no background daemon.

Scoped down from the larger ["AI Second Brain"](https://nextwork.ai/projects/ai-second-brain-claude-code)
concept to one focused slice: email triage, not a general proactive
assistant. See `docs/superpowers/specs/2026-08-01-inbox-digest-design.md`
for the full design rationale, including what was deliberately left out
and why.

## What it does

- **`/inbox-digest [hours]`** — scans inbox threads from the last N hours
  (default 24) that haven't been processed yet, and for each one:
  - Writes a 1-3 sentence summary and an Urgent/Normal/Low priority tag
    into a dated digest file (`digests/YYYY-MM-DD.md`).
  - If it's reply-worthy (a real question or request, not a newsletter or
    notification), drafts a reply — in your own writing voice if
    `VOICE.md` exists — as a real Gmail draft. **Never sends automatically.**
  - If it's actionable (implies a deadline or follow-up), creates a real
    Google Calendar event via `scripts/add_calendar_event.py`.
  - Labels the thread `SecondBrain/Processed` so it's never redone.
- **`/learn-voice [sample_size]`** — samples your Sent mail (default 30
  messages) and writes/refreshes `VOICE.md`, a style profile `/inbox-digest`
  reads when drafting replies. Your own hand-written notes in `VOICE.md`'s
  "Manual overrides" section are preserved across refreshes.

See `examples/sample-digest.md` and `examples/sample-voice.md` for
(anonymized, invented) sample output — real output stays local and
gitignored since it's derived from your actual inbox.

## Prerequisites

1. **A Claude Code session with the Gmail MCP connector configured** for
   the Gmail account you want this to run against. This project doesn't
   include its own Gmail integration — it drives the Gmail tools your
   Claude Code session already has.
2. **A Google Cloud project with the Calendar API enabled, and an OAuth
   client of your own**, since there's no equivalent MCP shortcut for
   Calendar. Free, one-time, about 10 minutes:

   1. Go to the [Google Cloud Console](https://console.cloud.google.com/)
      and sign in with the Google account whose calendar you want events
      created on.
   2. Click the project dropdown (top left) → **New Project** → give it
      any name (e.g. `ai-second-brain`) → **Create**.
   3. Go to **APIs & Services → Library**, search for **Google Calendar
      API**, open it, and click **Enable**.
   4. Go to **APIs & Services → OAuth consent screen**, click **Get
      Started**, and fill in:
      - App name: anything (e.g. `Inbox Digest`)
      - User support email: your email
      - Audience: **External**
      - Add your own email under **test users**
      - Developer contact email: your email
      - Save through the remaining steps. Leave **Publishing status** as
        **Testing** — moving it to Production requires Google's formal
        app-verification review for the Calendar scope, which is
        overkill for a personal tool only you will ever authenticate.
   5. Go to **APIs & Services → Credentials → Create Credentials →
      OAuth client ID**. Application type: **Desktop app**. Give it any
      name and click **Create**.
   6. Click **Download JSON** on the client you just created (or find it
      later in the Credentials list and click its download icon).
   7. Rename the downloaded file to `credentials.json` and place it in
      this repo's root directory (already gitignored — it will never be
      committed).

   **Known limitation:** because the app stays in Testing mode, Google
   expires its refresh token every **7 days**. Roughly once a week, the
   next `/inbox-digest` run that needs to create a calendar event will
   pop open a browser for a ~10-second re-consent instead of running
   silently — expected, not a bug. The very first time you authenticate,
   Google will also show an "unverified app" warning screen (since this
   is your own personal, unreviewed OAuth client) — click **Advanced →
   Go to `<app name>` (unsafe) → Continue**. This is safe; it's just
   Google flagging that the app hasn't gone through their formal review,
   which isn't necessary for a single-user personal tool.
3. **Python 3.9+**.

## Setup

```bash
pip install -r requirements.txt
```

Place your downloaded `credentials.json` in the repo root (see
Prerequisites above).

**Before running `/inbox-digest` for the first time, complete a one-time
Calendar OAuth bootstrap yourself, directly in your own terminal** (not
through Claude Code). This step needs a human to click through a browser
consent flow, which doesn't work reliably as a subprocess launched
automatically mid-digest-run — `/inbox-digest` checks for this and skips
calendar-event creation gracefully if it hasn't been done yet, rather
than hanging.

```bash
python scripts/add_calendar_event.py --summary "Calendar bootstrap test" --description "one-time OAuth setup" --date "2026-08-10T09:00:00"
```

A browser window will open. Sign in, and click through Google's
"unverified app" warning (**Advanced → Go to `<app name>` (unsafe) →
Continue** — safe, since it's your own personal OAuth client). Once
approved, the command prints the created event's link and a `token.json`
file appears in the repo root. Delete that test event from your calendar
afterward.

After this one-time bootstrap, `/inbox-digest` creates calendar events
silently — until the token expires after 7 days (see the Testing-mode
limitation under Prerequisites above), at which point one more quick
browser consent is needed.

## Usage

Inside a Claude Code session opened in this repo:

```
/learn-voice        # optional but recommended: builds VOICE.md from your Sent mail
/inbox-digest       # processes the last 24 hours of inbox activity
/inbox-digest 48    # or override the lookback window, in hours
```

### Quick launch (Windows)

`scripts/launch.bat` opens a terminal already in this repo's root,
starts Claude Code interactively, and auto-submits `/inbox-digest` as the
first message — no typing needed. It's still fully interactive: every
Gmail/Calendar action still asks for your permission normally, nothing
is bypassed, you can watch and stop it like any other session.

To run `/learn-voice` instead, pass it as an argument:
`scripts\launch.bat "/learn-voice"`.

Pin it to your taskbar/Start (Windows sometimes hides "Pin to taskbar"
for raw `.bat` files, so use a shortcut through `cmd.exe` if the direct
option is missing):

1. Right-click Desktop → **New → Shortcut**.
2. Location: `cmd.exe /k "C:\path\to\ai-second-brain\scripts\launch.bat"`
   — or add `"/learn-voice"` at the end for a second shortcut that runs
   that skill instead.
3. Name it, then right-click the shortcut → **Pin to Start** / **Pin to
   taskbar**.

## Automatic daily digest (email-only)

A scheduled cloud routine runs `/inbox-digest` once a day via Claude
Code's `schedule` skill, so a digest exists without you opening a session
at all. Two things are true about it that don't apply to a local run:

- **No calendar events.** Cloud routines get a fresh git checkout each
  run with no access to your local machine — `credentials.json` and
  `token.json` don't exist there, so calendar-event creation is skipped
  every time (by design, via the same `token.json` check documented
  above). You still need a local `/inbox-digest` run to actually get
  calendar events for actionable items.
- **No voice personalization.** `VOICE.md` is gitignored and local-only
  for the same reason, so cloud-drafted replies are always neutral-tone,
  never the learned voice from `/learn-voice`.
- The full per-thread digest (not just counts) is included in the
  routine's chat output, since `digests/*.md` itself can't persist
  between cloud runs either — view it at the routine's page on
  [claude.ai/code/routines](https://claude.ai/code/routines).

`/learn-voice` is not cloud-scheduled at all, for the same
fresh-checkout-every-run reason — it only makes sense run locally, where
`VOICE.md` actually persists on disk for future local runs to read.

## What this deliberately doesn't do

- Doesn't run the full pipeline (including calendar events and voice
  personalization) automatically — only the email-triage half is
  cloud-scheduled, per the limitations above. Getting calendar/voice
  automated too would mean local scheduling (e.g. Windows Task
  Scheduler) instead of a cloud routine, since it needs access to local
  secrets that shouldn't leave the machine.
- Never sends an email or auto-approves anything — every reply is a draft
  you review; every calendar event is something you can just delete.
- No multi-account, no non-Gmail providers, no semantic/vector memory, no
  multi-platform reach (Slack/Asana/etc.) — see the design spec's
  "Non-goals" section for the full list and reasoning.

## License

MIT — see `LICENSE`.
