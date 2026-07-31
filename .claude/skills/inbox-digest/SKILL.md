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
