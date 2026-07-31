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
   Calendar:
   - Go to the Google Cloud Console and create a project (or reuse one).
   - Enable the **Google Calendar API** for that project.
   - Configure the OAuth consent screen (choose "External" for a personal
     Google account, add your own email as a test user).
   - Create an **OAuth client ID** with application type **Desktop app**.
   - Download its JSON and save it as `credentials.json` in this repo's
     root (already gitignored — it will never be committed).
3. **Python 3.9+**.

## Setup

```bash
pip install -r requirements.txt
```

Place your downloaded `credentials.json` in the repo root (see
Prerequisites above).

The first time `/inbox-digest` creates a calendar event, the underlying
script opens a browser for one-time Google OAuth consent and caches a
refresh token in `token.json` (also gitignored). Every run after that is
silent.

## Usage

Inside a Claude Code session opened in this repo:

```
/learn-voice        # optional but recommended: builds VOICE.md from your Sent mail
/inbox-digest       # processes the last 24 hours of inbox activity
/inbox-digest 48    # or override the lookback window, in hours
```

## What this deliberately doesn't do

- Doesn't run automatically on a schedule (yet) — see the design spec's
  "Scheduling" section for how that would be layered on later via Claude
  Code's `schedule` skill, without any architecture change.
- Never sends an email or auto-approves anything — every reply is a draft
  you review; every calendar event is something you can just delete.
- No multi-account, no non-Gmail providers, no semantic/vector memory, no
  multi-platform reach (Slack/Asana/etc.) — see the design spec's
  "Non-goals" section for the full list and reasoning.

## License

MIT — see `LICENSE`.
