# Copyright (c) 2024, Your Company and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe import _
from frappe.utils import getdate, nowdate, get_time
import datetime


class MentorSessionBooking(Document):

    # ------------------------------------------------------------------
    # Lifecycle Hooks
    # ------------------------------------------------------------------

    def validate(self):
        self.validate_not_self_booking()
        self.validate_date_not_past()
        self.validate_time_range()
        self.calculate_duration()
        
        # ✅ Skip validations during cancel
        if self.status == "Cancelled":
            return
        
        self.validate_mentor_availability()
        self.validate_mentor_not_blocked()
        self.check_double_booking()

    def on_submit(self):
        if self.status == "Scheduled":
            self.db_set("status", "Scheduled")

    def on_cancel(self):
        self.db_set("status", "Cancelled")

    # ------------------------------------------------------------------
    # Validators
    # ------------------------------------------------------------------

    def validate_not_self_booking(self):
        if self.mentor == self.student:
            frappe.throw(_("Mentor and Student cannot be the same user."))

    def validate_date_not_past(self):
        if self.is_new() and getdate(self.session_date) < getdate(nowdate()):
            frappe.throw(_("Session date cannot be in the past."))

    def validate_time_range(self):
        if self.from_time and self.to_time:
            if self.from_time >= self.to_time:
                frappe.throw(_("From Time must be earlier than To Time."))

    def calculate_duration(self):
        if self.from_time and self.to_time:
            start = get_time(self.from_time)
            end = get_time(self.to_time)
            self.duration = (end.hour * 60 + end.minute) - (start.hour * 60 + start.minute)

    def validate_mentor_availability(self):
        day_name = getdate(self.session_date).strftime("%A")

        available_slots = frappe.get_all(
            "Mentor Availability",
            filters={"mentor": self.mentor, "day": day_name, "is_available": 1},
            fields=["from_time", "to_time"],
        )

        # ✅ Convert self times to time object
        self_from = get_time(self.from_time)
        self_to   = get_time(self.to_time)

        fits = any(
            get_time(slot.from_time) <= self_from and get_time(slot.to_time) >= self_to
            for slot in available_slots
        )

        if not fits:
            frappe.throw(
                _("The selected time ({0}–{1}) is outside {2}'s availability on {3}s.").format(
                    self.from_time, self.to_time, self.mentor, day_name
                )
            )

    def validate_mentor_not_blocked(self):
        blocked = frappe.get_all(
            "Mentor Blocked Time",
            filters={"mentor": self.mentor, "date": self.session_date},
            fields=["from_time", "to_time", "reason"],
        )
        for block in blocked:
            if _times_overlap(self.from_time, self.to_time, block.from_time, block.to_time):
                frappe.throw(
                    _("Mentor has blocked this time ({0}–{1}). Reason: {2}").format(
                        block.from_time, block.to_time, block.reason or "N/A"
                    )
                )

    def check_double_booking(self):
        existing = frappe.get_all(
            "Mentor Session Booking",
            filters={
                "mentor": self.mentor,
                "session_date": self.session_date,
                "status": ["in", ["Scheduled", "Completed"]],
                "name": ["!=", self.name],
            },
            fields=["name", "from_time", "to_time"],
        )
        for booking in existing:
            if _times_overlap(self.from_time, self.to_time, booking.from_time, booking.to_time):
                frappe.throw(
                    _("Mentor already has a session ({0}) from {1}–{2} on this date.").format(
                        booking.name, booking.from_time, booking.to_time
                    )
                )


# ------------------------------------------------------------------
# Shared Helper
# ------------------------------------------------------------------

def _times_overlap(start1, end1, start2, end2):
    start1 = get_time(start1)
    end1   = get_time(end1)
    start2 = get_time(start2)
    end2   = get_time(end2)

    return start1 < end2 and start2 < end1


def _time_to_str(t):
    """Safely convert timedelta or time object to HH:MM:SS string."""
    if t is None:
        return None
    if isinstance(t, datetime.timedelta):
        total = int(t.total_seconds())
        h = total // 3600
        m = (total % 3600) // 60
        s = total % 60
        return f"{h:02}:{m:02}:{s:02}"
    return str(t)


# ------------------------------------------------------------------
# Slot Calendar API  (used by the JS popup)
# ------------------------------------------------------------------

