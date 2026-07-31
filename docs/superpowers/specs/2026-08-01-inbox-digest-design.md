# Inbox Digest — Design Spec

**Date:** 2026-08-01 (rev. 2 — adds Google Calendar task delivery)
**Status:** Pending user re-approval after Calendar revision

## Summary

A small, resume-showcase project: a Claude Code **skill** that turns Gmail
inbox activity into three things a person actually wants each day:

1. A plain-English **summary** of what came in.
2. **Proposed replies**, saved as real Gmail drafts for the user to edit and
   send — never auto-sent.
3. **Suggested tasks**, created as real **Google Calendar events** (not a
   markdown list — see rev. 2 note below).

It runs on demand, inside a Claude Code session with the Gmail MCP
connector configured, driven by a skill prompt plus:
- **Gmail MCP tools** (already available, no new integration needed):
  `search_threads`, `get_thread`/`get_message`, `create_draft`,
  `label_thread`, `create_label`, `list_labels`.
- **A small Python script** (`scripts/add_calendar_event.py`) that the
  skill invokes via shell to create Google Calendar events, since no
  Calendar MCP tool exists in this environment. This is the one place
  real, standalone programming-language code exists in the project — the
  Gmail side deliberately stays code-free because the MCP connector
  already provides it for free; Calendar doesn't have that shortcut, so
  it gets the real API client instead.

**Rev. 2 change:** originally tasks were appended to a local `TASKS.md`.
That's now replaced entirely by Google Calendar events, per explicit
request, to (a) get real due-date/reminder behavior a static file can't
give, and (b) put an actual piece of programming-language code in the
repo for portfolio purposes.

## Non-goals (v1)

- No custom Gmail OAuth/API client — the Gmail MCP connector already
  provides this; building a parallel integration would duplicate what's
  free.
- No standalone scheduler/daemon — scheduling is a documented *future*
  phase, layered on via the existing `schedule` skill (cron-based cloud
  agent invoking the same skill), not built now.
- No classifier/NLP/date-parsing library — "is this reply-worthy,"
  "is this actionable," and "what date does this refer to" are judgment
  calls Claude makes inline as part of the skill prompt (it already knows
  today's date from session context), not a separate model or library.
- No multi-account support, no non-Gmail providers.
- No general-purpose calendar management (editing/deleting existing
  events, checking availability) — write-only, one event per task.

## Architecture

```
ai-second-brain/
├── README.md                       # what it is, setup (incl. Google Cloud/OAuth steps), how to run
├── LICENSE                         # MIT
├── requirements.txt                # google-auth, google-auth-oauthlib, google-api-python-client
├── .claude/
│   └── skills/
│       └── inbox-digest/
│           └── SKILL.md            # the skill: instructions + tool-call sequence
├── scripts/
│   ├── add_calendar_event.py       # real code: OAuth + Calendar API event creation
│   └── test_add_calendar_event.py  # unit test with a mocked Calendar API client
├── examples/
│   └── sample-digest.md            # anonymized fake-data example run output
├── digests/                        # real output — gitignored (private inbox content)
├── credentials.json                # user's OAuth client secret — gitignored, never committed
├── token.json                      # OAuth refresh token, created on first run — gitignored
└── .gitignore
```

Only the skill, script, tests, README, LICENSE, `requirements.txt`, and
anonymized example are tracked in git. `digests/*.md`, `credentials.json`,
and `token.json` are gitignored — the first is private email content, the
other two are secrets.

## Skill behavior (`/inbox-digest`)

Invoked manually as `/inbox-digest`, optionally with a lookback-hours
override passed as the skill's argument string, e.g. `/inbox-digest 48`
(default 24 if no argument given). Steps:

1. **Ensure label exists.** `list_labels`; if `SecondBrain/Processed` is
   absent, `create_label` it.
2. **Fetch candidates.** `search_threads` with query
   `newer_than:1d -label:SecondBrain/Processed in:inbox` (lookback
   substituted if overridden). Cap at 50 threads per run — a documented
   limit to keep a single run's context bounded, not a silent drop. If the
   cap is hit, the digest notes how many threads were left unprocessed so
   the user can re-run with a narrower window.
3. **Per thread:** fetch content via `get_thread`/`get_message`, then reason
   inline (no separate code path):
   - **Summary** — 1-3 sentence gist of the thread.
   - **Reply-worthy?** — a direct question, request, or action aimed at the
     user → yes; newsletter, automated notification, or FYI/CC-only thread
     → no.
   - **Actionable?** (independent judgment, broader than reply-worthy) —
     anything implying a task for the user (deadline, request, follow-up),
     including threads that don't need a reply at all (e.g. an automated
     "invoice due Friday" notice).
   - **When (if actionable)?** — resolve any explicit/relative date in the
     email (e.g. "by Friday") against today's date. If no date is stated,
     default to an all-day event on the next business day — a documented
     heuristic, not silent guessing (noted in the digest as "no explicit
     date found, defaulted").
4. **Act on judgments:**
   - Reply-worthy → `create_draft` with proposed reply body. Never sent
     automatically.
   - Actionable → shell out to
     `python scripts/add_calendar_event.py --summary "..." --description "..." --date "..."`
     to create a Google Calendar event; capture the returned event link.
   - Always → append an entry to today's `digests/YYYY-MM-DD.md`.
5. **Mark processed.** `label_thread` with `SecondBrain/Processed` so the
   next run's search excludes it regardless of read/unread state.
6. **Report.** Short in-chat summary: N threads processed, M drafts created,
   K calendar events created, and how many (if any) were left unprocessed
   due to the cap.

## `scripts/add_calendar_event.py`

A single-purpose CLI script, not a library or service:

- **Auth**: standard Google OAuth "installed app" flow
  (`google-auth-oauthlib.flow.InstalledAppFlow`) — reads `credentials.json`
  (the OAuth client the user creates in Google Cloud Console), opens a
  browser for one-time consent, caches the resulting refresh token in
  `token.json`. Subsequent runs reuse the cached token silently.
- **Args**: `--summary`, `--description`, `--date` (ISO date, or
  date+time), `--all-day` (flag; used when no explicit time was found).
- **Action**: builds an event body and calls
  `service.events().insert(calendarId='primary', body=...)`.
- **Output**: prints the created event's `htmlLink` to stdout (nothing
  else) so the calling skill can capture it and put it in the digest.
