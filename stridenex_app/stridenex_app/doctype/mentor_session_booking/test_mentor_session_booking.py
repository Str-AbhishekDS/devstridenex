# Copyright (c) 2026, QTPL and Contributors
# See license.txt

"""
Integration tests for reschedule_session().

Strategy:
  - Reuse existing Mentor (rahulg@gmail.com) and Student (abc11@gmail.com)
    records — avoids mandatory link-field issues when creating new ones.
  - Create temporary Mentor Offerings, Mentor Session Bookings, and
    Mentor Blocked Time records per test and clean up in tearDown.
  - All tests run as Administrator (System Manager).
  - The mentor rahulg@gmail.com is available Mon–Wed, 10:00–15:00, so all
    reschedule target times are chosen within that window.  The "original"
    booking is inserted directly via SQL so the validate() hook (which checks
    availability) is bypassed for setup purposes.
"""

import datetime
import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import add_days, nowdate, getdate

# On IntegrationTestCase, the doctype test records and all
# link-field test record dependencies are recursively loaded
EXTRA_TEST_RECORD_DEPENDENCIES = []
IGNORE_TEST_RECORD_DEPENDENCIES = []


# ---------------------------------------------------------------------------
# Constants — pick existing records from the database
# ---------------------------------------------------------------------------
MENTOR_NAME  = "rahulg@gmail.com"   # existing Mentor; available Mon–Wed 10:00–15:00
MENTOR_NAME2 = "ss@gmail.com"       # second existing mentor (for conflict tests)
STUDENT_NAME = "abc11@gmail.com"    # existing Student with email_id set


# ---------------------------------------------------------------------------
# Shared helper utilities
# ---------------------------------------------------------------------------

def _next_weekday(weekday: int, from_date=None) -> str:
    """
    Return the date string (YYYY-MM-DD) of the next occurrence of `weekday`
    (0=Monday … 6=Sunday) that is strictly AFTER from_date (default: today).
    """
    base = getdate(from_date or nowdate())
    days_ahead = weekday - base.weekday()
    if days_ahead <= 0:
        days_ahead += 7
    return str(base + datetime.timedelta(days=days_ahead))


def _make_offering(mentor=MENTOR_NAME, offering_type="1:1 Mentorship"):
    """Create a test Mentor Offering; returns its name."""
    doc = frappe.get_doc({
        "doctype": "Mentor Offering",
        "mentor": mentor,
        "title": f"_TEST_ {offering_type} Offering",
        "offering_type": offering_type,
        "price_per_session": 1,   # must be > 0 (validate_pricing)
        "status": "Live",
    })
    doc.insert(ignore_permissions=True)
    frappe.db.commit()
    return doc.name


def _make_booking(mentor, student, offering,
                  session_date, from_time, to_time,
                  topic="_test_topic_"):
    """
    Insert a Mentor Session Booking directly via raw SQL to completely bypass
    MentorSessionBooking.validate() — which enforces mentor availability and
    would reject bookings outside the real availability window.
    Returns the booking name.
    """
    from frappe.model.naming import make_autoname
    name = make_autoname("MSB-.YYYY.-.#####")
    frappe.db.sql("""
        INSERT INTO `tabMentor Session Booking`
            (name, mentor, student, offering, session_date, from_time, to_time,
             topic, status, mentor_request_status, offering_type,
             creation, modified, modified_by, owner, docstatus)
        VALUES
            (%(name)s, %(mentor)s, %(student)s, %(offering)s, %(session_date)s,
             %(from_time)s, %(to_time)s, %(topic)s, %(status)s,
             %(mentor_request_status)s, %(offering_type)s,
             NOW(), NOW(), 'Administrator', 'Administrator', 0)
    """, {
        "name": name,
        "mentor": mentor,
        "student": student,
        "offering": offering,
        "session_date": session_date,
        "from_time": from_time,
        "to_time": to_time,
        "topic": topic,
        "status": "Scheduled",
        "mentor_request_status": "Accepted",
        "offering_type": "1:1 Mentorship",
    })
    frappe.db.commit()
    return name


