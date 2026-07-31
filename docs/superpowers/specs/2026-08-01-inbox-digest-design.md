# Inbox Digest — Design Spec

**Date:** 2026-08-01 (rev. 4 — daily cloud routine for email-triage half)
**Status:** Implemented and running (see Scheduling section)

## Summary

A small, resume-showcase project: a Claude Code **skill** that turns Gmail
inbox activity into three things a person actually wants each day:

1. A plain-English **summary** of what came in.
2. **Proposed replies**, drafted in the user's own writing voice (learned
   from their sent mail — see rev. 3), saved as real Gmail drafts for the
   user to edit and send — never auto-sent.
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
- **A persisted voice profile** (`VOICE.md`), read by `/inbox-digest` when
  drafting replies, produced/refreshed by a second skill (`/learn-voice`).

**Rev. 2 change:** originally tasks were appended to a local `TASKS.md`.
That's now replaced entirely by Google Calendar events, per explicit
request, to (a) get real due-date/reminder behavior a static file can't
give, and (b) put an actual piece of programming-language code in the
repo for portfolio purposes.

**Rev. 3 change:** adds a "memory" of the user's own reply style, so
drafted replies sound like something the user would actually write, not a
generic assistant voice. This is the small-scope analog of the reference
project's `SOUL.md`/persistent-persona layer — one markdown file, no
vector DB, no cross-session agent memory beyond that file.

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
- No per-contact/relationship-specific voice variants (e.g. more formal to
  a manager, casual to a friend) — a single overall voice profile only.
- No automatic learning from edits made to sent drafts (comparing draft vs.
  sent to infer corrections) — voice profile only comes from analyzing
  existing sent mail, not from feedback loops on this tool's own drafts.
- No semantic/vector search over past digests, no multi-platform reach
  (Slack/Asana/Linear/GitHub), no auto-send tier, no habit-tracking
  nudges — all present in the larger reference project this is scoped
  down from, all declined here as solving problems this tool doesn't have.
- No `SessionStart` hook nudge, no sender allow/deny (VIP/ignore) list, no
  separate "Security & Permissions" README section — considered when
  comparing against the reference project, explicitly declined for this
  pass in favor of priority flagging only.

## Architecture

```
ai-second-brain/
├── README.md                       # what it is, setup (incl. Google Cloud/OAuth steps), how to run
├── LICENSE                         # MIT
├── requirements.txt                # google-auth, google-auth-oauthlib, google-api-python-client
├── .claude/
│   └── skills/
│       ├── inbox-digest/
│       │   └── SKILL.md            # the skill: instructions + tool-call sequence
│       └── learn-voice/
│           └── SKILL.md            # analyzes sent mail -> VOICE.md
├── scripts/
│   ├── add_calendar_event.py       # real code: OAuth + Calendar API event creation
│   └── test_add_calendar_event.py  # unit test with a mocked Calendar API client
├── examples/
│   ├── sample-digest.md            # anonymized fake-data example run output
│   └── sample-voice.md             # anonymized example of a generated voice profile
├── digests/                        # real output — gitignored (private inbox content)
├── VOICE.md                        # real output — gitignored (derived from private sent mail)
├── credentials.json                # user's OAuth client secret — gitignored, never committed
├── token.json                      # OAuth refresh token, created on first run — gitignored
└── .gitignore
```

Only the skills, script, tests, README, LICENSE, `requirements.txt`, and
anonymized examples are tracked in git. `digests/*.md`, `VOICE.md`,
`credentials.json`, and `token.json` are gitignored — the first two hold
private email content, the last two are secrets.

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
   - **Priority** — Urgent / Normal / Low, the same inline judgment call
     as the others (sender urgency cues, explicit deadlines, direct asks
     from a person vs. automated/bulk mail). No separate scoring system.
4. **Act on judgments:**
   - Reply-worthy → read `VOICE.md` if it exists (both its auto-learned
     and manual-overrides sections — see `/learn-voice` below; overrides
     win on conflict) and draft the reply body to match that voice, then
     `create_draft`. Never sent automatically. If `VOICE.md` doesn't
     exist yet, draft in a neutral professional tone and note in the
     digest "no voice profile found — run /learn-voice to personalize."
   - Actionable → shell out to
     `python scripts/add_calendar_event.py --summary "..." --description "..." --date "..."`
     to create a Google Calendar event; capture the returned event link.
   - Always → append an entry to today's `digests/YYYY-MM-DD.md`.
5. **Mark processed.** `label_thread` with `SecondBrain/Processed` so the
   next run's search excludes it regardless of read/unread state.
6. **Report.** Short in-chat summary: N threads processed, M drafts created,
   K calendar events created, J flagged Urgent, and how many (if any) were
   left unprocessed due to the cap.

## Skill behavior (`/learn-voice`)

Invoked manually as `/learn-voice`, optionally with a sample-size override
(default 30 sent messages). Steps:

1. **Preserve existing manual notes.** If `VOICE.md` already exists, read
   it and keep its "Manual overrides" section verbatim — only the
   "Auto-learned patterns" section gets regenerated.
2. **Sample sent mail.** `search_threads` with query `in:sent`, most
   recent N (default 30). `get_message` for each. If fewer than ~10 sent
   messages exist, still proceed but note in the output that the profile
   is low-confidence given the small sample.
