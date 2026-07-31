# Inbox Digest Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a public, resume-showcase GitHub repo containing two Claude Code skills (`/inbox-digest`, `/learn-voice`) and one real Python script (`scripts/add_calendar_event.py`), matching `docs/superpowers/specs/2026-08-01-inbox-digest-design.md`.

**Architecture:** Two prompt-driven Claude Code skills orchestrate existing Gmail MCP tools (search/read/draft/label) with zero custom code on the Gmail side. The one piece of real standalone code is a Python CLI script that creates Google Calendar events via OAuth2, since no Calendar MCP tool exists. A persisted `VOICE.md` (gitignored, user-specific) lets `/inbox-digest` draft replies in the user's own style.

**Tech Stack:** Claude Code skills (Markdown + YAML frontmatter), Python 3.9+, `google-auth`/`google-auth-oauthlib`/`google-api-python-client`, stdlib `unittest` for tests, git, GitHub (MCP `github` tools).

## Global Constraints

- Repo root: `C:\Users\vishu\OneDrive\Desktop\Projects\ai-second-brain` — already a local git repo with 4 commits (design spec + revisions). Do not re-init.
- License: MIT, copyright holder "Vikas Kumar", year 2026.
- GitHub target: owner `vikaskumar-23`, repo name `ai-second-brain`, **public** visibility.
- Dependencies limited to exactly: `google-auth`, `google-auth-oauthlib`, `google-api-python-client` (runtime) — no `pytest`, tests use stdlib `unittest` only.
- Never commit: `digests/*.md`, `VOICE.md`, `credentials.json`, `token.json` — all must be in `.gitignore` before any of them can be created.
- Gmail MCP tools to reference by exact name: `mcp__claude_ai_Gmail__search_threads`, `mcp__claude_ai_Gmail__get_thread`, `mcp__claude_ai_Gmail__get_message`, `mcp__claude_ai_Gmail__create_draft`, `mcp__claude_ai_Gmail__label_thread`, `mcp__claude_ai_Gmail__create_label`, `mcp__claude_ai_Gmail__list_labels`.
- Processed-marker label name, exactly: `SecondBrain/Processed`.
- `/inbox-digest` thread cap per run: 50. Default lookback: 24 hours.
- `/learn-voice` default sample size: 30 sent messages.
- Gmail's `newer_than` search operator only supports day/month/year granularity, not hours — any hour-based lookback must be converted to days (`ceil(hours / 24)`, minimum 1) before being used in a search query.

---

### Task 1: Project scaffolding

**Files:**
- Create: `.gitignore`
- Create: `requirements.txt`
- Create: `LICENSE`

**Interfaces:**
- Consumes: nothing (first task).
- Produces: a `.gitignore` that later tasks rely on to keep `digests/`, `VOICE.md`, `credentials.json`, `token.json` out of git; `requirements.txt` that Task 2 installs from.

- [ ] **Step 1: Create `.gitignore`**

```
digests/
VOICE.md
credentials.json
token.json
__pycache__/
*.pyc
.venv/
venv/
```

- [ ] **Step 2: Create `requirements.txt`**

```
google-auth>=2.23.0
google-auth-oauthlib>=1.1.0
google-api-python-client>=2.100.0
```

- [ ] **Step 3: Create `LICENSE`** (MIT)

```
MIT License

Copyright (c) 2026 Vikas Kumar

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

- [ ] **Step 4: Verify**

Run: `git status`
Expected: three new untracked files listed (`.gitignore`, `requirements.txt`, `LICENSE`), nothing from a gitignored path shows up.

- [ ] **Step 5: Commit**

```bash
git add .gitignore requirements.txt LICENSE
git commit -m "Add project scaffolding: gitignore, requirements, MIT license"
```

---

### Task 2: Calendar event script (TDD)

**Files:**
- Create: `scripts/add_calendar_event.py`
- Create: `scripts/test_add_calendar_event.py`
- Test: `scripts/test_add_calendar_event.py`

**Interfaces:**
- Consumes: `requirements.txt` from Task 1 (must `pip install -r requirements.txt` first).
- Produces (for Task 3 to shell out to):
  - CLI: `python scripts/add_calendar_event.py --summary "<str>" --description "<str>" --date "<ISO date or date+time>" [--all-day] [--dry-run] [--credentials <path>] [--token <path>]`
  - On success (non-dry-run): prints the created event's `htmlLink` as the only stdout line.
  - On `--dry-run`: prints the JSON event body, makes no network call.
  - Functions: `build_event_body(summary, description, date_str, all_day=False) -> dict`, `create_event(service, body) -> str`, `get_calendar_service(credentials_path="credentials.json", token_path="token.json")`.

- [ ] **Step 1: Install dependencies**

Run: `pip install -r requirements.txt`
Expected: installs without error (installs `google-auth`, `google-auth-oauthlib`, `google-api-python-client` and their transitive deps).

- [ ] **Step 2: Write the failing tests**

Create `scripts/test_add_calendar_event.py`:

```python
import unittest
from unittest.mock import MagicMock