@frappe.whitelist()
def get_slot_calendar(mentor, from_date, to_date):
    """
    Return a day-by-day slot calendar for a mentor between two dates.

    Each slot carries one of four statuses:
        available  – open for booking
        booked     – already has a confirmed session
        blocked    – mentor has blocked this window
        unavailable – outside mentor's weekly availability

    Args:
        mentor    (str): Mentor User ID.
        from_date (str): Start date YYYY-MM-DD.
        to_date   (str): End date YYYY-MM-DD.

    Response shape:
    {
        "2024-03-04": [
            {
                "from_time": "10:00:00",
                "to_time":   "11:00:00",
                "status":    "available" | "booked" | "blocked",
                "session_name": null | "SES-0001",
                "student":      null | "student@test.com",
                "reason":       null | "Personal"   (for blocked slots)
            },
            ...
        ],
        ...
    }
    """
    if not mentor or not from_date or not to_date:
        frappe.throw(_("mentor, from_date, and to_date are all required."))

    start = getdate(from_date)
    end = getdate(to_date)

    if start > end:
        frappe.throw(_("from_date must be on or before to_date."))

    # ── 1. Mentor's weekly availability ──────────────────────────────
    weekly_avail = frappe.get_all(
        "Mentor Availability",
        filters={"mentor": mentor, "is_available": 1},
        fields=["day", "from_time", "to_time"],
        order_by="from_time asc",
    )

    # Group by weekday name
    avail_by_day = {}
    for slot in weekly_avail:
        avail_by_day.setdefault(slot.day, []).append(
            {"from_time": _time_to_str(slot.from_time), "to_time": _time_to_str(slot.to_time)}
        )

    # ── 2. Blocked times in range ─────────────────────────────────────
    blocked_records = frappe.get_all(
        "Mentor Blocked Time",
        filters={"mentor": mentor, "date": ["between", [from_date, to_date]]},
        fields=["date", "from_time", "to_time", "reason"],
    )
    blocked_by_date = {}
    for b in blocked_records:
        blocked_by_date.setdefault(str(b.date), []).append(
            {
                "from_time": _time_to_str(b.from_time),
                "to_time": _time_to_str(b.to_time),
                "reason": b.reason or "",
            }
        )

    # ── 3. Booked sessions in range ───────────────────────────────────
    booked_records = frappe.get_all(
        "Mentor Session Booking",
        filters={
            "mentor": mentor,
            "session_date": ["between", [from_date, to_date]],
            "status": ["in", ["Scheduled", "Completed"]],
        },
        fields=["session_date", "from_time", "to_time", "student", "name", "topic"],
    )
    booked_by_date = {}
    for b in booked_records:
        booked_by_date.setdefault(str(b.session_date), []).append(
            {
                "from_time": _time_to_str(b.from_time),
                "to_time": _time_to_str(b.to_time),
                "session_name": b.name,
                "student": b.student,
                "topic": b.topic,
            }
        )

    # ── 4. Build the calendar ─────────────────────────────────────────
    calendar = {}
    current = start

    while current <= end:
        date_str = str(current)
        day_name = current.strftime("%A")
        raw_slots = avail_by_day.get(day_name, [])
        day_slots = []

        for slot in raw_slots:
            split_slots = split_into_hour_slots(slot["from_time"], slot["to_time"])
            day_slots.extend(split_slots)

        day_result = []
        for slot in day_slots:
            ft = slot["from_time"]
            tt = slot["to_time"]

            # Check blocked
            is_blocked = False
            block_reason = ""
            for b in blocked_by_date.get(date_str, []):
                if _times_overlap(ft, tt, b["from_time"], b["to_time"]):
                    is_blocked = True
                    block_reason = b["reason"]
                    break

            # Check booked
            is_booked = False
            session_name = None
            student = None
            topic = None
            for bk in booked_by_date.get(date_str, []):
                if _times_overlap(ft, tt, bk["from_time"], bk["to_time"]):
                    is_booked = True
                    session_name = bk["session_name"]
                    student = bk["student"]
                    topic = bk["topic"]
                    break

            if is_blocked:
                status = "blocked"
            elif is_booked:
                status = "booked"
            else:
                status = "available"

            day_result.append(
                {
                    "from_time": ft,
                    "to_time": tt,
                    "status": status,
                    "session_name": session_name,
                    "student": student,
                    "topic": topic,
                    "reason": block_reason,
                }
            )

        calendar[date_str] = day_result
        current += datetime.timedelta(days=1)

    return calendar