3. **Synthesize a profile** (Claude reasoning inline, no separate
   NLP/style-scoring code): typical greeting, typical sign-off, formality
   level, typical reply length, recurring phrases/quirks, tone
   description. This is a judgment call, same as the reply/actionable
   calls in `/inbox-digest` — not a scored model.
4. **Write `VOICE.md`**, replacing only the auto-learned section:

   ```
   # My Email Voice

   ## Auto-learned patterns (regenerated by /learn-voice — do not hand-edit this section)
   - Tone: ...
   - Typical greeting: ...
   - Typical sign-off: ...
   - Length/style: ...
   - Recurring phrases: ...

   ## Manual overrides (preserved across /learn-voice runs — edit freely)
   (empty until the user adds notes here)
   ```
5. **Report.** How many sent messages were sampled and a one-line summary
   of the inferred tone, so the user can sanity-check it against
   `VOICE.md` directly.

`VOICE.md` is derived from real private correspondence, so it's gitignored
like `digests/`, never committed. `examples/sample-voice.md` (an
invented, anonymized profile) ships instead, to show the shape without
exposing real writing.

## `scripts/add_calendar_event.py`

A single-purpose CLI script, not a library or service:

- **Auth**: standard Google OAuth "installed app" flow
  (`google-auth-oauthlib.flow.InstalledAppFlow`) — reads `credentials.json`
  (the OAuth client the user creates in Google Cloud Console), opens a
  browser for one-time consent, caches the resulting refresh token in
  `token.json`. Subsequent runs reuse the cached token silently.
- **Args**: `--summary`, `--description`, `--date` (ISO date, or
  date+time), `--all-day` (flag; used when no explicit time was found),
  `--timezone` (IANA name, default `Asia/Kolkata`).
- **Action**: builds an event body and calls
  `service.events().insert(calendarId='primary', body=...)`.
- **Timezone (rev. 5 fix)**: originally hardcoded `timeZone: "UTC"` on
  every timed event regardless of what timezone the source email's time
  actually meant. Since inbox-digest resolves times straight from email
  text (which for this user is IIT Goa, i.e. Asia/Kolkata local time),
  this silently shifted every timed event by 5.5 hours (a 2pm meeting
  landed on the calendar at 7:30pm). Fixed by defaulting `--timezone` to
  `Asia/Kolkata` and passing it through; the skill should pass `UTC`
  explicitly only when the source email itself states a UTC time (e.g.
  Codeforces contest announcements).
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
Priority: Urgent
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

## Scheduling (rev. 4 — partially built)

`/inbox-digest` is now wrapped in a daily cloud routine via Claude Code's
`schedule` skill ("Daily Inbox Digest", `30 2 * * *` UTC = 8am IST). Same
skill, same tool calls, no new architecture — just an automatic trigger.

Cloud routines get a fresh git checkout per run with no access to the
local machine, which surfaced two real consequences discovered only once
this was actually wired up:
- **Calendar events don't fire from cloud runs.** `credentials.json` and
  `token.json` are local-only (correctly gitignored), so they don't exist
  in the cloud checkout. `/inbox-digest`'s step 3 `token.json` check (see
  Skill behavior above) makes this a graceful no-op rather than a crash,
  but it means the cloud routine only ever delivers the email-triage half
  (summaries, reply drafts, labeling) — calendar events for actionable
  items still require a local run.
- **`VOICE.md` can't follow along either**, same reason — cloud-drafted
  replies are always neutral-tone.
- `digests/*.md` also can't persist between cloud runs (gitignored), so
  `/inbox-digest` step 6 now reports the full per-thread content in the
  chat response itself, not just aggregate counts — the routine's run
  history on claude.ai/code/routines is the durable record for cloud
  runs, since the file can't be.

`/learn-voice` is deliberately **not** cloud-scheduled, for the same
fresh-checkout reason: a cloud-generated `VOICE.md` would evaporate with
the ephemeral session and never reach any future run, local or cloud. It
only makes sense run locally, where it actually persists on disk.

Getting calendar events and voice personalization automated too (not
just email triage) would require local scheduling (e.g. Windows Task
Scheduler) instead of a cloud routine, since that needs access to local
secrets that shouldn't leave the machine. Not built — considered
out of scope for now; a fully unattended, permission-bypassed local
script also has a real oversight cost (nobody watching before it drafts
emails or creates events) that's worth weighing deliberately rather than
defaulting into.

## Repo/showcase considerations

- Public GitHub repo, MIT license. README documents two prerequisites
  clearly: (1) a Claude Code session with the Gmail MCP connector
  configured, and (2) a Google Cloud project with the Calendar API
  enabled and an OAuth client (`credentials.json`) the user creates
  themselves — this is not a hosted or installable end-user product, and
  no secrets ship in the repo.
- `examples/sample-digest.md` and `examples/sample-voice.md` use invented
  names/subjects/writing so the repo demonstrates output shape without
  exposing any real inbox content or real writing style.

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
- **`/learn-voice` (prompt-driven):** run it once against a real Sent
  folder, confirm `VOICE.md` is created with all expected subsections
  populated; hand-add a note under Manual overrides, re-run `/learn-voice`,
  and confirm the manual note survives while the auto-learned section
  updates.