from add_calendar_event import build_event_body, create_event


class TestBuildEventBody(unittest.TestCase):
    def test_timed_event(self):
        body = build_event_body(
            summary="Review Q3 numbers",
            description="From: jane@co.com — Q3 budget review",
            date_str="2026-08-05T15:00:00",
            all_day=False,
        )
        self.assertEqual(body["summary"], "Review Q3 numbers")
        self.assertEqual(body["description"], "From: jane@co.com — Q3 budget review")
        self.assertEqual(
            body["start"], {"dateTime": "2026-08-05T15:00:00", "timeZone": "UTC"}
        )
        self.assertEqual(
            body["end"], {"dateTime": "2026-08-05T15:30:00", "timeZone": "UTC"}
        )

    def test_all_day_event(self):
        body = build_event_body(
            summary="Invoice due",
            description="From: billing@vendor.com",
            date_str="2026-08-07",
            all_day=True,
        )
        self.assertEqual(body["start"], {"date": "2026-08-07"})
        self.assertEqual(body["end"], {"date": "2026-08-08"})


class TestCreateEvent(unittest.TestCase):
    def test_create_event_calls_insert_with_body(self):
        mock_service = MagicMock()
        mock_service.events.return_value.insert.return_value.execute.return_value = {
            "htmlLink": "https://calendar.google.com/event?eid=abc123"
        }
        body = {"summary": "Test event"}

        link = create_event(mock_service, body)

        mock_service.events.return_value.insert.assert_called_once_with(
            calendarId="primary", body=body
        )
        self.assertEqual(link, "https://calendar.google.com/event?eid=abc123")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 3: Run tests to verify they fail**

