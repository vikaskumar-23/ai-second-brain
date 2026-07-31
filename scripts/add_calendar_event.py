"""Create a Google Calendar event for a suggested task from inbox-digest."""
import argparse
import json
import os
from datetime import datetime, timedelta

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow, WSGITimeoutError
from googleapiclient.discovery import build

SCOPES = ["https://www.googleapis.com/auth/calendar.events"]


def build_event_body(summary, description, date_str, all_day=False, timezone="Asia/Kolkata"):
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
    return {
        "summary": summary,
        "description": description,
        "start": {"dateTime": start_dt.isoformat(), "timeZone": timezone},
        "end": {"dateTime": end_dt.isoformat(), "timeZone": timezone},
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
            # ponytail: pinned to 127.0.0.1 with a 5-minute window, because the
            # default host="localhost" can resolve to IPv6 first on Windows,
            # which this loopback server never binds to — that mismatch
            # otherwise surfaces as a confusing NoneType crash instead of a
            # clean timeout. Raise the ceiling if 5 minutes is too short.
            try:
                creds = flow.run_local_server(
                    port=0, bind_addr="127.0.0.1", timeout_seconds=300
                )
            except WSGITimeoutError:
                raise SystemExit(
                    "Timed out waiting for Google sign-in (5 min limit). Make "
                    "sure the browser window opened to the printed URL, and "
                    "complete sign-in and consent there, then re-run this "
                    "command."
                )
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
        "--timezone",
        default="Asia/Kolkata",
        help="IANA timezone for --date when it includes a time (default: Asia/Kolkata, IIT Goa's timezone)",
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Print the event body, don't call the API"
    )
    parser.add_argument("--credentials", default="credentials.json")
    parser.add_argument("--token", default="token.json")
    args = parser.parse_args()

    body = build_event_body(args.summary, args.description, args.date, args.all_day, args.timezone)

    if args.dry_run:
        print(json.dumps(body, indent=2))
        return

    service = get_calendar_service(args.credentials, args.token)
    print(create_event(service, body))


if __name__ == "__main__":
    main()