def _make_block(mentor, date,
                whole_day=False, from_time=None, to_time=None,
                reason="_test_block_"):
    """Create a Mentor Blocked Time record; returns its name."""
    doc = frappe.get_doc({
        "doctype": "Mentor Blocked Time",
        "mentor": mentor,
        "date": date,
        "whole_day": 1 if whole_day else 0,
        "from_time": from_time,
        "to_time": to_time,
        "reason": reason,
    })
    doc.insert(ignore_permissions=True)
    frappe.db.commit()
    return doc.name


def _delete(doctype, name):
    """Silently delete a document."""
    try:
        if name and frappe.db.exists(doctype, name):
            frappe.delete_doc(doctype, name, ignore_permissions=True, force=True)
            frappe.db.commit()
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Test class
# ---------------------------------------------------------------------------

class IntegrationTestMentorSessionBooking(IntegrationTestCase):
    """
    Integration tests for reschedule_session().

    Mentor rahulg@gmail.com is available Mon–Wed, 10:00–15:00.
    - d_mon: next Monday  → used as "initial" booking date (raw SQL, no availability check)
    - d_tue: next Tuesday → used as reschedule target date (validate() enforces availability)
    - Reschedule times: 10:00–11:00 and 11:00–12:00 (within 10:00–15:00 window)
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Create shared offerings for the two test mentors
        cls.offering  = _make_offering(MENTOR_NAME)
        cls.offering2 = _make_offering(MENTOR_NAME2)

        # Pick the next two consecutive available (Mon/Tue) days for the mentor
        cls.d_mon = _next_weekday(0)            # next Monday
        cls.d_tue = _next_weekday(1)            # next Tuesday (for reschedule target)
        cls.past  = add_days(nowdate(), -1)     # yesterday

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        # Cascade delete: bookings → blocked times → offerings
        for bk in frappe.get_all(
            "Mentor Session Booking",
            filters={"offering": ["in", [cls.offering, cls.offering2]]},
            fields=["name"],
        ):
            _delete("Mentor Session Booking", bk.name)

        for bt in frappe.get_all(
            "Mentor Blocked Time",
            filters={"mentor": MENTOR_NAME, "reason": "_test_block_"},
            fields=["name"],
        ):
            _delete("Mentor Blocked Time", bt.name)

        _delete("Mentor Offering", cls.offering)
        _delete("Mentor Offering", cls.offering2)

    @staticmethod
    def _fn():
        from stridenex_app.stridenex_app.doctype.mentor_session_booking.mentor_session_booking import (
            reschedule_session,
        )
        return reschedule_session

    # ======================================================================
    # Test 1 — Happy path: reschedule to an open slot within availability
    # ======================================================================
    def test_01_reschedule_success(self):
        """Rescheduling to a free slot within mentor availability must succeed."""
        reschedule_session = self._fn()
        # Original booking inserted via SQL (bypasses validate)
        session = _make_booking(
            MENTOR_NAME, STUDENT_NAME, self.offering,
            self.d_mon, "09:00:00", "10:00:00"   # outside hours — only for setup
        )
        try:
            # Reschedule to Tuesday 10:00–11:00 (within Mon–Wed 10:00–15:00 window)
            result = reschedule_session(
                session_name=session,
                mentor=MENTOR_NAME,
                student=STUDENT_NAME,
                new_date=self.d_tue,
                new_from_time="10:00:00",
                new_to_time="11:00:00",
                reason="Unit test reschedule",
            )
            self.assertEqual(result["status"], "success")
            self.assertEqual(result["new_date"], self.d_tue)

            # Verify DB row was updated
            updated = frappe.db.get_value(
                "Mentor Session Booking", session,
                ["session_date", "from_time", "to_time", "reschedule_reason"],
                as_dict=True,
            )
            self.assertEqual(str(updated.session_date), self.d_tue)
            self.assertEqual(updated.reschedule_reason, "Unit test reschedule")
        finally:
            _delete("Mentor Session Booking", session)

    # ======================================================================
    # Test 2 — Invalid time range: from_time >= to_time
    # ======================================================================
    def test_02_invalid_time_range_raises(self):
        """from_time >= to_time must raise ValidationError before any DB write."""
        reschedule_session = self._fn()
        session = _make_booking(
            MENTOR_NAME, STUDENT_NAME, self.offering,
            self.d_mon, "10:00:00", "11:00:00"
        )
        try:
            with self.assertRaises(frappe.exceptions.ValidationError):
                reschedule_session(
                    session_name=session,
                    mentor=MENTOR_NAME,
                    student=STUDENT_NAME,
                    new_date=self.d_tue,
                    new_from_time="14:00:00",
                    new_to_time="12:00:00",   # ← to < from → invalid
                )
            # Confirm DB was NOT changed
            current = frappe.db.get_value(
                "Mentor Session Booking", session, "from_time"
            )
            self.assertEqual(str(current), "10:00:00")
        finally:
            _delete("Mentor Session Booking", session)

    # ======================================================================
    # Test 3 — Past date
    # ======================================================================
    def test_03_past_date_raises(self):
        """Rescheduling to a past date must raise ValidationError."""
        reschedule_session = self._fn()
        session = _make_booking(
            MENTOR_NAME, STUDENT_NAME, self.offering,
            self.d_mon, "10:00:00", "11:00:00"
        )
        try:
            with self.assertRaises(frappe.exceptions.ValidationError):
                reschedule_session(
                    session_name=session,
                    mentor=MENTOR_NAME,
                    student=STUDENT_NAME,
                    new_date=self.past,
                    new_from_time="10:00:00",
                    new_to_time="11:00:00",
                )
        finally:
            _delete("Mentor Session Booking", session)

    # ======================================================================
    # Test 4 — Whole-day block
    # ======================================================================
    def test_04_whole_day_block_raises(self):
        """A whole-day blocked time on the reschedule date must raise."""
        reschedule_session = self._fn()
        session = _make_booking(
            MENTOR_NAME, STUDENT_NAME, self.offering,
            self.d_mon, "10:00:00", "11:00:00"
        )
        block = _make_block(MENTOR_NAME, self.d_tue, whole_day=True)
        try:
            with self.assertRaises(frappe.exceptions.ValidationError):
                reschedule_session(
                    session_name=session,
                    mentor=MENTOR_NAME,
                    student=STUDENT_NAME,
                    new_date=self.d_tue,
                    new_from_time="10:00:00",
                    new_to_time="11:00:00",
                )
        finally:
            _delete("Mentor Session Booking", session)
            _delete("Mentor Blocked Time", block)

    # ======================================================================
    # Test 5 — Partial block overlapping the new slot
    # ======================================================================
    def test_05_partial_block_overlap_raises(self):
        """A partial blocked slot overlapping the new time must raise."""
        reschedule_session = self._fn()
        session = _make_booking(
            MENTOR_NAME, STUDENT_NAME, self.offering,
            self.d_mon, "10:00:00", "11:00:00"
        )
        # Block 12:00–14:00; new slot 11:00–13:00 → overlap
        block = _make_block(
            MENTOR_NAME, self.d_tue,
            from_time="12:00:00", to_time="14:00:00",
        )
        try:
            with self.assertRaises(frappe.exceptions.ValidationError):
                reschedule_session(
                    session_name=session,
                    mentor=MENTOR_NAME,
                    student=STUDENT_NAME,
                    new_date=self.d_tue,
                    new_from_time="11:00:00",
                    new_to_time="13:00:00",
                )
        finally:
            _delete("Mentor Session Booking", session)
            _delete("Mentor Blocked Time", block)

    # ======================================================================
    # Test 6 — Mentor conflict (another booking at the same new slot)
    # ======================================================================
    def test_06_mentor_session_conflict_raises(self):
        """If mentor has another booking at the new time, reschedule must raise."""
        reschedule_session = self._fn()
        # We need a second student so the student-conflict check doesn't fire instead
        second_student = frappe.db.get_value(
            "Student",
            {"name": ["!=", STUDENT_NAME]},
            "name"
        )
        if not second_student:
            self.skipTest("No second student in DB for mentor-conflict test")

        session_to_move = _make_booking(
            MENTOR_NAME, STUDENT_NAME, self.offering,
            self.d_mon, "10:00:00", "11:00:00"
        )
        # Conflict: mentor already booked with second_student on d_tue 11:00–12:00
        conflicting = _make_booking(
            MENTOR_NAME, second_student, self.offering,
            self.d_tue, "11:00:00", "12:00:00"
        )
        try:
            with self.assertRaises(frappe.exceptions.ValidationError):
                reschedule_session(
                    session_name=session_to_move,
                    mentor=MENTOR_NAME,
                    student=STUDENT_NAME,
                    new_date=self.d_tue,
                    new_from_time="11:00:00",
                    new_to_time="12:00:00",
                )
        finally:
            _delete("Mentor Session Booking", session_to_move)
            _delete("Mentor Session Booking", conflicting)

    # ======================================================================
    # Test 7 — Student conflict (student already booked with another mentor)
    # ======================================================================
    def test_07_student_session_conflict_raises(self):
        """If the student has another session at the new time, reschedule must raise."""
        reschedule_session = self._fn()
        session_to_move = _make_booking(
            MENTOR_NAME, STUDENT_NAME, self.offering,
            self.d_mon, "10:00:00", "11:00:00"
        )
        # Student already booked with MENTOR_NAME2 at the target slot
        conflicting = _make_booking(
            MENTOR_NAME2, STUDENT_NAME, self.offering2,
            self.d_tue, "12:00:00", "13:00:00"
        )
        try:
            with self.assertRaises(frappe.exceptions.ValidationError):
                reschedule_session(
                    session_name=session_to_move,
                    mentor=MENTOR_NAME,
                    student=STUDENT_NAME,
                    new_date=self.d_tue,
                    new_from_time="12:00:00",
                    new_to_time="13:00:00",
                )
        finally:
            _delete("Mentor Session Booking", session_to_move)
            _delete("Mentor Session Booking", conflicting)

    # ======================================================================
    # Test 8 — Non-Scheduled status must raise
    # ======================================================================
    def test_08_non_scheduled_status_raises(self):
        """Only 'Scheduled' bookings can be rescheduled; Completed must raise."""
        reschedule_session = self._fn()
        session = _make_booking(
            MENTOR_NAME, STUDENT_NAME, self.offering,
            self.d_mon, "10:00:00", "11:00:00"
        )
        frappe.db.set_value("Mentor Session Booking", session, "status", "Completed")
        frappe.db.commit()
        try:
            with self.assertRaises(frappe.exceptions.ValidationError):
                reschedule_session(
                    session_name=session,
                    mentor=MENTOR_NAME,
                    student=STUDENT_NAME,
                    new_date=self.d_tue,
                    new_from_time="10:00:00",
                    new_to_time="11:00:00",
                )
        finally:
            _delete("Mentor Session Booking", session)

    # ======================================================================
    # Test 9 — Partial block that does NOT overlap → reschedule succeeds
    # ======================================================================
    def test_09_non_overlapping_block_allows_reschedule(self):
        """A partial blocked slot that does NOT overlap the new slot must not block reschedule."""
        reschedule_session = self._fn()
        session = _make_booking(
            MENTOR_NAME, STUDENT_NAME, self.offering,
            self.d_mon, "10:00:00", "11:00:00"
        )
        # Block 13:00–15:00 on d_tue; new slot is 10:00–11:00 → no overlap
        block = _make_block(
            MENTOR_NAME, self.d_tue,
            from_time="13:00:00", to_time="15:00:00",
        )
        try:
            result = reschedule_session(
                session_name=session,
                mentor=MENTOR_NAME,
                student=STUDENT_NAME,
                new_date=self.d_tue,
                new_from_time="10:00:00",
                new_to_time="11:00:00",
            )
            self.assertEqual(result["status"], "success")
        finally:
            _delete("Mentor Session Booking", session)
            _delete("Mentor Blocked Time", block)
