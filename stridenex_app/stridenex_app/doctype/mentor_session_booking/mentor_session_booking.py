# Copyright (c) 2024, Your Company and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe import _
from frappe.utils import getdate, nowdate, get_time


class MentorSessionBooking(Document):

    # ------------------------------------------------------------------
    # Lifecycle Hooks
    # ------------------------------------------------------------------

    def validate(self):
        self.validate_not_self_booking()
        self.validate_date_not_past()
        self.validate_time_range()
        self.calculate_duration()
        self.validate_mentor_availability()
        self.validate_mentor_not_blocked()
        self.check_double_booking()

    def on_submit(self):
        # Mark status as Scheduled on submit if still default
        if self.status == "Scheduled":
            self.db_set("status", "Scheduled")

    def on_cancel(self):
        self.db_set("status", "Cancelled")

    # ------------------------------------------------------------------
    # Validators
    # ------------------------------------------------------------------

    def validate_not_self_booking(self):
        """Mentor and student must be different users."""
        if self.mentor == self.student:
            frappe.throw(_("Mentor and Student cannot be the same user."))

    def validate_date_not_past(self):
        """New bookings cannot be placed on past dates."""
        if self.is_new() and getdate(self.session_date) < getdate(nowdate()):
            frappe.throw(_("Session date cannot be in the past."))

    def validate_time_range(self):
        """from_time must be strictly before to_time."""
        if self.from_time and self.to_time:
            if self.from_time >= self.to_time:
                frappe.throw(_("From Time must be earlier than To Time."))

    def calculate_duration(self):
        """Auto-compute duration in minutes from from_time and to_time."""
        if self.from_time and self.to_time:
            start = get_time(self.from_time)
            end = get_time(self.to_time)
            start_mins = start.hour * 60 + start.minute
            end_mins = end.hour * 60 + end.minute
            self.duration = end_mins - start_mins

    def validate_mentor_availability(self):
        """
        The requested time window must fall within at least one of the mentor's
        weekly availability slots for the corresponding weekday.
        """
        day_name = getdate(self.session_date).strftime("%A")

        available_slots = frappe.get_all(
            "Mentor Availability",
            filters={"mentor": self.mentor, "day": day_name, "is_available": 1},
            fields=["from_time", "to_time"],
        )

        fits = any(
            slot.from_time <= self.from_time and slot.to_time >= self.to_time
            for slot in available_slots
        )

        if not fits:
            frappe.throw(
                _(
                    "The requested time ({0} – {1}) falls outside {2}'s availability "
                    "on {3}s."
                ).format(self.from_time, self.to_time, self.mentor, day_name)
            )

    def validate_mentor_not_blocked(self):
        """The session must not overlap with any blocked time on the session date."""
        blocked = frappe.get_all(
            "Mentor Blocked Time",
            filters={"mentor": self.mentor, "date": self.session_date},
            fields=["from_time", "to_time", "reason"],
        )

        for block in blocked:
            if _times_overlap(self.from_time, self.to_time, block.from_time, block.to_time):
                frappe.throw(
                    _(
                        "The mentor has blocked their time from {0} to {1} on {2}. "
                        "Reason: {3}"
                    ).format(block.from_time, block.to_time, self.session_date, block.reason or "N/A")
                )

    def check_double_booking(self):
        """
        Prevent two active sessions for the same mentor that overlap in time
        on the same date.
        """
        existing = frappe.get_all(
            "Mentor Session Booking",
            filters={
                "mentor": self.mentor,
                "session_date": self.session_date,
                "status": ["in", ["Scheduled", "Completed"]],
                "name": ["!=", self.name],
            },
            fields=["name", "from_time", "to_time", "student"],
        )

        for booking in existing:
            if _times_overlap(self.from_time, self.to_time, booking.from_time, booking.to_time):
                frappe.throw(
                    _(
                        "The mentor already has a session ({0}) booked from {1} to {2} "
                        "on {3}, which overlaps with this booking."
                    ).format(booking.name, booking.from_time, booking.to_time, self.session_date)
                )
                
    


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _times_overlap(start1, end1, start2, end2):
    """Return True when two half-open time intervals [start, end) overlap."""
    return start1 < end2 and start2 < end1


# ------------------------------------------------------------------
# Whitelisted API Methods
# ------------------------------------------------------------------

@frappe.whitelist()
def get_upcoming_sessions(mentor, limit=20):
    """
    Return upcoming scheduled sessions for a mentor, ordered by date and time.

    Args:
        mentor (str): Mentor User ID.
        limit  (int): Maximum number of records to return (default 20).

    Response shape:
        [
            {
                "name": "SES-2410",
                "student": "priya@example.com",
                "topic": "ML Project Milestone Review",
                "session_date": "2024-02-26",
                "from_time": "16:00:00",
                "to_time": "17:00:00",
                "duration": 60,
                "status": "Scheduled",
                "meeting_link": "https://..."
            },
            ...
        ]
    """
    if not mentor:
        frappe.throw(_("Mentor is required."))

    sessions = frappe.get_all(
        "Mentor Session Booking",
        filters={
            "mentor": mentor,
            "session_date": [">=", nowdate()],
            "status": "Scheduled",
        },
        fields=[
            "name", "student", "topic", "session_date",
            "from_time", "to_time", "duration", "status", "meeting_link",
        ],
        order_by="session_date asc, from_time asc",
        limit_page_length=int(limit),
    )

    return sessions


