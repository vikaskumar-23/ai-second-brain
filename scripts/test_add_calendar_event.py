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
