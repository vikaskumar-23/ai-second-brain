# Inbox Digest — Design Spec

**Date:** 2026-08-01
**Status:** Approved for implementation

## Summary

A small, resume-showcase project: a Claude Code **skill** (no backend, no new
dependencies) that turns Gmail inbox activity into three things a person
actually wants each day:

1. A plain-English **summary** of what came in.
2. **Proposed replies**, saved as real Gmail drafts for the user to edit and
   send — never auto-sent.
3. **Suggested tasks**, appended to a local markdown file.

It is explicitly *not* a hosted service, web app, or background daemon in its
first version. It runs on demand, inside a Claude Code session that has the
Gmail MCP connector configured, driven entirely by a skill prompt plus the
Gmail MCP tools already available in that environment (`search_threads`,
`get_thread`/`get_message`, `create_draft`, `label_thread`, `create_label`,
`list_labels`).

## Non-goals (v1)

- No custom Gmail OAuth/API client — the Gmail MCP connector already
  provides this; building a parallel integration would duplicate what's
  free.
- No standalone scheduler/daemon — scheduling is a documented *future*
  phase, layered on via the existing `schedule` skill (cron-based cloud
  agent invoking the same skill), not built now.
- No classifier/NLP code — "is this reply-worthy," "is this actionable" are
  judgment calls made inline by Claude as part of the skill prompt, not a
  separate scored model.
- No multi-account support, no non-Gmail providers.

## Architecture

```
ai-second-brain/
├── README.md                     # what it is, setup, how to run, example output
├── LICENSE                       # MIT
├── .claude/
│   └── skills/
│       └── inbox-digest/
│           └── SKILL.md          # the skill: instructions + tool-call sequence
├── examples/
│   └── sample-digest.md          # anonymized fake-data example run output
├── TASKS.md                      # real output — gitignored (private inbox content)
├── digests/                      # real output — gitignored (private inbox content)
└── .gitignore
```

Only the skill definition, README, LICENSE, and anonymized example are
tracked in git. `TASKS.md` and `digests/*.md` hold real email content once
the skill is run against a real inbox, so they are gitignored.

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
4. **Act on judgments:**
   - Reply-worthy → `create_draft` with proposed reply body. Never sent
     automatically.
   - Actionable → append a checkbox line to `TASKS.md`.
   - Always → append an entry to today's `digests/YYYY-MM-DD.md`.
5. **Mark processed.** `label_thread` with `SecondBrain/Processed` so the
   next run's search excludes it regardless of read/unread state.
6. **Report.** Short in-chat summary: N threads processed, M drafts created,
   K tasks added, and how many (if any) were left unprocessed due to the cap.

## Data formats

`TASKS.md` — one checkbox line per task:

```
- [ ] Review Q3 budget numbers before Friday (from: jane@co.com, "Q3 budget review")
```

`digests/2026-08-01.md`:

```
# Inbox Digest — 2026-08-01

## "Q3 budget review" — jane@co.com
Summary: Jane needs sign-off on Q3 numbers by Friday.
Reply drafted: Yes
Task added: Yes
```

## Error handling

- A single thread failing (e.g. `create_draft` error) does not stop the
  run — it's noted in the digest as "reply draft failed" and the run
  continues to the next thread.
- If `search_threads` itself fails (e.g. auth/connector issue), the skill
  reports the failure clearly rather than silently producing an empty
  digest.

## Scheduling (future phase, not built now)

Once proven on demand, wrap the same skill with the existing `schedule`
skill (cron-based cloud agent) to fire `/inbox-digest` on a recurring
schedule (e.g. daily). No architecture change — same skill, same tool
calls, just an automatic trigger instead of a manual one.

## Repo/showcase considerations

- Public GitHub repo, MIT license, README documents that running this
  requires the user's own Claude Code session with a Gmail MCP connector
  configured — this is not a hosted or installable end-user product.
- `examples/sample-digest.md` uses invented sender names/subjects so the
  repo demonstrates output shape without exposing any real inbox content.

## Testing / verification

Since this is a prompt-driven skill (no branching code to unit-test), the
verification is a runnable check rather than an automated test suite:
manually invoke `/inbox-digest` against a real inbox with a small, known
set of recent test emails (a mix of a genuine question, a newsletter, and
an automated notification) and confirm: the newsletter gets no draft/no
task, the question gets a draft + is marked processed, the notification
gets a task but no draft, and re-running immediately produces zero new
output (label exclusion works).
