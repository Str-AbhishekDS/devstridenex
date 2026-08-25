# Copyright (c) 2026, QTPL and Contributors
# See license.txt

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import today, add_days, get_time

EXTRA_TEST_RECORD_DEPENDENCIES = []  # eg. ["User"]
IGNORE_TEST_RECORD_DEPENDENCIES = []  # eg. ["User"]


class IntegrationTestMentorBlockedTime(IntegrationTestCase):
    def setUp(self):
        super().setUp()
        self.mentor_email = "rahulg@gmail.com"
        self.student_email = "abc11@gmail.com"
        self.date = add_days(today(), 10)

        # Clean up any existing blocks or bookings on this specific date for the test mentor
        frappe.db.delete("Mentor Session Booking", {"mentor": self.mentor_email, "session_date": self.date})
        frappe.db.delete("Mentor Blocked Time", {"mentor": self.mentor_email, "date": self.date})

        self.offering = frappe.db.get_value("Mentor Offering", {"mentor": self.mentor_email}, "name")
        if not self.offering:
            offering_doc = frappe.get_doc({
                "doctype": "Mentor Offering",
                "mentor": self.mentor_email,
                "title": "1:1 Mentorship Session",
                "offering_type": "1:1 Mentorship",
                "price_per_session": 100,
                "status": "Active"
            })
            offering_doc.insert(ignore_permissions=True)
            self.offering = offering_doc.name

    def tearDown(self):
        # Delete Blocked Times, Bookings on this specific date
        frappe.db.delete("Mentor Session Booking", {"mentor": self.mentor_email, "session_date": self.date})
        frappe.db.delete("Mentor Blocked Time", {"mentor": self.mentor_email, "date": self.date})
        super().tearDown()

    def test_whole_day_block_clears_times(self):
        # Create a whole day block
        block = frappe.get_doc({
            "doctype": "Mentor Blocked Time",
            "mentor": self.mentor_email,
            "date": self.date,
            "whole_day": 1,
            "from_time": "10:00:00",
            "to_time": "12:00:00"
        })
        block.insert(ignore_permissions=True)
        
        self.assertIsNone(block.from_time)
        self.assertIsNone(block.to_time)

    def test_cannot_block_if_session_already_booked(self):
        # Create a session booking first
        booking = frappe.get_doc({
            "doctype": "Mentor Session Booking",
            "mentor": self.mentor_email,
            "student": self.student_email,
            "offering": self.offering,
            "session_date": self.date,
            "from_time": "10:00:00",
            "to_time": "11:00:00",
            "status": "Scheduled"
        })
        booking.insert(ignore_permissions=True)

        # Attempting to block whole day should fail
        block_whole = frappe.get_doc({
            "doctype": "Mentor Blocked Time",
            "mentor": self.mentor_email,
            "date": self.date,
            "whole_day": 1
        })
        with self.assertRaises(frappe.ValidationError) as context:
            block_whole.insert(ignore_permissions=True)
        
        self.assertIn("there is a session available so before block the time first reschdule the session and then block the time.", str(context.exception))

        # Attempting to block overlapping partial time should fail
        block_partial = frappe.get_doc({
            "doctype": "Mentor Blocked Time",
            "mentor": self.mentor_email,
            "date": self.date,
            "from_time": "09:30:00",
            "to_time": "10:30:00",
            "whole_day": 0
        })
        with self.assertRaises(frappe.ValidationError) as context_partial:
            block_partial.insert(ignore_permissions=True)
            
        self.assertIn("there is a session available so before block the time first reschdule the session and then block the time.", str(context_partial.exception))

    def test_cannot_book_session_if_whole_day_blocked(self):
        # Block the whole day
        block = frappe.get_doc({
            "doctype": "Mentor Blocked Time",
            "mentor": self.mentor_email,
            "date": self.date,
            "whole_day": 1
        })
        block.insert(ignore_permissions=True)

        # Attempt to book a session
        booking = frappe.get_doc({
            "doctype": "Mentor Session Booking",
            "mentor": self.mentor_email,
            "student": self.student_email,
            "offering": self.offering,
            "session_date": self.date,
            "from_time": "10:00:00",
            "to_time": "11:00:00",
            "status": "Scheduled"
        })
        with self.assertRaises(frappe.ValidationError):
            booking.insert(ignore_permissions=True)

    def test_get_slot_calendar_whole_day_blocked(self):
        from stridenex_app.stridenex_app.doctype.mentor_session_booking.mentor_session_booking import get_slot_calendar
        
        # Block the whole day
        block = frappe.get_doc({
            "doctype": "Mentor Blocked Time",
            "mentor": self.mentor_email,
            "date": self.date,
            "whole_day": 1,
            "reason": "Family Event"
        })
        block.insert(ignore_permissions=True)
        
        # Call get_slot_calendar after blocking the day
        cal_after = get_slot_calendar(mentor=self.mentor_email, from_date=self.date, to_date=self.date, offering=self.offering)
        
        # Check that all returned slots for self.date have status "blocked" and reason "Family Event"
        date_str = str(self.date)
        if date_str in cal_after:
            for slot in cal_after[date_str]:
                self.assertEqual(slot["status"], "blocked")
                self.assertEqual(slot["reason"], "Family Event")
