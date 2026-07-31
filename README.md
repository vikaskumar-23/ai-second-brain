# AI Second Brain — Inbox Digest

A Claude Code skill that turns daily Gmail activity into three things
worth having: a plain-English summary, reply drafts written in your own
voice, and Google Calendar events for anything that needs follow-up.

Deliberately scoped down from the broader ["AI Second Brain"](https://nextwork.ai/projects/ai-second-brain-claude-code)
pattern — one focused slice (email triage) done well, instead of a
general-purpose proactive agent. The full design rationale, including
what was intentionally left out and why, is in
[`docs/superpowers/specs/2026-08-01-inbox-digest-design.md`](docs/superpowers/specs/2026-08-01-inbox-digest-design.md).

## Features

- **`/inbox-digest [hours]`** — scans unprocessed inbox threads from the
  last N hours (default 24). For each thread:
  - Summarizes it and tags a priority (Urgent / Normal / Low)
  - Drafts a reply in the user's own voice, if warranted — saved as a
    real Gmail draft, **never sent automatically**
  - Creates a real Google Calendar event if it implies a deadline or
    follow-up
  - Labels the thread so it's never reprocessed
- **`/learn-voice [sample_size]`** — builds a writing-style profile from
  the user's own Sent mail, which `/inbox-digest` uses to draft
  replies that actually sound like them. Manual edits to the profile
  survive future refreshes.
- **Runs on demand or on a schedule** — a Claude Code skill invoked
  directly, or wrapped in a scheduled cloud routine for a fully
  automatic daily run (see [Automation](#automation)).

Sample output: [`examples/sample-digest.md`](examples/sample-digest.md),
[`examples/sample-voice.md`](examples/sample-voice.md) — anonymized,
invented data. Real output stays local and gitignored, since it's
derived from a real inbox.

## How it's built

```
ai-second-brain/
├── .claude/skills/
│   ├── inbox-digest/SKILL.md       # orchestrates Gmail via MCP + the calendar script
│   └── learn-voice/SKILL.md        # builds the writing-style profile
├── scripts/
│   ├── add_calendar_event.py       # Google Calendar OAuth2 + API client
│   ├── test_add_calendar_event.py  # unit tests, mocked API client
│   └── launch.bat                  # one-click local launcher (Windows)
├── examples/                       # anonymized sample output
├── docs/superpowers/                # design spec + implementation plan
├── requirements.txt
└── LICENSE
```

Two Claude Code skills orchestrate the Gmail MCP connector directly — no
custom Gmail integration was written, since the connector already
provides one. The single exception is Google Calendar, where no MCP
equivalent exists; that's the one place this project has real,
independently-tested Python: a small OAuth2 + Calendar API client with
its own unit tests (mocked, no live credentials required to run them).

**Notable decisions:**
- **MCP-first, code only where nothing free exists.** Rather than
  building a Gmail client from scratch, the skills drive Gmail's
  existing MCP tools; the Calendar script exists only because that
  shortcut doesn't exist for Calendar.
- **Hybrid automation, not one-size-fits-all.** A scheduled cloud
  routine runs the email-triage half daily. Calendar events and voice
  personalization stay local by design — cloud routines get a fresh,
  ephemeral git checkout per run with no access to local secrets
  (`credentials.json`, `token.json`, `VOICE.md`), so anything depending
  on them can't run there. The skill detects this and degrades
  gracefully instead of failing.
- **Two real bugs found and fixed post-deployment**: a Windows-specific
  IPv4/IPv6 loopback mismatch that crashed the OAuth flow instead of
  timing out cleanly, and a hardcoded UTC timezone that silently shifted
  every calendar event by 5.5 hours against the user's local time.

## Prerequisites

1. **Claude Code with the Gmail MCP connector configured.** This project
   has no Gmail integration of its own — it drives the Gmail tools
   already available in the session.
2. **A Google Cloud project with the Calendar API enabled and an OAuth
   client** — free, one-time, ~10 minutes:
   1. [Google Cloud Console](https://console.cloud.google.com/) → new
      project.
   2. **APIs & Services → Library** → enable **Google Calendar API**.
   3. **APIs & Services → OAuth consent screen** → **Get Started** →
      Audience **External**, add your own email as a **test user**,
      save through the remaining steps, leave publishing status as
      **Testing** (full verification isn't worth it for a single-user
      tool — see limitation below).
   4. **APIs & Services → Credentials → Create Credentials → OAuth
      client ID** → type **Desktop app** → Create.
   5. Download the client JSON, rename to `credentials.json`, place at
      the repo root (gitignored — never committed).
3. **Python 3.9+**.

> **Known limitation:** apps left in Testing mode get a refresh token
> that expires every 7 days, so roughly weekly the next calendar-event
> creation needs a ~10-second browser re-consent instead of running
> silently. Moving to Production would require Google's formal
> verification review for the Calendar scope — disproportionate for a
> tool only one person will ever authenticate.

## Setup

```bash
pip install -r requirements.txt
```

Then complete a **one-time Calendar OAuth bootstrap**, run directly in a
terminal (not through Claude Code — it requires a human to click through
a browser consent flow, which doesn't work as a subprocess mid-run):

```bash
python scripts/add_calendar_event.py --summary "Bootstrap test" --description "one-time OAuth setup" --date "2026-08-10T09:00:00"
```

Sign in, click through Google's "unverified app" warning (**Advanced →
Go to `<app name>` (unsafe) → Continue** — safe, it's your own OAuth
client), and approve. This prints the created event's link and writes
`token.json` (gitignored). Delete the test event afterward. From then on,
`/inbox-digest` creates calendar events silently until the 7-day token
expiry above.

## Usage

Inside a Claude Code session opened in this repo:

```
/learn-voice        # optional but recommended: builds VOICE.md from Sent mail
/inbox-digest       # processes the last 24 hours of inbox activity
/inbox-digest 48    # or override the lookback window, in hours
```

**Windows quick launch:** `scripts/launch.bat` opens a terminal in the
repo root and starts Claude Code with `/inbox-digest` pre-submitted —
still fully interactive, every action still asks for permission as
normal. Pass an argument (`launch.bat "/learn-voice"`) to run a different
skill. Pin it via a shortcut to `cmd.exe /k "path\to\launch.bat"`
(Windows often hides "Pin to taskbar" for raw `.bat` files, but always
allows it for a shortcut targeting an actual `.exe`).

## Automation

A scheduled cloud routine (Claude Code's `schedule` skill) runs
`/inbox-digest` once daily, so a digest exists without opening a
session. It only covers the email-triage half:

| | Local run | Cloud routine |
|---|---|---|
| Summaries, priority, labeling | ✅ | ✅ |
| Reply drafts | ✅ | ✅ (neutral tone) |
| Voice personalization | ✅ | ❌ (`VOICE.md` is local-only) |
| Calendar events | ✅ | ❌ (`token.json` is local-only) |

Since `digests/*.md` also can't persist between ephemeral cloud runs,
the routine reports full per-thread content in its chat output — that's
the durable record for cloud runs, viewable at
[claude.ai/code/routines](https://claude.ai/code/routines).
`/learn-voice` is intentionally not cloud-scheduled, for the same reason
its output wouldn't survive to the next run.

## Testing

```bash
cd scripts
python -m unittest test_add_calendar_event -v
```

Covers event-body construction (timed and all-day events, timezone
handling) and the Calendar API call shape, via a mocked client — no live
credentials or network access needed.

## Non-goals

- No auto-send, no bypassing user review — every reply is a draft,
  every calendar event is deletable.
- No multi-account or non-Gmail support, no semantic/vector memory, no
  multi-platform reach (Slack/Asana/etc.).
- No fully unattended local automation — a script with silent,
  permission-bypassed access to real email and calendar actions is a
  deliberate line not crossed here.

Full reasoning for these in the [design spec](docs/superpowers/specs/2026-08-01-inbox-digest-design.md).

## License

MIT — see [`LICENSE`](LICENSE).