- **`--dry-run` flag**: builds and prints the event body without calling
  the API — used by the test and for manual sanity-checking without
  touching a real calendar.

## Data formats

`digests/2026-08-01.md`:

```
# Inbox Digest — 2026-08-01

## "Q3 budget review" — jane@co.com
Summary: Jane needs sign-off on Q3 numbers by Friday.
Reply drafted: Yes
Calendar event: Yes — https://calendar.google.com/event?eid=...
```

## Error handling

- A single thread failing (e.g. `create_draft` or calendar-script error)
  does not stop the run — it's noted in the digest as "reply draft
  failed" / "calendar event failed" and the run continues to the next
  thread.
- If `search_threads` itself fails (e.g. auth/connector issue), the skill
  reports the failure clearly rather than silently producing an empty
  digest.
- If `add_calendar_event.py` fails because `credentials.json` is missing
  or OAuth hasn't been completed yet, the skill surfaces that specific
  cause (not a generic error) since it's a one-time setup step documented
  in the README.

## Scheduling (future phase, not built now)

Once proven on demand, wrap the same skill with the existing `schedule`
skill (cron-based cloud agent) to fire `/inbox-digest` on a recurring
schedule (e.g. daily). No architecture change — same skill, same tool
calls, just an automatic trigger instead of a manual one.

## Repo/showcase considerations

- Public GitHub repo, MIT license. README documents two prerequisites
  clearly: (1) a Claude Code session with the Gmail MCP connector
  configured, and (2) a Google Cloud project with the Calendar API
  enabled and an OAuth client (`credentials.json`) the user creates
  themselves — this is not a hosted or installable end-user product, and
  no secrets ship in the repo.
- `examples/sample-digest.md` uses invented sender names/subjects so the
  repo demonstrates output shape without exposing any real inbox content.

## Testing / verification

- **Skill (prompt-driven, no branching code):** manually invoke
  `/inbox-digest` against a real inbox with a small, known set of recent
  test emails (a genuine question, a newsletter, an automated
  notification with a date) and confirm: the newsletter gets no
  draft/event, the question gets a draft + is marked processed, the
  notification gets a calendar event but no draft, and re-running
  immediately produces zero new output (label exclusion works).
- **`add_calendar_event.py` (real code):** `scripts/test_add_calendar_event.py`
  mocks the Calendar API client (`unittest.mock`) and asserts
  `events().insert()` is called with the expected event body for both a
  timed and an all-day event — no real credentials or network calls
  needed to run it. Plus manual `--dry-run` sanity checks during setup.