@frappe.whitelist()
def get_session_history(mentor, from_date=None, to_date=None, limit=50):
    """
    Return completed/cancelled sessions for a mentor within an optional date range.

    Args:
        mentor    (str): Mentor User ID.
        from_date (str): Optional start date (YYYY-MM-DD).
        to_date   (str): Optional end date (YYYY-MM-DD).
        limit     (int): Maximum records to return (default 50).
    """
    if not mentor:
        frappe.throw(_("Mentor is required."))

    filters = {
        "mentor": mentor,
        "status": ["in", ["Completed", "Cancelled"]],
    }

    if from_date:
        filters["session_date"] = [">=", from_date]
    if to_date:
        # If both dates provided, use between
        if from_date:
            filters["session_date"] = ["between", [from_date, to_date]]
        else:
            filters["session_date"] = ["<=", to_date]

    sessions = frappe.get_all(
        "Mentor Session Booking",
        filters=filters,
        fields=[
            "name", "student", "topic", "session_date",
            "from_time", "to_time", "duration", "status",
        ],
        order_by="session_date desc, from_time desc",
        limit_page_length=int(limit),
    )

    return sessions


@frappe.whitelist()
def reschedule_session(session_name, new_date, new_from_time, new_to_time):
    """
    Reschedule an existing Scheduled session to a new date and time slot.
    All availability and conflict validations are re-run via doc.save().

    Args:
        session_name  (str): Name of the Mentor Session Booking to reschedule.
        new_date      (str): New session date (YYYY-MM-DD).
        new_from_time (str): New start time (HH:MM:SS).
        new_to_time   (str): New end time (HH:MM:SS).

    Returns:
        str: Confirmation message.
    """
    doc = frappe.get_doc("Mentor Session Booking", session_name)

    if doc.status != "Scheduled":
        frappe.throw(
            _("Only Scheduled sessions can be rescheduled. Current status: {0}").format(doc.status)
        )

    doc.session_date = new_date
    doc.from_time = new_from_time
    doc.to_time = new_to_time
    doc.save(ignore_permissions=False)
    frappe.db.commit()

    return _("Session {0} has been rescheduled to {1} from {2} to {3}.").format(
        session_name, new_date, new_from_time, new_to_time
    )


@frappe.whitelist()
def cancel_session(session_name):
    """
    Cancel a scheduled session.

    Args:
        session_name (str): Name of the Mentor Session Booking.

    Returns:
        str: Confirmation message.
    """
    doc = frappe.get_doc("Mentor Session Booking", session_name)

    if doc.status != "Scheduled":
        frappe.throw(
            _("Only Scheduled sessions can be cancelled. Current status: {0}").format(doc.status)
        )

    doc.status = "Cancelled"
    doc.save(ignore_permissions=False)
    frappe.db.commit()

    return _("Session {0} has been cancelled.").format(session_name)


@frappe.whitelist()
def mark_session_completed(session_name):
    """
    Mark a scheduled session as Completed.

    Args:
        session_name (str): Name of the Mentor Session Booking.

    Returns:
        str: Confirmation message.
    """
    doc = frappe.get_doc("Mentor Session Booking", session_name)

    if doc.status != "Scheduled":
        frappe.throw(
            _("Only Scheduled sessions can be marked as Completed. Current status: {0}").format(
                doc.status
            )
        )

    doc.status = "Completed"
    doc.save(ignore_permissions=False)
    frappe.db.commit()

    return _("Session {0} marked as Completed.").format(session_name)


@frappe.whitelist()
def get_weekly_booked_sessions(mentor, week_start_date):
    """
    Return all booked sessions for a mentor during the ISO week that contains
    week_start_date (Monday to Sunday).

    Args:
        mentor          (str): Mentor User ID.
        week_start_date (str): Any date within the target week (YYYY-MM-DD).

    Returns:
        list of session dicts, each including student full name.
    """
    if not mentor or not week_start_date:
        frappe.throw(_("Mentor and week_start_date are required."))

    import datetime
    start = getdate(week_start_date)
    # Adjust to Monday
    monday = start - datetime.timedelta(days=start.weekday())
    sunday = monday + datetime.timedelta(days=6)

    sessions = frappe.get_all(
        "Mentor Session Booking",
        filters={
            "mentor": mentor,
            "session_date": ["between", [str(monday), str(sunday)]],
            "status": ["in", ["Scheduled", "Completed"]],
        },
        fields=[
            "name", "student", "topic", "session_date",
            "from_time", "to_time", "duration", "status", "meeting_link",
        ],
        order_by="session_date asc, from_time asc",
    )

    # Enrich with student full name
    for s in sessions:
        s["student_full_name"] = frappe.db.get_value("User", s.student, "full_name") or s.student

    return sessions