Run (from inside `scripts/`): `python -m unittest test_add_calendar_event -v`
Expected: `ModuleNotFoundError: No module named 'add_calendar_event'` (the module doesn't exist yet).

- [ ] **Step 4: Write the implementation**

Create `scripts/add_calendar_event.py`:

```python
"""Create a Google Calendar event for a suggested task from inbox-digest."""
import argparse
import json
import os
from datetime import datetime, timedelta

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = ["https://www.googleapis.com/auth/calendar.events"]


def build_event_body(summary, description, date_str, all_day=False):
    if all_day:
        start_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        end_date = start_date + timedelta(days=1)
        return {
            "summary": summary,
            "description": description,
            "start": {"date": start_date.isoformat()},
            "end": {"date": end_date.isoformat()},
        }

    start_dt = datetime.fromisoformat(date_str)
    end_dt = start_dt + timedelta(minutes=30)
    # ponytail: timezone fixed to UTC, add a --timezone flag (or tzlocal) if
    # events show up at the wrong local time.
    return {
        "summary": summary,
        "description": description,
        "start": {"dateTime": start_dt.isoformat(), "timeZone": "UTC"},
        "end": {"dateTime": end_dt.isoformat(), "timeZone": "UTC"},
    }


def get_calendar_service(credentials_path="credentials.json", token_path="token.json"):
    creds = None
    if os.path.exists(token_path):
        creds = Credentials.from_authorized_user_file(token_path, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(credentials_path, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(token_path, "w") as f:
            f.write(creds.to_json())
    return build("calendar", "v3", credentials=creds)


def create_event(service, body):
    event = service.events().insert(calendarId="primary", body=body).execute()
    return event["htmlLink"]


def main():
    parser = argparse.ArgumentParser(
        description="Create a Google Calendar event for a suggested task."
    )
    parser.add_argument("--summary", required=True)
    parser.add_argument("--description", default="")
    parser.add_argument(
        "--date",
        required=True,
        help="ISO date (YYYY-MM-DD) for --all-day, or date+time (YYYY-MM-DDTHH:MM:SS) otherwise",
    )
    parser.add_argument("--all-day", action="store_true")
    parser.add_argument(
        "--dry-run", action="store_true", help="Print the event body, don't call the API"
    )
    parser.add_argument("--credentials", default="credentials.json")
    parser.add_argument("--token", default="token.json")
    args = parser.parse_args()

    body = build_event_body(args.summary, args.description, args.date, args.all_day)

    if args.dry_run:
        print(json.dumps(body, indent=2))
        return

    service = get_calendar_service(args.credentials, args.token)
    print(create_event(service, body))


if __name__ == "__main__":
    main()
```

- [ ] **Step 5: Run tests to verify they pass**

Run (from inside `scripts/`): `python -m unittest test_add_calendar_event -v`
Expected: `OK` (3 tests pass).

- [ ] **Step 6: Manual dry-run sanity check**

Run (from repo root): `python scripts/add_calendar_event.py --summary "Test task" --description "Sanity check" --date "2026-08-10T09:00:00" --dry-run`
Expected: pretty-printed JSON event body on stdout, no browser opens, no network call.

- [ ] **Step 7: Commit**

```bash
git add scripts/add_calendar_event.py scripts/test_add_calendar_event.py
git commit -m "Add Google Calendar event script with mocked unit tests"
```

---

### Task 3: `/inbox-digest` skill

**Files:**
- Create: `.claude/skills/inbox-digest/SKILL.md`

**Interfaces:**
- Consumes: the CLI from Task 2 (`python scripts/add_calendar_event.py --summary ... --description ... --date ... [--all-day]`); reads `VOICE.md` at repo root if present (format defined in Task 4).
- Produces: the `/inbox-digest [hours]` command, and `digests/YYYY-MM-DD.md` files at runtime (gitignored, not created by this task itself).

- [ ] **Step 1: Create the skill file**

Create `.claude/skills/inbox-digest/SKILL.md`:

```markdown
---
name: inbox-digest
description: Summarize recent Gmail inbox threads, draft replies in the user's own voice, and create Google Calendar events for actionable items. Optional argument: lookback window in hours (default 24).
---

# Inbox Digest

Summarizes recent Gmail inbox activity, drafts replies for anything that
needs one (in the user's own voice, if `VOICE.md` exists), and creates a
Google Calendar event for anything actionable. Never sends email
automatically.

## Argument

An optional lookback window in hours, e.g. `/inbox-digest 48`. Default: 24.
Parse this as `LOOKBACK_HOURS`.

Gmail's `newer_than` search operator only supports day/month/year
granularity, not hours. Convert: `LOOKBACK_DAYS = ceil(LOOKBACK_HOURS / 24)`,
minimum 1.

## Steps

1. **Ensure the processed-marker label exists.**
   Call `mcp__claude_ai_Gmail__list_labels`. If no label named
   `SecondBrain/Processed` exists, create it with
   `mcp__claude_ai_Gmail__create_label` (`displayName: "SecondBrain/Processed"`).

2. **Fetch candidate threads.**
   Call `mcp__claude_ai_Gmail__search_threads` with query:
   `newer_than:{LOOKBACK_DAYS}d -label:SecondBrain/Processed in:inbox`
   Take at most the 50 most recent threads returned. If more than 50
   matched, remember the overflow count for the final report.

3. **For each thread (oldest first):**

   a. Fetch full content with `mcp__claude_ai_Gmail__get_thread` (or
      `mcp__claude_ai_Gmail__get_message` for single-message threads).

   b. Judge, reasoning inline (no separate scoring code):
      - **Summary**: 1-3 sentence gist.
      - **Reply-worthy**: true if it's a direct question, request, or
        action aimed at the user; false for newsletters, automated
        notifications, or FYI/CC-only threads.
      - **Actionable**: true if it implies any task for the user
        (deadline, request, follow-up) — independent of reply-worthy;
        e.g. an automated "invoice due Friday" notice is actionable but
        not reply-worthy.
      - **Due date** (only if actionable): resolve any explicit or
        relative date mentioned (e.g. "by Friday") against today's date.
        If no date is mentioned, default to the next business day and
        note that it was defaulted.
      - **Priority**: Urgent / Normal / Low, based on sender urgency
        cues, explicit deadlines, and whether it's a direct ask from a
        person vs. automated/bulk mail.

   c. If reply-worthy:
      - Read `VOICE.md` from the repo root if it exists (both its
        "Auto-learned patterns" and "Manual overrides" sections; manual
        overrides win on conflict). Draft the reply body to match that
        voice. If `VOICE.md` doesn't exist, draft in a neutral
        professional tone and note "no voice profile found — run
        /learn-voice to personalize" for this thread in the digest.
      - Call `mcp__claude_ai_Gmail__create_draft` with `replyToMessageId`
        set to the relevant message ID, and the drafted body. Never send.
      - If this call fails, record "reply draft failed" for this thread
        and continue to the next thread — don't stop the run.

   d. If actionable:
      - Run:
        `python scripts/add_calendar_event.py --summary "<short task title>" --description "<1-2 sentence context: thread subject + sender>" --date "<resolved ISO date or date+time>"`
        (add `--all-day` if no specific time was found in the email).
      - Capture the printed event link (the script's stdout) for the digest.
      - If the script fails (non-zero exit), record "calendar event
        failed" for this thread. If the failure output mentions a
        missing `credentials.json` or an incomplete OAuth flow, surface
        that specific cause instead of a generic error. Continue to the
        next thread.

   e. Append an entry to `digests/YYYY-MM-DD.md` (today's date, create
      the file with a top-level `# Inbox Digest — YYYY-MM-DD` heading if
      it doesn't exist yet):

      ```
      ## "<thread subject>" — <sender email>
      Priority: <Urgent|Normal|Low>
      Summary: <summary>
      Reply drafted: <Yes|No — reason if failed or skipped>
      Calendar event: <Yes — <link>|No — reason if failed or skipped>
      ```

4. **Mark each processed thread** with `mcp__claude_ai_Gmail__label_thread`
   (label: `SecondBrain/Processed`), regardless of read/unread state —
   including threads where a sub-step (3c or 3d) failed, so failures
   don't get silently retried forever. If the failure was in
   `search_threads` itself (step 2, not per-thread), do NOT label
   anything and instead report the search failure directly to the user.

5. **Report** back in chat: number of threads processed, drafts created,
   calendar events created, threads flagged Urgent, and (if any) how many
   candidate threads were left unprocessed beyond the 50-thread cap
   (suggest re-running with a narrower lookback window if so).
```

- [ ] **Step 2: Verify the file is well-formed**

Run: `python -c "import re; content = open('.claude/skills/inbox-digest/SKILL.md').read(); assert content.startswith('---'); assert 'name: inbox-digest' in content"`
Expected: no output (assertions pass, exit code 0).

- [ ] **Step 3: Commit**

```bash
git add .claude/skills/inbox-digest/SKILL.md
git commit -m "Add inbox-digest skill"
```

---

### Task 4: `/learn-voice` skill

**Files:**
- Create: `.claude/skills/learn-voice/SKILL.md`

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces: the `/learn-voice [sample_size]` command and the `VOICE.md` format Task 3 reads (two sections: "Auto-learned patterns", "Manual overrides").

- [ ] **Step 1: Create the skill file**

Create `.claude/skills/learn-voice/SKILL.md`:

```markdown
---
name: learn-voice
description: Analyze a sample of the user's sent Gmail messages and write/refresh VOICE.md, a style profile inbox-digest uses to draft replies in the user's own voice. Optional argument: sample size (default 30).
---

# Learn Voice

Builds or refreshes `VOICE.md`, a profile of how the user writes email, by
sampling their own Sent mail. `/inbox-digest` reads this file when
drafting replies.

## Argument

An optional sample size, e.g. `/learn-voice 50`. Default: 30.
Parse this as `SAMPLE_SIZE`.

## Steps

1. **Preserve manual notes.** If `VOICE.md` already exists at the repo
   root, read it and keep its "Manual overrides" section's content
   verbatim for step 4 — only the "Auto-learned patterns" section gets
   regenerated.

2. **Sample sent mail.** Call `mcp__claude_ai_Gmail__search_threads` with
   query `in:sent`, and take the most recent `SAMPLE_SIZE` messages. Call
   `mcp__claude_ai_Gmail__get_message` for each. If fewer than 10 sent
   messages exist in total, proceed anyway but note the low sample size
   in the final report.

3. **Synthesize a profile**, reasoning inline over the sampled messages
   (no separate NLP/style-scoring code):
   - Typical greeting (e.g. "Hi <name>," vs "Hey," vs none)
   - Typical sign-off (e.g. "Best," "Thanks," a name, none)
   - Formality level (casual / neutral / formal)
   - Typical reply length (short/1-2 sentences, medium paragraph, long)
   - Recurring phrases or quirks worth preserving
   - One-paragraph overall tone description

4. **Write `VOICE.md`** at the repo root, replacing only the
   auto-learned section (preserving the manual-overrides content from
   step 1 verbatim, or using the empty placeholder below if the file
   didn't exist before):

   ```
   # My Email Voice

   ## Auto-learned patterns (regenerated by /learn-voice — do not hand-edit this section)
   - Tone: <one-paragraph description>
   - Typical greeting: <...>
   - Typical sign-off: <...>
   - Length/style: <...>
   - Recurring phrases: <...>

   ## Manual overrides (preserved across /learn-voice runs — edit freely)
   <preserved content from step 1, or "(empty until the user adds notes here)" if new>
   ```

5. **Report** back in chat: how many sent messages were sampled, and a
   one-line summary of the inferred tone, so the user can sanity-check it
   against `VOICE.md` directly.
```

- [ ] **Step 2: Verify the file is well-formed**

Run: `python -c "content = open('.claude/skills/learn-voice/SKILL.md').read(); assert content.startswith('---'); assert 'name: learn-voice' in content"`
Expected: no output (assertions pass, exit code 0).

- [ ] **Step 3: Commit**

```bash
git add .claude/skills/learn-voice/SKILL.md
git commit -m "Add learn-voice skill"
```

---

### Task 5: Anonymized example outputs

**Files:**
- Create: `examples/sample-digest.md`
- Create: `examples/sample-voice.md`

**Interfaces:**
- Consumes: the digest format from Task 3 and the `VOICE.md` format from Task 4 (must match exactly, with invented data).
- Produces: reference files the README (Task 6) links to.

- [ ] **Step 1: Create `examples/sample-digest.md`**

```markdown
# Inbox Digest — 2026-07-15

## "Q3 budget sign-off" — jane.doe@examplecorp.com
Priority: Urgent
Summary: Jane needs sign-off on the Q3 budget numbers before Friday's finance review.
Reply drafted: Yes
Calendar event: Yes — https://calendar.google.com/event?eid=example1

## "You're invited: TechConf 2026 early bird tickets" — newsletter@techconf.example
Priority: Low
Summary: Marketing newsletter announcing early-bird ticket pricing. No action needed.
Reply drafted: No
Calendar event: No

## "Invoice #4821 due Friday" — billing@vendorexample.com
Priority: Normal
Summary: Automated notice that invoice #4821 ($1,240) is due Friday. No response requested.
Reply drafted: No
Calendar event: Yes — https://calendar.google.com/event?eid=example2

## "Quick question about the API rate limits" — sam.lee@partnerexample.com
Priority: Normal
Summary: Sam is asking whether the new rate limits apply to the sandbox environment too.
Reply drafted: Yes
Calendar event: No
```

- [ ] **Step 2: Create `examples/sample-voice.md`**

```markdown
# My Email Voice

## Auto-learned patterns (regenerated by /learn-voice — do not hand-edit this section)
- Tone: Friendly but efficient — gets to the point in the first sentence, avoids filler, uses contractions.
- Typical greeting: "Hi <first name>," (rarely "Hey," for close colleagues)
- Typical sign-off: "Thanks,\n<first name>"
- Length/style: Short — usually 2-4 sentences, one idea per paragraph.
- Recurring phrases: "Sounds good", "Let me know if that works", "Happy to hop on a call if easier"

## Manual overrides (preserved across /learn-voice runs — edit freely)
- Always sign off with my full name when writing to anyone outside the company.
```

- [ ] **Step 3: Verify**

Run: `git status`
Expected: `examples/sample-digest.md` and `examples/sample-voice.md` listed as untracked.

- [ ] **Step 4: Commit**

```bash
git add examples/sample-digest.md examples/sample-voice.md
git commit -m "Add anonymized example digest and voice profile"
```

---

### Task 6: README

**Files:**
- Create: `README.md`

**Interfaces:**
- Consumes: everything from Tasks 1-5 (describes and links to it).
- Produces: the repo's front page for anyone (including resume reviewers) landing on it.

- [ ] **Step 1: Create `README.md`**

```markdown
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
```

- [ ] **Step 2: Verify**

Run: `python -c "content = open('README.md').read(); assert '/inbox-digest' in content and '/learn-voice' in content and 'credentials.json' in content"`
Expected: no output (assertions pass, exit code 0).

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "Add README with setup, usage, and prerequisites"
```

---

### Task 7: Push to GitHub

**Files:** none (repo operation only).

**Interfaces:**
- Consumes: all prior commits in the local repo.
- Produces: the public GitHub repo `vikaskumar-23/ai-second-brain`.

- [ ] **Step 1: Confirm no secrets are staged for push**

Run: `git status && git log --stat --oneline -10`
Expected: no `credentials.json`, `token.json`, `digests/*.md`, or `VOICE.md` appear in any commit's file list. If any do, stop and remove them from history before continuing (do not push).

- [ ] **Step 2: Rename local branch to `main`**

```bash
git branch -M main
```

- [ ] **Step 3: Create the GitHub repository**

Use the `mcp__plugin_github_github__create_repository` tool:
- `name`: `ai-second-brain`
- `description`: `Claude Code skill that summarizes Gmail, drafts replies in your voice, and creates Calendar events for actionable emails.`
- `private`: `false`
- (omit `autoInit` / leave false — the repo already has local commits to push)

- [ ] **Step 4: Add the remote and push**

```bash
git remote add origin https://github.com/vikaskumar-23/ai-second-brain.git
git push -u origin main
```

- [ ] **Step 5: Verify**

Use `mcp__plugin_github_github__get_file_contents` (owner: `vikaskumar-23`, repo: `ai-second-brain`, path: `README.md`) or visit the repo to confirm files are present and `digests/`, `VOICE.md`, `credentials.json`, `token.json` are absent from the pushed tree.

Report the final repo URL to the user: `https://github.com/vikaskumar-23/ai-second-brain`

---

## Post-implementation manual verification (not a subagent task)

Tasks 1-7 produce working, committed, pushed code, but two checks from the
spec's "Testing / verification" section require a **real Gmail inbox and a
completed Google Cloud OAuth setup** — neither is available to an isolated
subagent, and the Calendar half specifically can't happen until the user
has finished the Prerequisites steps in `README.md` (creating
`credentials.json` themselves). These should be run in a live session
that already has the Gmail MCP connector (this one qualifies), with the
user present, since they exercise real drafts/labels/calendar events:

1. **`/inbox-digest` live check**: run it against the real inbox. Confirm:
   a newsletter/notification-only thread gets no draft and no event; a
   thread with a direct question gets a Gmail draft and is labeled
   `SecondBrain/Processed`; a thread implying a deadline gets a Calendar
   event but no draft where appropriate; running `/inbox-digest`
   immediately again produces zero new output (the label exclusion in
   the search query works).
2. **`/learn-voice` live check**: run it once, confirm `VOICE.md` is
   created with all expected subsections populated from real Sent mail.
   Hand-add a line under "Manual overrides", re-run `/learn-voice`, and
   confirm that line survives while "Auto-learned patterns" updates.

Do not run step 1's calendar-event path until `credentials.json` exists
(see README Prerequisites) — without it, `add_calendar_event.py` will
fail with a clear "credentials.json not found" error, which is expected
and fine to see once, but isn't the actual success check.