@frappe.whitelist()
def book_slot(mentor, student, session_date, from_time, to_time, topic):
    """
    Create a new Mentor Session Booking for a student.

    Returns:
        dict: { "session_name": "SES-XXXX" }
    """
    if not frappe.has_permission("Mentor Session Booking", "create"):
        frappe.throw(_("You do not have permission to book a session."), frappe.PermissionError)

    doc = frappe.get_doc(
        {
            "doctype": "Mentor Session Booking",
            "mentor": mentor,
            "student": student,
            "session_date": session_date,
            "from_time": from_time,
            "to_time": to_time,
            "topic": topic,
            "status": "Scheduled",
        }
    )
    doc.insert(ignore_permissions=False)
    frappe.db.commit()
    return {"session_name": doc.name}


@frappe.whitelist()
def get_upcoming_sessions(mentor, limit=20):
    sessions = frappe.get_all(
        "Mentor Session Booking",
        filters={"mentor": mentor, "session_date": [">=", nowdate()], "status": "Scheduled"},
        fields=["name", "student", "topic", "session_date", "from_time", "to_time", "duration", "status", "meeting_link"],
        order_by="session_date asc, from_time asc",
        limit_page_length=int(limit),
    )
    return sessions


@frappe.whitelist()
def get_session_history(mentor, from_date=None, to_date=None, limit=50):
    filters = {"mentor": mentor, "status": ["in", ["Completed", "Cancelled"]]}
    if from_date and to_date:
        filters["session_date"] = ["between", [from_date, to_date]]
    return frappe.get_all(
        "Mentor Session Booking",
        filters=filters,
        fields=["name", "student", "topic", "session_date", "from_time", "to_time", "duration", "status"],
        order_by="session_date desc",
        limit_page_length=int(limit),
    )


@frappe.whitelist()
def reschedule_session(session_name, new_date, new_from_time, new_to_time):
    doc = frappe.get_doc("Mentor Session Booking", session_name)

    if doc.status != "Scheduled":
        frappe.throw(_("Only Scheduled sessions can be rescheduled."))

    # Store old values (optional debug)
    old_date = doc.session_date
    old_from = doc.from_time
    old_to   = doc.to_time

    # Update same document (IMPORTANT)
    doc.session_date = new_date
    doc.from_time = new_from_time
    doc.to_time = new_to_time

    doc.save()
    frappe.db.commit()

    return {
        "message": _("Session rescheduled successfully"),
        "old_slot": f"{old_date} {old_from}-{old_to}",
        "new_slot": f"{new_date} {new_from_time}-{new_to_time}"
    }



@frappe.whitelist()
def cancel_session(session_name):
    doc = frappe.get_doc("Mentor Session Booking", session_name)
    if doc.status != "Scheduled":
        frappe.throw(_("Only Scheduled sessions can be cancelled."))
    doc.status = "Cancelled"
    doc.save()
    frappe.db.commit()
    return _("Session {0} cancelled.").format(session_name)


@frappe.whitelist()
def mark_session_completed(session_name):
    doc = frappe.get_doc("Mentor Session Booking", session_name)
    if doc.status != "Scheduled":
        frappe.throw(_("Only Scheduled sessions can be marked as Completed."))
    doc.status = "Completed"
    doc.save()
    frappe.db.commit()
    return _("Session {0} marked as Completed.").format(session_name)


@frappe.whitelist()
def get_weekly_booked_sessions(mentor, week_start_date):
    start = getdate(week_start_date)
    monday = start - datetime.timedelta(days=start.weekday())
    sunday = monday + datetime.timedelta(days=6)
    sessions = frappe.get_all(
        "Mentor Session Booking",
        filters={
            "mentor": mentor,
            "session_date": ["between", [str(monday), str(sunday)]],
            "status": ["in", ["Scheduled", "Completed"]],
        },
        fields=["name", "student", "topic", "session_date", "from_time", "to_time", "duration", "status", "meeting_link"],
        order_by="session_date asc, from_time asc",
    )
    for s in sessions:
        s["student_full_name"] = frappe.db.get_value("User", s.student, "full_name") or s.student
    return sessions

@frappe.whitelist()
def split_into_hour_slots(from_time, to_time):
    slots = []

    start = get_time(from_time)
    end   = get_time(to_time)

    current = start

    while current < end:
        next_time = (datetime.datetime.combine(datetime.date.today(), current)
                     + datetime.timedelta(hours=1)).time()

        if next_time > end:
            break

        slots.append({
            "from_time": current.strftime("%H:%M:%S"),
            "to_time": next_time.strftime("%H:%M:%S")
        })

        current = next_time

    return slots


