# Copyright (c) 2024, Your Company and contributors
# For license information, please see license.txt

from frappe.email.doctype.email_queue.email_queue import send_now
from frappe.utils import today, nowtime, now_datetime

import frappe
from frappe.model.document import Document
from frappe import _
from frappe.utils import getdate, nowdate, get_time, add_days
import datetime
import calendar
from frappe.utils import get_url_to_form
from frappe.utils import time_diff_in_seconds

import frappe
from frappe.utils import (
    get_first_day,
    get_last_day,
    nowdate,
    getdate
)


class MentorSessionBooking(Document):
    def before_insert(self):
        self._fetch_session_type_from_offering()

    def autoname(self):
        from frappe.model.naming import make_autoname
        self.name = make_autoname("MSB-.YYYY.-.#####")

    def validate(self):
        # Resolve offering type if not set yet (fetch_from isn't always set before validation)
        if self.offering and not self.offering_type:
            self.offering_type = frappe.db.get_value("Mentor Offering", self.offering, "offering_type")

        # Resolve lms_batch from offering if not set
        if self.offering and not self.get("lms_batch"):
            self.lms_batch = frappe.db.get_value("Mentor Offering", self.offering, "lms_batch")

        # Automatically schedule bookings if the offering type is other than "1:1 Mentorship"
        if self.status not in ("Payment Pending", "Cancelled", "Completed", "Rejected"):
            if self.offering_type and self.offering_type != "1:1 Mentorship":
                self.status = "Scheduled"
                self.mentor_request_status = "Accepted"

        # Auto-fill session_date, from_time, to_time for Group Sessions / Workshops from Offering if not set
        if self.offering and self.offering_type in ("Group Session", "Workshop"):
            off_date, off_from, off_to = frappe.db.get_value("Mentor Offering", self.offering, ["start_date", "start_time", "end_time"])
            if off_date and not self.session_date:
                self.session_date = off_date
            if off_from and not self.from_time:
                self.from_time = off_from
            if off_to and not self.to_time:
                self.to_time = off_to

        self.fetch_mentor_from_offering()
        self.fetch_amount_from_offering()
        self.validate_not_self_booking()

        is_request_stage = (
            self.status in ("Pending", "Suggested Alt Time")
            or not self.from_time
            or not self.to_time
        )

        if is_request_stage:
            if self.session_date and getdate(self.session_date) < getdate(nowdate()):
                frappe.throw(_("Preferred date cannot be in the past."))
            return

        if self.status == "Cancelled":
            return

        if self.offering_type not in ("Group Session", "Workshop"):
            self.validate_date_not_past()
            self.validate_time_range()
            self.calculate_duration()
            self.validate_mentor_availability()
            self.validate_mentor_not_blocked()
            self.check_double_booking()

    def on_update(self):
        if self.status not in ("Payment Pending",):
            if self.offering:
                self.update_offering_aggregates()
            self._refresh_seat_count()

        if self.status in ("Scheduled", "Accepted", "Completed", "Pending"):
            if self.lms_batch and self.student:
                from stridenex_app.api_stridenex_app.app_utils import (
                    get_or_create_course_enrollment,
                    is_student_in_batch,
                    add_student_to_batch,
                )

                # 1. LMS Course Enrollment (optional, only if course is linked)
                lms_course = frappe.db.get_value(
                    "Mentor Offering", self.offering, "lms_course"
                )
                if lms_course:
                    enrollment_name = get_or_create_course_enrollment(
                        lms_course, self.student, batch=self.lms_batch
                    )
                    if self.lms_enrollment != enrollment_name:
                        self.db_set("lms_enrollment", enrollment_name)

                # 2. LMS Batch Enrollment
                # raise_if_duplicate=False: idempotent on re-saves (status updates, etc.)
                # Batch-full still throws and is caught below to log + not crash.
                try:
                    add_student_to_batch(
                        self.lms_batch,
                        self.student,
                        raise_if_duplicate=False,
                    )
                except Exception as e:
                    # Log real errors (e.g. batch full) without crashing the save
                    frappe.logger().error(
                        f"[MSB] Failed to enroll {self.student} in batch "
                        f"{self.lms_batch} for booking {self.name}: {e}"
                    )

        elif self.status in ("Cancelled", "Rejected", "Declined"):
            if self.lms_batch and self.student:
                try:
                    enrollment = frappe.db.get_value(
                        "LMS Batch Enrollment",
                        {"batch": self.lms_batch, "member": self.student},
                        "name"
                    )
                    if enrollment:
                        frappe.delete_doc(
                            "LMS Batch Enrollment",
                            enrollment,
                            ignore_permissions=True
                        )
                        frappe.db.commit()
                except Exception:
                    pass

        # Send confirmation/request notification if not already sent
        if self.status in ("Scheduled", "Pending"):
            notification_subject = "Booking Confirmed" if self.status == "Scheduled" else "New Session Booking Request"
            
            # Check if this notification has already been sent for this booking
            already_sent = frappe.db.exists("Notification Log", {
                "document_type": "Mentor Session Booking",
                "document_name": self.name,
                "subject": notification_subject
            })
            
            if not already_sent:
                student_email = frappe.db.get_value("Student", self.student, "email_id") or self.student
                mentor_email = frappe.db.get_value("Mentor", self.mentor, "email_id") or self.mentor
                
                user_to_notify = student_email if self.status == "Scheduled" else mentor_email
                resolved_user = frappe.db.get_value("User", {"email": user_to_notify}, "name") or frappe.db.get_value("User", user_to_notify, "name")
                
                if resolved_user:
                    if self.status == "Scheduled":
                        message = f"""
                            Your booking has been confirmed.

                            Offering: {self.get("offering_type") or "Mentor Session"}
                            Mentor: {self.mentor}
                            Date: {self.session_date}
                            Time: {self.from_time} - {self.to_time}
                            Topic: {self.get("topic") or "General"}
                        """
                    else:
                        message = f"""
                            A new mentor session request has been submitted.

                            Student: {self.student}
                            Date: {self.session_date}
                            Time: {self.from_time} - {self.to_time}
                            Topic: {self.get("topic") or "General"}
                        """
                    
                    create_notification(
                        user=resolved_user,
                        subject=notification_subject,
                        message=message,
                        document_type="Mentor Session Booking",
                        document_name=self.name,
                        ignore_permissions=True
                    )

    def _refresh_seat_count(self):
        if self.offering_type == "Group Session" and self.get("group_slot"):
            slot = frappe.get_doc("Group Session Slot", self.group_slot)
            slot.update_seat_count()
        elif self.offering_type == "Workshop" and self.get("workshop"):
            ws = frappe.get_doc("Workshop", self.workshop)
            ws.update_seat_count()

    def _fetch_session_type_from_offering(self):
        if self.offering and not self.session_type:
            cat = frappe.db.get_value("Mentor Offering", self.offering, "category")
            if cat:
                self.session_type = cat

        if self.offering and not self.offering_type:
            self.offering_type = frappe.db.get_value("Mentor Offering", self.offering, "offering_type")

    def fetch_mentor_from_offering(self):
        if self.offering and not self.mentor:
            self.mentor = frappe.db.get_value("Mentor Offering", self.offering, "mentor")

    def fetch_amount_from_offering(self):
        if self.offering and not self.amount_paid:
            price = frappe.db.get_value("Mentor Offering", self.offering, "price_per_session")
            if price:
                self.amount_paid = price

    def update_offering_aggregates(self):
        if self.offering:
            offering = frappe.get_doc("Mentor Offering", self.offering)
            offering.update_aggregates()

    def validate_not_self_booking(self):
        if self.mentor == self.student:
            frappe.throw(_("Mentor and Student cannot be the same user."))

    def validate_date_not_past(self):
        if self.is_new() and getdate(self.session_date) < getdate(nowdate()):
            frappe.throw(_("Session date cannot be in the past."))

    def validate_time_range(self):
        offering_type = frappe.db.get_value(
            "Mentor Offering", self.offering, "offering_type"
        ) if self.offering else None

        if offering_type != "1:1 Mentorship":
            return

        if self.from_time and self.to_time:
            if self.from_time >= self.to_time:
                frappe.throw(_("From Time must be earlier than To Time."))

    def calculate_duration(self):
        if self.from_time and self.to_time:
            start = get_time(self.from_time)
            end   = get_time(self.to_time)
            self.duration = (end.hour * 60 + end.minute) - (start.hour * 60 + start.minute)

    def validate_mentor_availability(self):
        if not self.offering:
            return

        offering_type = frappe.db.get_value(
            "Mentor Offering", self.offering, "offering_type"
        )

        if offering_type != "1:1 Mentorship":
            return

        day_name  = getdate(self.session_date).strftime("%A").lower()
        self_from = get_time(self.from_time)
        self_to   = get_time(self.to_time)

        availability_docs = frappe.get_all(
            "Mentor Availability",
            filters={"mentor": self.mentor, "is_available": 1},
            fields=["name", "schedule_type", "from_time", "to_time"]
        )

        fits = False

        for avail in availability_docs:
            doc = frappe.get_doc("Mentor Availability", avail.name)

            if avail.schedule_type == "Each Day Same Schedule":
                for row in (doc.days_multi or []):
                    if (row.day or "").strip().lower() == day_name:
                        if get_time(doc.from_time) <= self_from and get_time(doc.to_time) >= self_to:
                            fits = True
                            break
            else:
                for row in (doc.daily_schedule or []):
                    if (row.day or "").strip().lower() == day_name:
                        if get_time(row.from_time) <= self_from and get_time(row.to_time) >= self_to:
                            fits = True
                            break

            if fits:
                break

        if not fits:
            frappe.throw(
                _("The selected time ({0}–{1}) is outside {2}'s availability on {3}.").format(
                    self.from_time, self.to_time, self.mentor, day_name.capitalize()
                )
            )

    def validate_mentor_not_blocked(self):
        blocked = frappe.get_all(
            "Mentor Blocked Time",
            filters={"mentor": self.mentor, "date": self.session_date},
            fields=["from_time", "to_time", "reason", "whole_day"],
        )
        for block in blocked:
            if block.whole_day or _times_overlap(self.from_time, self.to_time, block.from_time, block.to_time):
                if block.whole_day:
                    frappe.throw(
                        _("Mentor has blocked the whole day.{0}").format(
                            f" Reason: {block.reason}" if block.reason else ""
                        )
                    )
                else:
                    frappe.throw(
                        _("Mentor has blocked this time ({0}–{1}). Reason: {2}").format(
                            block.from_time, block.to_time, block.reason or "N/A"
                        )
                    )

    def check_double_booking(self):
        existing = frappe.get_all(
            "Mentor Session Booking",
            filters={
                "mentor":       self.mentor,
                "session_date": self.session_date,
                "status":       ["in", ["Scheduled", "Completed"]],
                "name":         ["!=", self.name],
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
# Notification + Email Helper
# ------------------------------------------------------------------

@frappe.whitelist(allow_guest=False)
def create_notification(user, subject, message, document_type=None, document_name=None, ignore_permissions=False):
    """
    Permission: Caller must have READ on 'Notification Log'.
    Internal callers (accept_request, reschedule_session, etc.) already
    run inside a whitelisted context that passed its own permission check,
    so a lightweight READ guard here is enough.
    """
    # ----------------------------------------------------------
    # PERMISSION CHECK
    # ----------------------------------------------------------
    if not ignore_permissions:
        session_user = frappe.session.user

        if not frappe.has_permission("Notification Log", ptype="read", user=session_user):
            frappe.throw(
                _("You do not have permission to create notifications."),
                frappe.PermissionError
            )

    # ----------------------------------------------------------
    # Resolve User — unchanged logic
    # ----------------------------------------------------------
    if not user:
        return

    frappe.log_error(user)
    user = frappe.db.get_value("User", {"email": user}, "name")

    if not user:
        user = frappe.db.get_value("User", user, "name")

    if not user:
        frappe.log_error(f"User not found: {user}", "NOTIFICATION ERROR")
        return

    # ----------------------------------------------------------
    # EMAIL — unchanged logic
    # ----------------------------------------------------------
    try:
        frappe.sendmail(
            recipients=[user],
            subject=subject,
            message=message,
            now=True
        )
    except Exception:
        frappe.log_error(frappe.get_traceback(), "EMAIL ERROR")

    # ----------------------------------------------------------
    # NOTIFICATION LOG — unchanged logic
    # ----------------------------------------------------------
    try:
        from_user = frappe.session.user

        if not from_user or from_user == "Guest":
            from_user = "Administrator"

        if not frappe.db.exists("User", from_user):
            from_user = "Administrator"

        notification = frappe.get_doc({
            "doctype":       "Notification Log",
            "subject":       subject,
            "for_user":      user,
            "from_user":     from_user,
            "type":          "Alert",
            "document_type": document_type,
            "document_name": document_name,
            "email_content": message,
            "read":          0
        })

        notification.insert(ignore_permissions=True)
        frappe.db.commit()

        frappe.publish_realtime(
            event="notification",
            message={"user": user},
            user=user
        )

    except Exception:
        frappe.log_error(frappe.get_traceback(), "NOTIFICATION ERROR")


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _times_overlap(start1, end1, start2, end2):
    if not (start1 and end1 and start2 and end2):
        return False
    start1 = get_time(start1)
    end1   = get_time(end1)
    start2 = get_time(start2)
    end2   = get_time(end2)
    return start1 < end2 and start2 < end1


def _time_to_str(t):
    if t is None:
        return None
    if isinstance(t, datetime.timedelta):
        total = int(t.total_seconds())
        h = total // 3600
        m = (total % 3600) // 60
        s = total % 60
        return f"{h:02}:{m:02}:{s:02}"
    return str(t)

import datetime

import frappe
from frappe import _
from frappe.utils import nowdate, add_days, getdate, get_time

# ----------------------------------------------------------------
# CONFIG — matches your "Mentor Offering" schema
# ----------------------------------------------------------------
OFFERING_TYPE_FIELD = "offering_type"      # fieldname on Mentor Offering
GROUP_SESSION_VALUE = "Group Session"      # exact value for group offerings
ONE_ON_ONE_VALUE = "1:1 Mentorship"        # exact value for 1:1 offerings (adjust if different)
CAPACITY_FIELD = "max_group_size"          # fieldname on Mentor Offering for group capacity

NON_BLOCKING_STATUSES = ["Cancelled", "Rejected"]

# Fields pulled from Mentor Offering for a group session response
OFFERING_FIELDS = [
    "name", "mentor", "title", "offering_type", "category", "lms_batch",
    "duration_minutes", "start_date", "end_date", "start_time", "end_time",
    "batch_details", "max_group_size", "price_per_session", "status", "description",
]


# ==================================================================
# HELPER: fetch offering meta
# ==================================================================
def _get_offering_doc(offering):
    """Raw dict of the Mentor Offering row, or None."""
    if not offering:
        return None
    return frappe.db.get_value("Mentor Offering", offering, OFFERING_FIELDS, as_dict=True)


def _is_group(offering_doc):
    return bool(offering_doc) and offering_doc.get(OFFERING_TYPE_FIELD) == GROUP_SESSION_VALUE


# ==================================================================
# get_slot_calendar
# ==================================================================
@frappe.whitelist(allow_guest=False)
def get_slot_calendar(mentor, from_date=None, to_date=None, offering=None):
    """
    Permission: READ on 'Mentor Session Booking'.

    Behaviour now depends on the offering's type:
      - offering_type == "Group Session": returns the offering's fixed
        date/time/capacity + current booking count. No calendar is built.
      - Anything else (1:1, or no offering given): original day-by-day
        availability calendar, unchanged.
    """
    session_user = frappe.session.user

    if not frappe.has_permission("Mentor Session Booking", ptype="read", user=session_user):
        frappe.throw(
            _("You do not have permission to view the session calendar."),
            frappe.PermissionError
        )

    offering_doc = _get_offering_doc(offering)

    # ------------------------------------------------------------
    # GROUP SESSION or WORKSHOP -> return offering details card,
    # not a day-by-day calendar (both types have fixed date/time)
    # ------------------------------------------------------------
    if offering_doc and offering_doc.get(OFFERING_TYPE_FIELD) in ("Group Session", "Workshop"):
        return _get_group_session_details(offering_doc, mentor)

    # ------------------------------------------------------------
    # 1:1 (or no offering) -> original calendar logic, unchanged
    # ------------------------------------------------------------
    if not from_date and not to_date:
        from_date = nowdate()
        to_date = add_days(from_date, 6)

    if not mentor or not from_date or not to_date:
        frappe.throw(_("mentor, from_date, and to_date are required"))

    duration_minutes = 60
    if offering_doc and offering_doc.get("duration_minutes"):
        duration_minutes = int(offering_doc["duration_minutes"])

    start = getdate(from_date)
    end = getdate(to_date)

    avail_by_day = {}
    for avail in frappe.get_all(
        "Mentor Availability",
        filters={"mentor": mentor, "is_available": 1},
        fields=["name", "schedule_type"]
    ):
        doc = frappe.get_doc("Mentor Availability", avail.name)
        if avail.schedule_type == "Each Day Same Schedule":
            for row in (doc.days_multi or []):
                key = (row.day or "").strip().lower()
                avail_by_day.setdefault(key, []).append({
                    "from_time": _time_to_str(doc.from_time),
                    "to_time": _time_to_str(doc.to_time),
                })
        else:
            for row in (doc.daily_schedule or []):
                key = (row.day or "").strip().lower()
                avail_by_day.setdefault(key, []).append({
                    "from_time": _time_to_str(row.from_time),
                    "to_time": _time_to_str(row.to_time),
                })

    blocked_by_date = {}
    for b in frappe.get_all(
        "Mentor Blocked Time",
        filters={"mentor": mentor, "date": ["between", [from_date, to_date]]},
        fields=["date", "from_time", "to_time", "reason", "whole_day"]
    ):
        blocked_by_date.setdefault(str(b.date), []).append({
            "from_time": _time_to_str(b.from_time) if not b.whole_day else None,
            "to_time": _time_to_str(b.to_time) if not b.whole_day else None,
            "reason": b.reason or "",
            "whole_day": b.whole_day,
        })

    booked_by_date = {}

    # ── 1:1 bookings: one chip per booking ───────────────────────────────────
    for b in frappe.get_all(
        "Mentor Session Booking",
        filters={
            "mentor": mentor,
            "session_date": ["between", [from_date, to_date]],
            "status": ["not in", NON_BLOCKING_STATUSES],
            "offering_type": ["in", ["1:1 Mentorship", "", None]],
        },
        fields=["session_date", "from_time", "to_time", "student", "name", "topic", "offering_type"]
    ):
        booked_by_date.setdefault(str(b.session_date), []).append({
            "from_time": _time_to_str(b.from_time),
            "to_time": _time_to_str(b.to_time),
            "session_name": b.name,
            "student": b.student,
            "topic": b.topic,
            "offering_type": b.offering_type,
            "participant_count": 1,
        })

    # ── Group Session / Workshop bookings: collapse per offering ─────────────
    # Many students may book the same offering — we show ONE chip per offering,
    # not one chip per student, so the calendar doesn't explode with duplicates.
    group_raw = frappe.get_all(
        "Mentor Session Booking",
        filters={
            "mentor": mentor,
            "session_date": ["between", [from_date, to_date]],
            "status": ["not in", NON_BLOCKING_STATUSES],
            "offering_type": ["in", ["Group Session", "Workshop"]],
        },
        fields=["session_date", "from_time", "to_time", "student", "name",
                "topic", "offering", "offering_type"]
    )

    # Key: (date_str, offering) — collapse to one chip per session
    group_chips = {}
    for b in group_raw:
        date_str = str(b.session_date)
        key = (date_str, b.offering or b.name)
        if key not in group_chips:
            group_chips[key] = {
                "from_time": _time_to_str(b.from_time),
                "to_time": _time_to_str(b.to_time),
                "session_name": b.name,          # representative booking name
                "student": None,                  # no single student — it's a group
                "topic": b.topic,
                "offering": b.offering,
                "offering_type": b.offering_type,
                "participant_count": 1,
            }
        else:
            group_chips[key]["participant_count"] += 1

    for (date_str, _key), chip in group_chips.items():
        booked_by_date.setdefault(date_str, []).append(chip)

    cal = {}
    current = start

    while current <= end:
        date_str = str(current)
        day_key = current.strftime("%A").lower()
        raw_windows = avail_by_day.get(day_key, [])
        day_bookings = booked_by_date.get(date_str, [])
        day_blocks = blocked_by_date.get(date_str, [])

        occupied_intervals = (
            [(b["from_time"], b["to_time"]) for b in day_bookings] +
            [(b["from_time"], b["to_time"]) for b in day_blocks if not b.get("whole_day")]
        )

        is_whole_day_blocked = any(b.get("whole_day") for b in day_blocks)

        day_result = []

        for window in raw_windows:
            win_from_min = _to_minutes(window["from_time"])
            win_to_min = _to_minutes(window["to_time"])

            occupied_chips = []

            if is_whole_day_blocked:
                reason = ""
                for bl in day_blocks:
                    if bl.get("whole_day"):
                        reason = bl["reason"]
                        break
                occupied_chips.append({
                    "from_time": window["from_time"],
                    "to_time": window["to_time"],
                    "status": "blocked",
                    "session_name": None,
                    "student": None,
                    "topic": None,
                    "offering": None,
                    "offering_type": None,
                    "participant_count": 0,
                    "reason": reason,
                })
                day_result.extend(occupied_chips)
                continue

            for bk in day_bookings:
                bk_from = _to_minutes(bk["from_time"])
                bk_to = _to_minutes(bk["to_time"])
                if bk_from < win_to_min and bk_to > win_from_min:
                    chip_from = max(bk_from, win_from_min)
                    chip_to = min(bk_to, win_to_min)
                    occupied_chips.append({
                        "from_time": _from_minutes(chip_from),
                        "to_time": _from_minutes(chip_to),
                        "status": "booked",
                        "session_name": bk["session_name"],
                        "student": bk.get("student"),
                        "topic": bk["topic"],
                        "offering": bk.get("offering"),
                        "offering_type": bk.get("offering_type"),
                        "participant_count": bk.get("participant_count", 1),
                        "reason": "",
                    })

            for bl in day_blocks:
                bl_from = _to_minutes(bl["from_time"])
                bl_to = _to_minutes(bl["to_time"])
                if bl_from < win_to_min and bl_to > win_from_min:
                    chip_from = max(bl_from, win_from_min)
                    chip_to = min(bl_to, win_to_min)
                    occupied_chips.append({
                        "from_time": _from_minutes(chip_from),
                        "to_time": _from_minutes(chip_to),
                        "status": "blocked",
                        "session_name": None,
                        "student": None,
                        "topic": None,
                        "offering": None,
                        "offering_type": None,
                        "participant_count": 0,
                        "reason": bl["reason"],
                    })

            free_slots = split_into_duration_slots(
                window["from_time"],
                window["to_time"],
                duration_minutes=duration_minutes,
                booked_intervals=occupied_intervals,
            )
            for slot in free_slots:
                slot["status"] = "available"
                slot["session_name"] = None
                slot["student"] = None
                slot["topic"] = None
                slot["offering"] = None
                slot["offering_type"] = None
                slot["participant_count"] = 0
                slot["reason"] = ""

            all_chips = free_slots + occupied_chips
            all_chips.sort(key=lambda s: _to_minutes(s["from_time"]))
            day_result.extend(all_chips)

        cal[date_str] = day_result
        current += datetime.timedelta(days=1)

    return cal


def _get_group_session_details(offering_doc, mentor):
    """
    For a Group Session offering: no slot splitting, no calendar.
    Just the offering's fixed date/time + how full it is.
    """
    offering_name = offering_doc["name"]
    max_group_size = offering_doc.get(CAPACITY_FIELD) or 0

    bookings = frappe.get_all(
        "Mentor Session Booking",
        filters={
            "mentor": mentor,
            "offering": offering_name,
            "status": ["not in", NON_BLOCKING_STATUSES],
        },
        fields=["name", "student", "topic", "status"],
    )

    participants_booked = len(bookings)
    seats_left = max(max_group_size - participants_booked, 0) if max_group_size else None
    seat_status = "full" if (max_group_size and participants_booked >= max_group_size) else "open"

    return {
        "offering_type": GROUP_SESSION_VALUE,
        "offering": offering_name,
        "mentor": offering_doc.get("mentor") or mentor,
        "title": offering_doc.get("title"),
        "description": offering_doc.get("description"),
        "category": offering_doc.get("category"),
        "lms_batch": offering_doc.get("lms_batch"),
        "batch_details": offering_doc.get("batch_details"),
        "price_per_session": offering_doc.get("price_per_session"),
        "status": offering_doc.get("status"),
        "start_date": str(offering_doc["start_date"]) if offering_doc.get("start_date") else None,
        "end_date": str(offering_doc["end_date"]) if offering_doc.get("end_date") else None,
        "start_time": _time_to_str(offering_doc.get("start_time")),
        "end_time": _time_to_str(offering_doc.get("end_time")),
        "duration_minutes": offering_doc.get("duration_minutes"),
        "max_group_size": max_group_size,
        "participants_booked": participants_booked,
        "seats_left": seats_left,
        "seat_status": seat_status,
        "participants": [
            {"student": b.student, "session_name": b.name, "topic": b.topic, "status": b.status}
            for b in bookings
        ],
    }


# ==================================================================
# book_slot
# ==================================================================
@frappe.whitelist(allow_guest=False)
def book_slot(mentor, student, session_date, from_time, to_time, topic, offering=None):
    """
    Permission: CREATE on 'Mentor Session Booking'.

    For Group Session offerings, session_date/from_time/to_time are
    IGNORED if passed and are instead taken directly from the offering
    (they're fixed there) — this guarantees every participant lands on
    the exact same slot and prevents mismatched/fragmented bookings.
    """
    session_user = frappe.session.user

    if not frappe.has_permission("Mentor Session Booking", ptype="create", user=session_user):
        frappe.throw(
            _("You do not have permission to book a session."),
            frappe.PermissionError
        )

    if not (mentor and student and topic):
        frappe.throw(_("Mentor, student and topic are required."))

    offering_doc = _get_offering_doc(offering)
    is_group = _is_group(offering_doc)

    # Determine if this offering is a Group Session or Workshop — both are
    # directly scheduled without requiring mentor acceptance.
    offering_type_value = offering_doc.get(OFFERING_TYPE_FIELD) if offering_doc else None
    is_auto_schedule = offering_type_value in ("Group Session", "Workshop")

    # Group Sessions AND Workshops both have fixed date/time on the offering.
    # Pull those values directly so every participant lands on the exact same slot.
    if is_auto_schedule:
        if not offering_doc.get("start_date") or not offering_doc.get("start_time") or not offering_doc.get("end_time"):
            frappe.throw(_("This {0} offering is missing date/time details. Contact the mentor.").format(offering_type_value))

        session_date = getdate(offering_doc["start_date"])
        from_time = offering_doc["start_time"]
        to_time = offering_doc["end_time"]
    else:
        if not (session_date and from_time and to_time):
            frappe.throw(_("Session date, from time and to time are required."))
        session_date = getdate(session_date)

    new_from = get_time(from_time)
    new_to = get_time(to_time)

    if new_from >= new_to:
        frappe.throw(_("'From Time' must be earlier than 'To Time'."))

    if is_auto_schedule:
        _validate_group_booking(mentor, student, session_date, from_time, to_time, offering, offering_doc)
    else:
        _validate_1on1_booking(mentor, session_date, new_from, new_to, from_time, to_time)

    # Student can't be double-booked at the same time, group or 1:1.
    _validate_student_conflict(student, session_date, new_from, new_to, from_time, to_time)

    # If the offering type is other than "1:1 Mentorship", the status is directly Scheduled.
    # 1:1 Mentorship (and bookings without an offering) go through the Pending flow.
    if offering_doc and offering_type_value != "1:1 Mentorship":
        booking_status = "Scheduled"
        mentor_request_status = "Accepted"
    else:
        booking_status = "Pending"
        mentor_request_status = "Pending"

    doc = frappe.get_doc({
        "doctype": "Mentor Session Booking",
        "offering": offering,
        "mentor": mentor,
        "student": student,
        "session_date": session_date,
        "from_time": from_time,
        "to_time": to_time,
        "topic": topic,
        "status": booking_status,
        "mentor_request_status": mentor_request_status,
    })

    doc.insert(ignore_permissions=False)
    frappe.db.commit()

    if booking_status == "Scheduled":
        # Notify the student that their seat is confirmed immediately.
        create_notification(
            user=student,
            subject="Booking Confirmed",
            message=f"""
                Your booking has been confirmed.

                Offering: {offering_type_value}
                Mentor: {mentor}
                Date: {session_date}
                Time: {from_time} - {to_time}
                Topic: {topic}
            """,
            document_type="Mentor Session Booking",
            document_name=doc.name
        )
    else:
        # Notify the mentor about the new pending session request.
        create_notification(
            user=mentor,
            subject="New Session Booking Request",
            message=f"""
                A new mentor session request has been submitted.

                Student: {student}
                Date: {session_date}
                Time: {from_time} - {to_time}
                Topic: {topic}
            """,
            document_type="Mentor Session Booking",
            document_name=doc.name
        )

    return {"session_name": doc.name, "status": booking_status}


def _validate_1on1_booking(mentor, session_date, new_from, new_to, from_time, to_time):
    """Original exclusive-overlap check — unchanged."""
    existing_bookings = frappe.get_all(
        "Mentor Session Booking",
        filters={
            "mentor": mentor,
            "session_date": session_date,
            "status": ["not in", NON_BLOCKING_STATUSES],
        },
        fields=["name", "from_time", "to_time", "student", "status"],
    )

    for booking in existing_bookings:
        existing_from = get_time(booking.from_time)
        existing_to = get_time(booking.to_time)

        if new_from < existing_to and new_to > existing_from:
            frappe.throw(
                _(
                    "This time slot ({0} - {1}) on {2} is already booked "
                    "for mentor {3} (Booking: {4}). Please choose a different "
                    "date or time."
                ).format(from_time, to_time, session_date, mentor, booking.name),
                frappe.ValidationError,
            )


def _validate_group_booking(mentor, student, session_date, from_time, to_time, offering, offering_doc):
    """
    Since date/time are fixed and derived directly from the offering, we
    check:
      1. The student hasn't already booked this same offering.
      2. The offering hasn't exceeded max capacity.
    """
    # ── Duplicate student check ──────────────────────────────────────────
    already_booked = frappe.get_all(
        "Mentor Session Booking",
        filters={
            "student": student,
            "offering": offering,
            "status": ["not in", NON_BLOCKING_STATUSES],
        },
        fields=["name"],
        limit=1,
    )

    if already_booked:
        frappe.throw(
            _(
                "You are already registered for '{0}'. "
                "You cannot book the same session more than once."
            ).format(offering_doc.get("title") or offering),
            frappe.ValidationError,
        )

    # ── Capacity check ───────────────────────────────────────────────────
    max_group_size = offering_doc.get(CAPACITY_FIELD) or 0

    existing = frappe.get_all(
        "Mentor Session Booking",
        filters={
            "mentor": mentor,
            "offering": offering,
            "status": ["not in", NON_BLOCKING_STATUSES],
        },
        fields=["name"],
    )

    if max_group_size and len(existing) >= max_group_size:
        frappe.throw(
            _(
                "This session '{0}' on {1} is already full ({2}/{3} seats)."
            ).format(offering_doc.get("title") or offering, session_date, len(existing), max_group_size),
            frappe.ValidationError,
        )


def _validate_student_conflict(student, session_date, new_from, new_to, from_time, to_time):
    student_bookings = frappe.get_all(
        "Mentor Session Booking",
        filters={
            "student": student,
            "session_date": session_date,
            "status": ["not in", NON_BLOCKING_STATUSES],
        },
        fields=["name", "from_time", "to_time"],
    )

    for booking in student_bookings:
        existing_from = get_time(booking.from_time)
        existing_to = get_time(booking.to_time)

        if new_from < existing_to and new_to > existing_from:
            frappe.throw(
                _(
                    "You already have another session booked during "
                    "{0} - {1} on {2} (Booking: {3})."
                ).format(from_time, to_time, session_date, booking.name),
                frappe.ValidationError,
            )


# def _validate_group_booking(mentor, session_date, from_time, to_time, offering, offering_meta):
#     """
#     Group sessions: many students can share the SAME fixed (from_time, to_time)
#     slot for the SAME offering, up to max_group_size. We only block when:
#       1. Capacity is full for that exact slot, or
#       2. The mentor has a conflicting (overlapping but not identical) booking
#          of a DIFFERENT slot/offering at that time — mentor still can't be
#          double-booked across two different sessions simultaneously.
#     """
#     max_group_size = offering_meta["max_group_size"]

#     all_bookings = frappe.get_all(
#         "Mentor Session Booking",
#         filters={
#             "mentor": mentor,
#             "session_date": session_date,
#             "status": ["not in", NON_BLOCKING_STATUSES],
#         },
#         fields=["name", "from_time", "to_time", "offering", "student"],
#     )

#     new_from = get_time(from_time)
#     new_to = get_time(to_time)

#     same_slot_count = 0
#     for booking in all_bookings:
#         existing_from = get_time(booking.from_time)
#         existing_to = get_time(booking.to_time)
#         same_slot = (
#             existing_from == new_from
#             and existing_to == new_to
#             and booking.offering == offering
#         )

#         if same_slot:
#             same_slot_count += 1
#             continue

#         # Different slot/offering but overlapping time -> mentor conflict
#         if new_from < existing_to and new_to > existing_from:
#             frappe.throw(
#                 _(
#                     "Mentor {0} already has a different session ({1}) that "
#                     "overlaps {2} - {3} on {4}. Please choose a different time."
#                 ).format(mentor, booking.name, from_time, to_time, session_date),
#                 frappe.ValidationError,
#             )

#     if max_group_size is not None and same_slot_count >= max_group_size:
#         frappe.throw(
#             _(
#                 "This group session ({0} - {1} on {2}) is already full "
#                 "({3}/{4} participants)."
#             ).format(from_time, to_time, session_date, same_slot_count, max_group_size),
#             frappe.ValidationError,
#         )


# def _validate_student_conflict(student, session_date, new_from, new_to, from_time, to_time):
#     student_bookings = frappe.get_all(
#         "Mentor Session Booking",
#         filters={
#             "student": student,
#             "session_date": session_date,
#             "status": ["not in", NON_BLOCKING_STATUSES],
#         },
#         fields=["name", "from_time", "to_time"],
#     )

#     for booking in student_bookings:
#         existing_from = get_time(booking.from_time)
#         existing_to = get_time(booking.to_time)

#         if new_from < existing_to and new_to > existing_from:
#             frappe.throw(
#                 _(
#                     "You already have another session booked during "
#                     "{0} - {1} on {2} (Booking: {3})."
#                 ).format(from_time, to_time, session_date, booking.name),
#                 frappe.ValidationError,
#             )




@frappe.whitelist(allow_guest=False)
def reschedule_session(session_name, mentor, student, new_date, new_from_time, new_to_time, reason=None):
    """
    Permission: WRITE on 'Mentor Session Booking'.
    Configured via Role Permission Manager — no hardcoded roles.
    reason: Optional text explaining why the session is being rescheduled.

    Validates (in order) BEFORE saving:
      1. WRITE permission
      2. Session exists and is in 'Scheduled' status
      3. new_from_time < new_to_time
      4. new_date is not in the past
      5. Mentor has no blocked time overlapping the new slot (whole-day or partial)
      6. Mentor has no other session overlapping the new slot (excludes this booking)
      7. Student has no other session overlapping the new slot (excludes this booking)
    Only after all validations pass does it save and send a notification.
    """
    # ----------------------------------------------------------
    # 1. PERMISSION CHECK
    # ----------------------------------------------------------
    session_user = frappe.session.user

    if not frappe.has_permission("Mentor Session Booking", ptype="write", user=session_user):
        frappe.throw(
            _("You do not have permission to reschedule sessions."),
            frappe.PermissionError
        )

    # ----------------------------------------------------------
    # 2. Load document and validate current status
    # ----------------------------------------------------------
    doc = frappe.get_doc("Mentor Session Booking", session_name)

    if doc.status != "Scheduled":
        frappe.throw(_("Only Scheduled sessions can be rescheduled."))

    # Fall back to values on the document when caller omits them
    if not mentor:
        mentor = doc.mentor
    if not student:
        student = doc.student

    # ----------------------------------------------------------
    # 3. Required fields + time range check
    # ----------------------------------------------------------
    if not (new_date and new_from_time and new_to_time):
        frappe.throw(_("New date, from time, and to time are required."))

    new_from = get_time(new_from_time)
    new_to   = get_time(new_to_time)

    if new_from >= new_to:
        frappe.throw(_("'From Time' must be earlier than 'To Time'."))

    # ----------------------------------------------------------
    # 4. Validate new_date is not in the past
    # ----------------------------------------------------------
    if getdate(new_date) < getdate(nowdate()):
        frappe.throw(_("Rescheduled session date cannot be in the past."))

    # ----------------------------------------------------------
    # 5. Check mentor blocked time on new_date
    # ----------------------------------------------------------
    blocked_times = frappe.get_all(
        "Mentor Blocked Time",
        filters={"mentor": mentor, "date": new_date},
        fields=["from_time", "to_time", "reason", "whole_day"],
    )
    for block in blocked_times:
        if block.whole_day:
            frappe.throw(
                _("Mentor has blocked the entire day on {0}.{1}").format(
                    new_date,
                    f" Reason: {block.reason}" if block.reason else ""
                ),
                frappe.ValidationError
            )
        if _times_overlap(new_from_time, new_to_time, block.from_time, block.to_time):
            frappe.throw(
                _("Mentor has a blocked slot from {0}–{1} on {2}. Reason: {3}").format(
                    block.from_time, block.to_time, new_date, block.reason or "N/A"
                ),
                frappe.ValidationError
            )

    # ----------------------------------------------------------
    # 6. Check mentor has no other overlapping session on new_date
    #    (exclude the current session being rescheduled)
    # ----------------------------------------------------------
    mentor_sessions = frappe.get_all(
        "Mentor Session Booking",
        filters={
            "mentor":       mentor,
            "session_date": new_date,
            "status":       ["not in", NON_BLOCKING_STATUSES],
            "name":         ["!=", session_name],
        },
        fields=["name", "from_time", "to_time"],
    )
    for s in mentor_sessions:
        if _times_overlap(new_from_time, new_to_time, s.from_time, s.to_time):
            frappe.throw(
                _(
                    "Mentor already has a session ({0}) from {1}–{2} on {3}. "
                    "Please choose a different time slot."
                ).format(s.name, s.from_time, s.to_time, new_date),
                frappe.ValidationError
            )

    # ----------------------------------------------------------
    # 7. Check student has no other overlapping session on new_date
    #    (exclude the current session being rescheduled)
    # ----------------------------------------------------------
    student_sessions = frappe.get_all(
        "Mentor Session Booking",
        filters={
            "student":      student,
            "session_date": new_date,
            "status":       ["not in", NON_BLOCKING_STATUSES],
            "name":         ["!=", session_name],
        },
        fields=["name", "from_time", "to_time"],
    )
    for s in student_sessions:
        if _times_overlap(new_from_time, new_to_time, s.from_time, s.to_time):
            frappe.throw(
                _(
                    "Student already has another session ({0}) from {1}–{2} on {3}. "
                    "Please choose a different time slot."
                ).format(s.name, s.from_time, s.to_time, new_date),
                frappe.ValidationError
            )

    # ----------------------------------------------------------
    # All validations passed — snapshot old slot, apply changes, save
    # ----------------------------------------------------------
    old_date = doc.session_date
    old_from = doc.from_time
    old_to   = doc.to_time

    doc.session_date          = new_date
    doc.from_time             = new_from_time
    doc.to_time               = new_to_time
    doc.mentor_request_status = "Accepted"
    if reason:
        doc.reschedule_reason = reason

    doc.save(ignore_permissions=True)
    frappe.db.commit()

    # ----------------------------------------------------------
    # Resolve student email and send notification
    # ----------------------------------------------------------
    student_email = frappe.db.get_value("Student", student, "email_id")

    if not student_email:
        frappe.log_error(
            f"reschedule_session: no email_id on Student '{student}' for booking {session_name}",
            "Reschedule Notification Warning"
        )
    else:
        reason_text = f"\nReason: {reason}" if reason else ""

        create_notification(
            user=student_email,
            subject="Session Rescheduled",
            message=f"""
                Your mentor session has been rescheduled.
                {reason_text}

                Old Slot: {old_date}  {old_from} – {old_to}
                New Slot: {new_date}  {new_from_time} – {new_to_time}

                Mentor: {mentor}
            """,
            document_type="Mentor Session Booking",
            document_name=doc.name
        )

        frappe.publish_realtime(
            event="msgprint",
            message={
                "title":     "Session Rescheduled",
                "message":   f"Your session has been moved to {new_date} {new_from_time} – {new_to_time}",
                "indicator": "green"
            },
            user=student_email
        )

    return {
        "status":    "success",
        "message":   "Session rescheduled successfully",
        "old_date":  str(old_date),
        "old_from":  str(old_from),
        "old_to":    str(old_to),
        "new_date":  str(new_date),
        "new_from":  str(new_from_time),
        "new_to":    str(new_to_time),
    }


@frappe.whitelist(allow_guest=False)
def mark_session_completed(session_name):
    """
    Permission: WRITE on 'Mentor Session Booking'.
    Configured via Role Permission Manager — no hardcoded roles.

    Marks the session as Completed and sends a system notification + email
    to every enrolled student (1 for 1:1, all enrolled for Group/Workshop)
    inviting them to leave a review and rating.
    """
    # ----------------------------------------------------------
    # PERMISSION CHECK
    # ----------------------------------------------------------
    session_user = frappe.session.user

    if not frappe.has_permission("Mentor Session Booking", ptype="write", user=session_user):
        frappe.throw(
            _("You do not have permission to mark sessions as completed."),
            frappe.PermissionError
        )

    # ----------------------------------------------------------
    # Load and transition the booking
    # ----------------------------------------------------------
    doc = frappe.get_doc("Mentor Session Booking", session_name)

    if doc.status != "Scheduled":
        frappe.throw(_("Only Scheduled sessions can be marked as Completed."))

    doc.status = "Completed"
    doc.mentor_request_status = "Completed"
    doc.save(ignore_permissions=True)
    frappe.db.commit()

    # Update mentor stats — wrapped so a permission error doesn't block notifications
    try:
        _update_mentor_stats(doc.mentor)
    except Exception:
        frappe.log_error(frappe.get_traceback(), "mark_session_completed: _update_mentor_stats failed")

    # ----------------------------------------------------------
    # Notify student(s) using the same create_notification pattern
    # as accept_request — the proven working approach
    # ----------------------------------------------------------
    try:
        _send_session_completed_notifications(doc)
    except Exception:
        frappe.log_error(frappe.get_traceback(), "mark_session_completed: notification failed")

    return _("Session {0} marked as Completed.").format(session_name)


def _send_session_completed_notifications(doc):
    """
    Notify every student enrolled in the completed session using the same
    create_notification() call that accept_request uses — this is the proven
    working pattern in this codebase.

    - 1:1 Mentorship  → single student on doc.student
    - Group Session / Workshop → all students with a Completed booking for
      the same offering
    """
    # Resolve offering type
    offering_type = doc.get("offering_type")
    if not offering_type and doc.get("offering"):
        offering_type = frappe.db.get_value(
            "Mentor Offering", doc.offering, "offering_type"
        )

    # Resolve mentor display name
    mentor_display = (
        frappe.db.get_value("User", doc.mentor, "full_name")
        or doc.mentor
    )

    # Resolve session label
    session_label = (
        doc.get("topic")
        or (frappe.db.get_value("Mentor Offering", doc.offering, "title") if doc.get("offering") else None)
        or "Mentor Session"
    )

    notification_message = f"""
Your session "{session_label}" with mentor {mentor_display} has been marked as Completed.

We'd love to hear how it went! Please take a moment to add a review and rating for your mentor so other students can benefit from your experience.

Thank you for learning with us!
— The StridenEx Team
    """.strip()

    # Build the list of students to notify
    students_to_notify = []  # list of {student, booking_name}

    if offering_type in ("Group Session", "Workshop") and doc.get("offering"):
        # All students enrolled in this offering
        group_bookings = frappe.get_all(
            "Mentor Session Booking",
            filters={
                "offering": doc.offering,
                "status":   "Completed",
                "student":  ["is", "set"],
            },
            fields=["name", "student"],
            ignore_permissions=True,
        )
        seen = set()
        for bk in group_bookings:
            if bk.student and bk.student not in seen:
                seen.add(bk.student)
                students_to_notify.append({"student": bk.student, "booking_name": bk.name})
    else:
        # 1:1 — single student
        if doc.student:
            students_to_notify.append({"student": doc.student, "booking_name": doc.name})

    frappe.log_error(
        f"[SessionCompleted] booking={doc.name} offering_type={offering_type} "
        f"students={[e['student'] for e in students_to_notify]}",
        "Session Completed Debug"
    )

    for entry in students_to_notify:
        # Resolve the student's email — create_notification expects the user's
        # email (it resolves it to a User record internally)
        student_id = entry["student"]
        student_email = (
            frappe.db.get_value("Student", student_id, "email_id")
            or student_id
        )

        create_notification(
            user=student_email,
            subject="Your session is completed — add a review for your mentor!",
            message=notification_message,
            document_type="Mentor Session Booking",
            document_name=entry["booking_name"],
            ignore_permissions=True,
        )



@frappe.whitelist(allow_guest=False)
def submit_review(booking_name, rating, review, skill_highlights=None):
    """
    Submit a student review and rating for a completed session.
    
    Parameters:
        booking_name    - The Mentor Session Booking name (required)
        rating          - Numeric rating 1-5 (required)
        review          - Text review (required)
        skill_highlights - Optional. Comma-separated string OR JSON list of skills
                           the student found best (e.g. "Communication,Explanation with Examples")
    
    Permission: WRITE on 'Mentor Session Booking'.
    Configured via Role Permission Manager — no hardcoded roles.
    """
    import json

    # ----------------------------------------------------------
    # PERMISSION CHECK
    # ----------------------------------------------------------
    session_user = frappe.session.user

    if not frappe.has_permission("Mentor Session Booking", ptype="write", user=session_user):
        frappe.throw(
            _("You do not have permission to submit a review."),
            frappe.PermissionError
        )

    # ----------------------------------------------------------
    # Validate booking
    # ----------------------------------------------------------
    if not frappe.db.exists("Mentor Session Booking", booking_name):
        frappe.throw(_("Invalid Booking"))

    booking = frappe.get_doc("Mentor Session Booking", booking_name)

    if booking.status != "Completed":
        frappe.throw(_("Only completed sessions can be reviewed."))

    # Resolve student name from session user
    student_name = frappe.db.get_value(
        "Student",
        {"email_id": frappe.session.user},
        "name"
    )

    # ----------------------------------------------------------
    # Prevent duplicate reviews: one review per student per booking
    # ----------------------------------------------------------
    if student_name:
        already_reviewed = any(
            row.reviewed_by == student_name
            for row in (booking.review or [])
        )
        if already_reviewed:
            frappe.throw(_("You have already submitted a review for this session."))

    # ----------------------------------------------------------
    # Normalise skill_highlights — accept str OR list OR None
    # ----------------------------------------------------------
    normalized_skills = []
    if skill_highlights:
        if isinstance(skill_highlights, list):
            normalized_skills = [s.strip() for s in skill_highlights if s.strip()]
        elif isinstance(skill_highlights, str):
            # Try JSON first, fall back to comma-separated
            try:
                parsed = json.loads(skill_highlights)
                if isinstance(parsed, list):
                    normalized_skills = [s.strip() for s in parsed if str(s).strip()]
                else:
                    normalized_skills = [s.strip() for s in str(parsed).split(",") if s.strip()]
            except (json.JSONDecodeError, ValueError):
                normalized_skills = [s.strip() for s in skill_highlights.split(",") if s.strip()]

    skills_str = ",".join(normalized_skills) if normalized_skills else None

    # ----------------------------------------------------------
    # Append review row to child table
    # ----------------------------------------------------------
    booking.append("review", {
        "rating":           float(rating),
        "review_text":      review,
        "skill_highlights": skills_str,
        "reviewed_by":      student_name,
        "reviewed_on":      now_datetime()
    })

    # Set rating on the parent booking record as well
    booking.rating = float(rating)

    booking.save(ignore_permissions=True)
    frappe.db.commit()

    if booking.offering:
        offering = frappe.get_doc("Mentor Offering", booking.offering)
        offering.update_aggregates()

    # Also update the mentor's stats (includes skill highlights recomputation)
    _update_mentor_stats(booking.mentor)

    return {
        "success":          True,
        "skill_highlights": normalized_skills
    }


@frappe.whitelist(allow_guest=False)
def get_review_status(booking_name):
    """
    Returns whether the currently logged-in student has already reviewed
    the given booking, plus existing reviews (without PII) for display.

    Permission: READ on 'Mentor Session Booking'.
    """
    session_user = frappe.session.user

    if not frappe.has_permission("Mentor Session Booking", ptype="read", user=session_user):
        frappe.throw(
            _("You do not have permission to check review status."),
            frappe.PermissionError
        )

    if not frappe.db.exists("Mentor Session Booking", booking_name):
        frappe.throw(_("Invalid Booking"))

    booking = frappe.get_doc("Mentor Session Booking", booking_name)

    # Resolve student name for current user
    student_name = frappe.db.get_value(
        "Student",
        {"email_id": session_user},
        "name"
    )

    already_reviewed = False
    student_review = None

    reviews_out = []
    for row in (booking.review or []):
        import json as _json
        highlights = []
        if row.skill_highlights:
            highlights = [s.strip() for s in row.skill_highlights.split(",") if s.strip()]

        entry = {
            "rating":           row.rating,
            "review_text":      row.review_text,
            "skill_highlights": highlights,
            "reviewed_on":      str(row.reviewed_on) if row.reviewed_on else None,
        }
        reviews_out.append(entry)

        if student_name and row.reviewed_by == student_name:
            already_reviewed = True
            student_review = entry

    return {
        "booking_name":    booking_name,
        "status":          booking.status,
        "already_reviewed": already_reviewed,
        "student_review":   student_review,
        "total_reviews":   len(reviews_out),
        "reviews":         reviews_out,
    }


def _get_student_full_name(student_email):
    if not student_email:
        return ""
    # Try Student doctype first
    student_profile = frappe.db.get_value(
        "Student",
        {"email_id": student_email},
        ["first_name", "last_name"],
        as_dict=True,
    )
    if student_profile:
        full_name = " ".join(
            filter(None, [student_profile.get("first_name"),
                           student_profile.get("last_name")])
        ).strip()
        if full_name:
            return full_name

    # Try User doctype next
    user_full_name = frappe.db.get_value("User", student_email, "full_name")
    if user_full_name:
        return user_full_name

    return student_email


@frappe.whitelist(allow_guest=False)
def get_upcoming_sessions(mentor, limit=20):
    """
    Permission: READ on 'Mentor Session Booking'.
    Non-System-Manager users can only view their own mentor sessions (ownership check).
    Configured via Role Permission Manager — no hardcoded roles.
    """
    # ----------------------------------------------------------
    # PERMISSION CHECK
    # ----------------------------------------------------------
    session_user = frappe.session.user

    if not frappe.has_permission("Mentor Session Booking", ptype="read", user=session_user):
        frappe.throw(
            _("You do not have permission to access Mentor Session Booking."),
            frappe.PermissionError
        )

    # ----------------------------------------------------------
    # OWNERSHIP CHECK
    # Non-System-Manager can only view their own mentor's sessions.
    # ----------------------------------------------------------
    if "System Manager" not in frappe.get_roles(session_user):
        mentor_linked_to_user = frappe.db.get_value(
            "Mentor",
            {"email_id": session_user},
            ["name", "email_id"],
            as_dict=True,
        )

        if not mentor_linked_to_user:
            frappe.throw(
                _("No Mentor profile found for your account."),
                frappe.PermissionError
            )

        # The `mentor` param from the frontend can be either the doc name (email)
        # or the email_id. Compare case-insensitively against both to handle
        # newly onboarded mentors and any capitalisation differences.
        mentor_param_lower = (mentor or "").strip().lower()
        allowed = (
            mentor_param_lower == mentor_linked_to_user.name.lower()
            or mentor_param_lower == mentor_linked_to_user.email_id.lower()
        )

        if not allowed:
            frappe.throw(
                _("You are not permitted to view another mentor's sessions."),
                frappe.PermissionError
            )

    # ----------------------------------------------------------
    # Unchanged logic below
    # ----------------------------------------------------------

    sessions = frappe.get_all(
        "Mentor Session Booking",
        filters={
            "mentor": mentor,
            "status": ["in", ["Scheduled", "Accepted"]],
            "mentor_request_status": ["in", ["Accepted", "Pending"]],
            "session_date": [">=", today()],
        },
        fields=[
            "name", "mentor", "student", "topic", "session_date",
            "from_time", "to_time", "duration", "status", "meeting_link",
            "offering", "offering_type", "amount_paid", "mentor_request_status",
        ],
        order_by="session_date asc, from_time asc",
        limit_page_length=int(limit),
    )

    # ── Collapse Group Session / Workshop rows into one entry per offering ────
    # For 1:1 sessions, each booking is its own row (as before).
    # For Group/Workshop, N student bookings share the same slot → collapse to 1.
    collapsed = {}
    for s in sessions:
        if s.offering_type in ("Group Session", "Workshop"):
            key = (s.offering or s.name, str(s.session_date),
                   str(s.from_time), str(s.to_time))
            if key not in collapsed:
                entry = dict(s)
                entry["participant_count"] = 1
                entry["participants"] = [s.student]
                entry["student"] = None          # no single student for group
                entry["student_full_name"] = None
                collapsed[key] = entry
            else:
                collapsed[key]["participant_count"] += 1
                collapsed[key]["participants"].append(s.student)
        else:
            # 1:1 — resolve student name as before
            entry = dict(s)
            entry["student_full_name"] = _get_student_full_name(s.student)
            entry["participant_count"] = 1
            entry["participants"] = [s.student]
            collapsed[s.name] = entry

    # Resolve group session student names now that we have unique participants
    result = []
    for entry in collapsed.values():
        if entry.get("offering_type") in ("Group Session", "Workshop"):
            # Build offering title for display
            if entry.get("offering"):
                entry["offering_title"] = frappe.db.get_value(
                    "Mentor Offering", entry["offering"], "title"
                ) or ""
            else:
                entry["offering_title"] = entry.get("topic") or ""

            # Resolve participant names and join them for student_full_name
            participant_names = []
            for p in entry.get("participants", []):
                name = _get_student_full_name(p)
                if name:
                    participant_names.append(name)
            entry["student_full_name"] = ", ".join(participant_names) if participant_names else "No participants"

        result.append(entry)

    return result


@frappe.whitelist(allow_guest=False)
def get_session_history(mentor, from_date=None, to_date=None, limit=50):
    """
    Permission: READ on 'Mentor Session Booking'.
    Configured via Role Permission Manager — no hardcoded roles.
    """
    # ----------------------------------------------------------
    # PERMISSION CHECK
    # ----------------------------------------------------------
    session_user = frappe.session.user

    if not frappe.has_permission("Mentor Session Booking", ptype="read", user=session_user):
        frappe.throw(
            _("You do not have permission to access session history."),
            frappe.PermissionError
        )

    # ----------------------------------------------------------
    # Unchanged logic below
    # ----------------------------------------------------------
    filters = {"mentor": mentor, "status": ["in", ["Completed", "Cancelled"]]}
    if from_date and to_date:
        filters["session_date"] = ["between", [from_date, to_date]]

    return frappe.get_all(
        "Mentor Session Booking",
        filters=filters,
        fields=[
            "name", "student", "topic", "session_date",
            "from_time", "to_time", "duration", "status", "offering"
        ],
        order_by="session_date desc",
        limit_page_length=int(limit),
    )


@frappe.whitelist(allow_guest=False)
def get_weekly_booked_sessions(mentor, week_start_date=None):
    """
    Permission: READ on 'Mentor Session Booking'.
    Configured via Role Permission Manager — no hardcoded roles.
    """
    # ----------------------------------------------------------
    # PERMISSION CHECK
    # ----------------------------------------------------------
    session_user = frappe.session.user

    if not frappe.has_permission("Mentor Session Booking", ptype="read", user=session_user):
        frappe.throw(
            _("You do not have permission to access weekly sessions."),
            frappe.PermissionError
        )

    # ----------------------------------------------------------
    # Unchanged logic below
    # ----------------------------------------------------------
    start  = getdate(week_start_date)
    monday = start - datetime.timedelta(days=start.weekday())
    sunday = monday + datetime.timedelta(days=6)

    sessions = frappe.get_all(
        "Mentor Session Booking",
        filters={
            "mentor":       mentor,
            "session_date": ["between", [str(monday), str(sunday)]],
            "status":       "Scheduled",
        },
        fields=[
            "name", "student", "topic", "session_date",
            "from_time", "to_time", "duration", "status",
            "meeting_link", "offering", "offering_type"
        ],
        order_by="session_date asc, from_time asc",
    )

    # ── Collapse Group Session / Workshop rows into one entry per offering ────
    collapsed = {}
    for s in sessions:
        if s.offering_type in ("Group Session", "Workshop"):
            key = (s.offering or s.name, str(s.session_date),
                   str(s.from_time), str(s.to_time))
            if key not in collapsed:
                entry = dict(s)
                entry["participant_count"] = 1
                entry["participants"] = [s.student]
                entry["student"] = None
                entry["student_full_name"] = None
                if entry.get("offering"):
                    entry["offering_title"] = frappe.db.get_value(
                        "Mentor Offering", entry["offering"], "title"
                    ) or ""
                collapsed[key] = entry
            else:
                collapsed[key]["participant_count"] += 1
                collapsed[key]["participants"].append(s.student)
        else:
            entry = dict(s)
            entry["student_full_name"] = _get_student_full_name(s.student)
            entry["participant_count"] = 1
            entry["participants"] = [s.student]
            collapsed[s.name] = entry

    # Resolve group session student names now that we have unique participants
    for entry in collapsed.values():
        if entry.get("offering_type") in ("Group Session", "Workshop"):
            participant_names = []
            for p in entry.get("participants", []):
                name = _get_student_full_name(p)
                if name:
                    participant_names.append(name)
            entry["student_full_name"] = ", ".join(participant_names) if participant_names else "No participants"

    return list(collapsed.values())


@frappe.whitelist(allow_guest=False)
def get_monthly_booked_sessions(mentor, month_date=None):
    """
    Permission: READ on 'Mentor Session Booking'.
    Configured via Role Permission Manager — no hardcoded roles.
    """
    # ----------------------------------------------------------
    # PERMISSION CHECK
    # ----------------------------------------------------------
    session_user = frappe.session.user

    if not frappe.has_permission("Mentor Session Booking", ptype="read", user=session_user):
        frappe.throw(
            _("You do not have permission to access monthly sessions."),
            frappe.PermissionError
        )

    # ----------------------------------------------------------
    # Unchanged logic below
    # ----------------------------------------------------------
    if not month_date:
        month_date = nowdate()

    start        = getdate(month_date)
    first_day    = start.replace(day=1)
    last_day_num = calendar.monthrange(start.year, start.month)[1]
    last_day     = start.replace(day=last_day_num)

    sessions = frappe.get_all(
        "Mentor Session Booking",
        filters={
            "mentor":       mentor,
            "session_date": ["between", [str(first_day), str(last_day)]],
            "status":       ["in", ["Scheduled", "Completed"]],
        },
        fields=[
            "name", "student", "topic", "session_date",
            "from_time", "to_time", "duration", "status",
            "meeting_link", "offering"
        ],
        order_by="session_date asc, from_time asc",
    )

    for s in sessions:
        s["student_full_name"] = _get_student_full_name(s.student)

    return sessions


@frappe.whitelist(allow_guest=False)
def get_mentor_dashboard_stats(mentor=None):
    """
    Permission: READ on 'Mentor Session Booking'.
    Configured via Role Permission Manager — no hardcoded roles.
    """
    # ----------------------------------------------------------
    # PERMISSION CHECK
    # ----------------------------------------------------------
    session_user = frappe.session.user

    if not frappe.has_permission("Mentor Session Booking", ptype="read", user=session_user):
        frappe.throw(
            _("You do not have permission to access mentor dashboard stats."),
            frappe.PermissionError
        )

    # ----------------------------------------------------------
    # Unchanged logic below
    # ----------------------------------------------------------
    mentor = mentor or frappe.session.user

    if not mentor:
        return {"success": False, "message": "Mentor is required"}

    # Resolve the mentor ID from email/user session
    resolved_mentor = frappe.db.get_value("Mentor", {"email_id": mentor}, "name") or frappe.db.get_value("Mentor", mentor, "name")
    if resolved_mentor:
        mentor = resolved_mentor

    today     = getdate(nowdate())
    first_day = get_first_day(today)
    last_day  = get_last_day(today)

    total_students = frappe.db.sql("""
        SELECT COUNT(DISTINCT student) AS total_students
        FROM `tabMentor Session Booking`
        WHERE mentor = %(mentor)s
        AND status = 'Completed'
    """, {"mentor": mentor}, as_dict=True)[0].total_students or 0

    this_month_students = frappe.db.sql("""
        SELECT COUNT(DISTINCT student) AS total_students
        FROM `tabMentor Session Booking`
        WHERE mentor = %(mentor)s
        AND status = 'Completed'
        AND COALESCE(session_date, DATE(creation)) BETWEEN %(first_day)s AND %(last_day)s
    """, {"mentor": mentor, "first_day": first_day, "last_day": last_day}, as_dict=True)[0].total_students or 0

    sessions_this_month = frappe.db.sql("""
        SELECT COUNT(*) AS count
        FROM `tabMentor Session Booking`
        WHERE mentor = %(mentor)s
        AND status IN ('Scheduled', 'Completed')
        AND COALESCE(session_date, DATE(creation)) BETWEEN %(first_day)s AND %(last_day)s
    """, {"mentor": mentor, "first_day": first_day, "last_day": last_day}, as_dict=True)[0].count or 0

    sessions_completed = frappe.db.sql("""
        SELECT COUNT(*) AS count
        FROM `tabMentor Session Booking`
        WHERE mentor = %(mentor)s
        AND status = 'Completed'
        AND COALESCE(session_date, DATE(creation)) BETWEEN %(first_day)s AND %(last_day)s
    """, {"mentor": mentor, "first_day": first_day, "last_day": last_day}, as_dict=True)[0].count or 0

    upcoming_sessions = frappe.db.sql("""
        SELECT COUNT(*) AS count
        FROM `tabMentor Session Booking`
        WHERE mentor = %(mentor)s
        AND status = 'Scheduled'
        AND COALESCE(session_date, DATE(creation)) >= %(today)s
    """, {"mentor": mentor, "today": today}, as_dict=True)[0].count or 0

    five_star_reviews = frappe.db.sql("""
        SELECT COUNT(mor.name) AS total_reviews
        FROM `tabMentor Offering Review` mor
        INNER JOIN `tabMentor Session Booking` msb ON msb.name = mor.parent
        WHERE msb.mentor = %(mentor)s
        AND mor.rating = 5
        AND COALESCE(msb.session_date, DATE(msb.creation)) BETWEEN %(first_day)s AND %(last_day)s
    """, {"mentor": mentor, "first_day": first_day, "last_day": last_day}, as_dict=True)[0].total_reviews or 0

    skills_verified = frappe.db.count(
        "Skill Evidence",
        filters={
            "allocated_mentor":   mentor,
            "verification_status": "Verified",
            "modified":           ["between", [first_day, last_day]]
        }
    )

    session_rows = frappe.db.sql("""
        SELECT offering, offering_type, COALESCE(session_date, DATE(creation)) AS resolved_date, from_time, to_time
        FROM `tabMentor Session Booking`
        WHERE mentor = %(mentor)s
        AND status = 'Completed'
        AND COALESCE(session_date, DATE(creation)) BETWEEN %(first_day)s AND %(last_day)s
    """, {"mentor": mentor, "first_day": first_day, "last_day": last_day}, as_dict=True)

    total_seconds = 0
    seen_group_slots = set()

    for row in session_rows:
        if row.from_time and row.to_time:
            duration = max(time_diff_in_seconds(row.to_time, row.from_time), 0)
            if row.offering_type in ("Group Session", "Workshop"):
                slot_key = (row.offering, row.resolved_date, str(row.from_time), str(row.to_time))
                if slot_key not in seen_group_slots:
                    seen_group_slots.add(slot_key)
                    total_seconds += duration
            else:
                total_seconds += duration

    total_hours = round(total_seconds / 3600, 1)

    # ── Rating summary from child table reviews (Mentor Offering Review) ────────
    # All-time: avg rating + total review count across all completed sessions
    all_time_rating_row = frappe.db.sql("""
        SELECT
            ROUND(AVG(mor.rating), 1) AS avg_rating,
            COUNT(mor.name)           AS total_reviews
        FROM `tabMentor Offering Review` mor
        INNER JOIN `tabMentor Session Booking` msb ON msb.name = mor.parent
        WHERE msb.mentor  = %(mentor)s
        AND   msb.status  = 'Completed'
        AND   mor.rating IS NOT NULL
    """, {"mentor": mentor}, as_dict=True)

    all_time_avg_rating  = float(all_time_rating_row[0].avg_rating or 0) if all_time_rating_row else 0.0
    total_reviews_count  = int(all_time_rating_row[0].total_reviews or 0) if all_time_rating_row else 0

    # This-month avg rating
    month_rating_row = frappe.db.sql("""
        SELECT ROUND(AVG(mor.rating), 1) AS avg_rating
        FROM `tabMentor Offering Review` mor
        INNER JOIN `tabMentor Session Booking` msb ON msb.name = mor.parent
        WHERE msb.mentor  = %(mentor)s
        AND   msb.status  = 'Completed'
        AND   mor.rating IS NOT NULL
        AND   COALESCE(msb.session_date, DATE(msb.creation)) BETWEEN %(first_day)s AND %(last_day)s
    """, {"mentor": mentor, "first_day": first_day, "last_day": last_day}, as_dict=True)

    month_avg_rating = float(month_rating_row[0].avg_rating or 0) if month_rating_row else 0.0

    # 1–5 star distribution (all-time)
    star_dist_rows = frappe.db.sql("""
        SELECT
            FLOOR(mor.rating) AS star,
            COUNT(mor.name)   AS count
        FROM `tabMentor Offering Review` mor
        INNER JOIN `tabMentor Session Booking` msb ON msb.name = mor.parent
        WHERE msb.mentor  = %(mentor)s
        AND   msb.status  = 'Completed'
        AND   mor.rating IS NOT NULL
        GROUP BY FLOOR(mor.rating)
    """, {"mentor": mentor}, as_dict=True)

    rating_distribution = {str(i): 0 for i in range(1, 6)}
    for r in star_dist_rows:
        key = str(int(r.star or 0))
        if key in rating_distribution:
            rating_distribution[key] = int(r.count)
    # ────────────────────────────────────────────────────────────────────────────

    return {
        "success":                    True,
        "mentor":                     mentor,
        "total_students_mentored":    total_students,
        "this_month_mentored_students": this_month_students,
        "sessions_this_month":        sessions_this_month,
        "upcoming_sessions":          upcoming_sessions,
        "month_start":                str(first_day),
        "month_end":                  str(last_day),
        # ── Rating summary (sourced from Mentor Offering Review child table) ──
        "avg_rating":           all_time_avg_rating,
        "total_reviews":        total_reviews_count,
        "rating_distribution":  rating_distribution,
        # ─────────────────────────────────────────────────────────────────────
        "this_month": {
            "sessions_completed": sessions_completed,
            "five_star_reviews":  five_star_reviews,
            "avg_rating":         month_avg_rating,
            "skills_verified":    skills_verified,
            "hours_mentored":     f"{total_hours}h",
        }
    }


# ------------------------------------------------------------------
# Slot Generation
# ------------------------------------------------------------------

def _to_minutes(t):
    if isinstance(t, str):
        t = get_time(t)
    if isinstance(t, datetime.timedelta):
        return int(t.total_seconds()) // 60
    return t.hour * 60 + t.minute


def _from_minutes(m):
    h  = m // 60
    mn = m % 60
    return f"{h:02}:{mn:02}:00"


def _get_free_windows(avail_from, avail_to, booked_intervals):
    overlapping = []
    for (bs, be) in booked_intervals:
        cs = max(bs, avail_from)
        ce = min(be, avail_to)
        if cs < ce:
            overlapping.append((cs, ce))

    overlapping.sort(key=lambda x: x[0])
    merged = []
    for interval in overlapping:
        if merged and interval[0] <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], interval[1]))
        else:
            merged.append(list(interval))

    free   = []
    cursor = avail_from
    for (bs, be) in merged:
        if cursor < bs:
            free.append((cursor, bs))
        cursor = max(cursor, be)
    if cursor < avail_to:
        free.append((cursor, avail_to))

    return free


@frappe.whitelist(allow_guest=False)
def get_booked_sessions(student_email=None):
    """
    Permission: READ on 'Mentor Session Booking'.
    Configured via Role Permission Manager — no hardcoded roles.
    """
    # ----------------------------------------------------------
    # PERMISSION CHECK
    # ----------------------------------------------------------
    session_user = frappe.session.user

    if not frappe.has_permission("Mentor Session Booking", ptype="read", user=session_user):
        frappe.throw(
            _("You do not have permission to view booked sessions."),
            frappe.PermissionError
        )

    # ----------------------------------------------------------
    # Unchanged logic below
    # ----------------------------------------------------------
    if not student_email:
        frappe.throw("Student email is required")

    return frappe.get_all(
        "Mentor Session Booking",
        filters={
            "student":               student_email,
            "status":                ["not in", ["Cancelled", "Rejected"]],
            "mentor_request_status": ["not in", ["Declined"]]
        },
        fields=[
            "name", "mentor", "offering", "offering_type", "session_date",
            "session_type", "status", "priority", "topic",
            "from_time", "to_time", "duration"
        ]
    )


def split_into_duration_slots(from_time, to_time, duration_minutes, booked_intervals=None):
    duration_minutes = int(duration_minutes or 60)
    booked_intervals = booked_intervals or []

    avail_from = _to_minutes(from_time)
    avail_to   = _to_minutes(to_time)

    booked_min = [
        (_to_minutes(b[0]), _to_minutes(b[1]))
        for b in booked_intervals
    ]

    free_windows = _get_free_windows(avail_from, avail_to, booked_min)

    slots = []
    for (win_start, win_end) in free_windows:
        if (win_end - win_start) < duration_minutes:
            continue
        cursor = win_start
        while cursor + duration_minutes <= win_end:
            slots.append({
                "from_time": _from_minutes(cursor),
                "to_time":   _from_minutes(cursor + duration_minutes),
            })
            cursor += duration_minutes

    return slots


@frappe.whitelist()
def split_into_hour_slots(from_time, to_time):
    return split_into_duration_slots(from_time, to_time, duration_minutes=60)


@frappe.whitelist(allow_guest=False)
def create_group_session_booking(offering, batch_name, student):
    """
    Permission: CREATE on 'Mentor Session Booking'.
    Configured via Role Permission Manager — no hardcoded roles.
    """
    # ----------------------------------------------------------
    # PERMISSION CHECK
    # ----------------------------------------------------------
    session_user = frappe.session.user

    if not frappe.has_permission("Mentor Session Booking", ptype="create", user=session_user):
        frappe.throw(
            _("You do not have permission to create a group session booking."),
            frappe.PermissionError
        )

    # ----------------------------------------------------------
    # Unchanged logic below
    # ----------------------------------------------------------
    offering_doc = frappe.get_doc("Mentor Offering", offering)
    batch_doc    = frappe.get_doc("LMS Batch", batch_name)

    doc = frappe.get_doc({
        "doctype":       "Mentor Session Booking",
        "offering_type": "Group Session",
        "offering":      offering,
        "mentor":        offering_doc.mentor,
        "student":       student,
        "lms_batch":     batch_name,
        "session_date":  batch_doc.start_date,
        "from_time":     "00:00:00",
        "to_time":       "00:00:00",
        "topic":         batch_doc.title,
        "status":        "Scheduled",
    })
    doc.insert(ignore_permissions=True)
    frappe.db.commit()

    return {"session_name": doc.name}


@frappe.whitelist(allow_guest=False)
def create_session_request(mentor, student, offering, topic, requested_date,
                           requested_time=None, student_message=None):
    """
    Permission: CREATE on 'Mentor Session Booking'.
    Configured via Role Permission Manager — no hardcoded roles.
    """
    # ----------------------------------------------------------
    # PERMISSION CHECK
    # ----------------------------------------------------------
    session_user = frappe.session.user

    if not frappe.has_permission("Mentor Session Booking", ptype="create", user=session_user):
        frappe.throw(_("Permission denied."), frappe.PermissionError)

    # ----------------------------------------------------------
    # Unchanged logic below
    # ----------------------------------------------------------
    if mentor == student:
        frappe.throw(_("Student and Mentor cannot be the same user."))

    if getdate(requested_date) < getdate(nowdate()):
        frappe.throw(_("Preferred date cannot be in the past."))

    fee = frappe.db.get_value("Mentor Offering", offering, "price_per_session") or 0

    doc = frappe.get_doc({
        "doctype":               "Mentor Session Booking",
        "mentor":                mentor,
        "student":               student,
        "offering":              offering,
        "topic":                 topic,
        "requested_date":        requested_date,
        "requested_time":        requested_time,
        "student_message":       student_message,
        "amount_paid":           fee,
        "status":                "Pending",
        "mentor_request_status": "Pending",
    })
    doc.insert(ignore_permissions=True)
    frappe.db.commit()

    return {"booking_name": doc.name}


@frappe.whitelist(allow_guest=False)
def get_pending_requests(mentor, limit=None):
    """
    Permission: READ on 'Mentor Session Booking'.
    Configured via Role Permission Manager — no hardcoded roles.
    """
    # ----------------------------------------------------------
    # PERMISSION CHECK
    # ----------------------------------------------------------
    session_user = frappe.session.user

    if not frappe.has_permission("Mentor Session Booking", ptype="read", user=session_user):
        frappe.throw(
            _("You do not have permission to view pending requests."),
            frappe.PermissionError
        )

    # ----------------------------------------------------------
    # Unchanged logic below
    # ----------------------------------------------------------
    filters = {"mentor": mentor, "mentor_request_status": "Pending"}

    total_pending_count = frappe.db.count("Mentor Session Booking", filters=filters)

    query_args = {
        "doctype": "Mentor Session Booking",
        "filters": filters,
        "fields":  [
            "name", "student", "offering", "topic", "session_date",
            "from_time", "to_time", "session_type", "priority",
            "student_message", "amount_paid",
        ],
    }

    if limit:
        query_args["limit_page_length"] = int(limit)

    rows = frappe.get_all(**query_args)

    for r in rows:
        r["student_name"]   = frappe.db.get_value("User", r.student, "full_name") or r.student
        r["offering_title"] = (
            frappe.db.get_value("Mentor Offering", r.offering, "title") if r.offering else ""
        )

    return {"total_pending_count": total_pending_count, "records": rows}


@frappe.whitelist(allow_guest=False)
def get_request_counts(mentor):
    """
    Permission: READ on 'Mentor Session Booking'.
    Configured via Role Permission Manager — no hardcoded roles.
    """
    # ----------------------------------------------------------
    # PERMISSION CHECK
    # ----------------------------------------------------------
    session_user = frappe.session.user

    if not frappe.has_permission("Mentor Session Booking", ptype="read", user=session_user):
        frappe.throw(
            _("You do not have permission to view request counts."),
            frappe.PermissionError
        )

    # ----------------------------------------------------------
    # Unchanged logic below
    # ----------------------------------------------------------
    pending = frappe.db.count(
        "Mentor Session Booking",
        {"mentor": mentor, "mentor_request_status": "Pending"}
    )

    approved = frappe.db.sql("""
        SELECT COUNT(*) FROM `tabMentor Session Booking`
        WHERE mentor = %s
          AND mentor_request_status = 'Accepted'
          AND MONTH(modified) = MONTH(CURDATE())
          AND YEAR(modified)  = YEAR(CURDATE())
    """, mentor)[0][0]

    svr_pending = 0
    if frappe.db.exists("DocType", "Skill Verification Request"):
        svr_pending = frappe.db.count(
            "Skill Verification Request",
            {"mentor": mentor, "status": "Pending"}
        )

    return {
        "pending":             pending,
        "svr_pending":         svr_pending,
        "approved_this_month": int(approved),
    }


@frappe.whitelist(allow_guest=False)
def decline_request(booking_name, notes=None):
    """
    Permission: WRITE on 'Mentor Session Booking'.
    Configured via Role Permission Manager — no hardcoded roles.
    """
    # ----------------------------------------------------------
    # PERMISSION CHECK
    # ----------------------------------------------------------
    session_user = frappe.session.user

    if not frappe.has_permission("Mentor Session Booking", ptype="write", user=session_user):
        frappe.throw(
            _("You do not have permission to decline session requests."),
            frappe.PermissionError
        )

    # ----------------------------------------------------------
    # Unchanged logic below
    # ----------------------------------------------------------
    doc = frappe.get_doc("Mentor Session Booking", booking_name)

    if doc.mentor_request_status != "Pending":
        frappe.throw(_("Only Pending requests can be declined."))

    doc.mentor_request_status = "Declined"
    doc.status                = "Cancelled"
    if notes:
        doc.notes = notes
    doc.save(ignore_permissions=True)
    frappe.db.commit()

    return {"status": "Declined"}


@frappe.whitelist(allow_guest=False)
def suggest_alt_time(booking_name, alt_date, alt_time, notes=None):
    """
    Permission: WRITE on 'Mentor Session Booking'.
    Configured via Role Permission Manager — no hardcoded roles.
    """
    # ----------------------------------------------------------
    # PERMISSION CHECK
    # ----------------------------------------------------------
    session_user = frappe.session.user

    if not frappe.has_permission("Mentor Session Booking", ptype="write", user=session_user):
        frappe.throw(
            _("You do not have permission to suggest alternate times."),
            frappe.PermissionError
        )

    # ----------------------------------------------------------
    # Unchanged logic below
    # ----------------------------------------------------------
    doc = frappe.get_doc("Mentor Session Booking", booking_name)

    if doc.mentor_request_status != "Pending":
        frappe.throw(_("Only Pending requests can have an alt time suggested."))

    doc.mentor_request_status = "Suggested Alt Time"
    doc.status                = "Pending"
    doc.alt_date              = alt_date
    doc.alt_time              = alt_time
    if notes:
        doc.notes = notes
    doc.save(ignore_permissions=True)

    student_email = frappe.db.get_value("Student", doc.student, "email_id")

    if student_email:

        create_notification(
            user=student_email,
            subject="Alternate Time Suggested",
            message=f"""
                Your mentor has suggested an alternate session time.

                Date: {alt_date}
                Time: {alt_time}

                Please review the suggested slot.
            """,
            document_type="Mentor Session Booking",
            document_name=doc.name
        )

        if frappe.db.exists("User", student_email):
            notification = frappe.get_doc({
                "doctype": "Notification Log",
                "subject": "Alternate Time Suggested",
                "for_user": student_email,
                "type": "Alert",
                "document_type": "Mentor Session Booking",
                "document_name": doc.name,
                "email_content": f"""
                    Your mentor has suggested an alternate session time.

                    Date: {alt_date}
                    Time: {alt_time}
                """
            })
            notification.insert(ignore_permissions=True)

            frappe.publish_realtime(
                event="msgprint",
                message={
                    "title": "Alternate Time Suggested",
                    "message": f"Mentor suggested {alt_date} {alt_time}",
                    "indicator": "orange"
                },
                user=student_email
            )

    frappe.db.commit()

    return {"status": "Suggested Alt Time"}


@frappe.whitelist(allow_guest=False)
def student_confirm_alt_time(booking_name):
    """
    Permission: WRITE on 'Mentor Session Booking'.
    Configured via Role Permission Manager — no hardcoded roles.
    """
    # ----------------------------------------------------------
    # PERMISSION CHECK
    # ----------------------------------------------------------
    session_user = frappe.session.user

    if not frappe.has_permission("Mentor Session Booking", ptype="write", user=session_user):
        frappe.throw(
            _("You do not have permission to confirm alternate times."),
            frappe.PermissionError
        )

    # ----------------------------------------------------------
    # Unchanged logic below
    # ----------------------------------------------------------
    doc = frappe.get_doc("Mentor Session Booking", booking_name)

    if doc.mentor_request_status != "Suggested Alt Time":
        frappe.throw(_("No alternate time to confirm."))

    doc.requested_date        = doc.alt_date
    doc.requested_time        = doc.alt_time
    doc.alt_date              = None
    doc.alt_time              = None
    doc.mentor_request_status = "Pending"
    doc.status                = "Accepted"
    doc.save(ignore_permissions=True)
    frappe.db.commit()

    create_notification(
        user=doc.mentor,
        subject="Alternate Time Confirmed",
        message=f"""
            Student has confirmed the alternate session time.

            Student: {doc.student}
            Date: {doc.requested_date}
            Time: {doc.requested_time}
        """,
        document_type="Mentor Session Booking",
        document_name=doc.name
    )

    return {"status": "Pending"}


# ------------------------------------------------------------------
# Skill Highlight Aggregation Helpers
# ------------------------------------------------------------------

def _compute_mentor_skill_highlights(mentor, top_n=10):
    """
    Aggregate skill_highlights across ALL completed session reviews for a mentor.
    Returns a JSON-encoded list of {skill, count} dicts sorted by count desc,
    limited to top_n skills.

    Example output (stored on Mentor.skill_highlights):
        '[{"skill": "Communication", "count": 14}, {"skill": "Explanation with Examples", "count": 9}]'
    """
    import json
    from collections import Counter

    # Pull all skill_highlights values for this mentor's completed sessions
    rows = frappe.db.sql("""
        SELECT mor.skill_highlights
        FROM `tabMentor Offering Review` mor
        INNER JOIN `tabMentor Session Booking` msb ON msb.name = mor.parent
        WHERE msb.mentor = %(mentor)s
          AND msb.status = 'Completed'
          AND mor.skill_highlights IS NOT NULL
          AND mor.skill_highlights != ''
    """, {"mentor": mentor}, as_dict=True)

    counter = Counter()
    for row in rows:
        skills_raw = row.get("skill_highlights") or ""
        for skill in skills_raw.split(","):
            skill = skill.strip()
            if skill:
                counter[skill] += 1

    top_skills = [
        {"skill": skill, "count": cnt}
        for skill, cnt in counter.most_common(top_n)
    ]

    return json.dumps(top_skills, ensure_ascii=False)


@frappe.whitelist(allow_guest=False)
def get_mentor_skill_highlights(mentor, top_n=10):
    """
    Returns the top skill highlights for a mentor based on aggregated
    student reviews. Used to display skill badges on mentor cards.

    Parameters:
        mentor  - Mentor email / document name (required)
        top_n   - Maximum number of skills to return (default 10)

    Permission: READ on 'Mentor Session Booking'.

    Response:
        {
            "mentor": "...",
            "skill_highlights": [
                {"skill": "Communication", "count": 14},
                {"skill": "Explanation with Examples", "count": 9},
                ...
            ]
        }
    """
    import json
    from collections import Counter

    session_user = frappe.session.user
    if not frappe.has_permission("Mentor Session Booking", ptype="read", user=session_user):
        frappe.throw(
            _("You do not have permission to view mentor highlights."),
            frappe.PermissionError
        )

    if not mentor:
        frappe.throw(_("Mentor is required."))

    top_n = int(top_n or 10)

    # First try reading from cached value on Mentor doctype (fast path)
    cached_json = frappe.db.get_value("Mentor", mentor, "skill_highlights")
    if cached_json:
        try:
            highlights = json.loads(cached_json)
            return {
                "mentor":           mentor,
                "skill_highlights": highlights[:top_n],
                "source":           "cache",
            }
        except (json.JSONDecodeError, ValueError):
            pass  # Fall through to live computation

    # Live computation (slow path — also refreshes cache)
    rows = frappe.db.sql("""
        SELECT mor.skill_highlights
        FROM `tabMentor Offering Review` mor
        INNER JOIN `tabMentor Session Booking` msb ON msb.name = mor.parent
        WHERE msb.mentor = %(mentor)s
          AND msb.status = 'Completed'
          AND mor.skill_highlights IS NOT NULL
          AND mor.skill_highlights != ''
    """, {"mentor": mentor}, as_dict=True)

    counter = Counter()
    for row in rows:
        skills_raw = row.get("skill_highlights") or ""
        for skill in skills_raw.split(","):
            skill = skill.strip()
            if skill:
                counter[skill] += 1

    highlights = [
        {"skill": skill, "count": cnt}
        for skill, cnt in counter.most_common(top_n)
    ]

    # Persist to cache on Mentor doc
    try:
        frappe.db.set_value("Mentor", mentor, "skill_highlights",
                            json.dumps(highlights, ensure_ascii=False),
                            update_modified=False)
        frappe.db.commit()
    except Exception:
        pass  # Non-critical; just return the live data

    return {
        "mentor":           mentor,
        "skill_highlights": highlights,
        "source":           "live",
    }


@frappe.whitelist(allow_guest=False)
def _update_mentor_stats(mentor):

    """
    Permission: WRITE on 'Mentor'.
    Configured via Role Permission Manager — no hardcoded roles.
    """
    # ----------------------------------------------------------
    # PERMISSION CHECK
    # ----------------------------------------------------------
    session_user = frappe.session.user
    
    if not frappe.has_permission("Mentor", ptype="write", user=session_user):
        frappe.throw(
            _("You do not have permission to update mentor stats."),
            frappe.PermissionError
        )

    # ----------------------------------------------------------
    # Unchanged logic below
    # ----------------------------------------------------------
    if not mentor:
        return {"success": False, "message": "Mentor is required"}

    MENTOR_DOCTYPE = "Mentor"

    if not frappe.db.exists(MENTOR_DOCTYPE, mentor):
        mentor_doc_name = frappe.db.get_value(
            MENTOR_DOCTYPE, {"mentor": mentor}, "name"
        )
        if not mentor_doc_name:
            return {"success": False, "message": "Mentor profile not found"}
    else:
        mentor_doc_name = mentor

    session_rows = frappe.db.sql("""
        SELECT offering, offering_type, COALESCE(session_date, DATE(creation)) AS resolved_date, from_time, to_time, amount_paid
        FROM `tabMentor Session Booking`
        WHERE mentor = %(mentor)s
        AND status = 'Completed'
    """, {"mentor": mentor}, as_dict=True)

    total_sessions = len(session_rows)
    total_earnings = sum(float(r.amount_paid or 0) for r in session_rows)

    # Calculate avg rating from the child table (Mentor Offering Review) —
    # the parent booking's `rating` field is unreliable; child reviews are
    # the actual student-submitted ratings.
    rating_agg = frappe.db.sql("""
        SELECT ROUND(AVG(mor.rating), 1) AS avg_rating
        FROM `tabMentor Offering Review` mor
        INNER JOIN `tabMentor Session Booking` msb ON msb.name = mor.parent
        WHERE msb.mentor = %(mentor)s
        AND   msb.status = 'Completed'
        AND   mor.rating IS NOT NULL
    """, {"mentor": mentor}, as_dict=True)
    avg_rating = float(rating_agg[0].avg_rating or 0) if rating_agg else 0.0

    total_seconds = 0
    seen_group_slots = set()

    for row in session_rows:
        if row.from_time and row.to_time:
            duration = max(time_diff_in_seconds(row.to_time, row.from_time), 0)
            if row.offering_type in ("Group Session", "Workshop"):
                slot_key = (row.offering, row.resolved_date, str(row.from_time), str(row.to_time))
                if slot_key not in seen_group_slots:
                    seen_group_slots.add(slot_key)
                    total_seconds += duration
            else:
                total_seconds += duration

    total_hours = round(total_seconds / 3600, 2)

    frappe.db.set_value(
        MENTOR_DOCTYPE,
        mentor_doc_name,
        {
            "total_sessions": total_sessions,
            "total_hours":    total_hours,
            "total_earnings": total_earnings,
            "avg_rating":     avg_rating,
            "skill_highlights": _compute_mentor_skill_highlights(mentor),
        },
        # update_modified=False
    )
    frappe.db.commit()

    return {
        "success":        True,
        "mentor":         mentor_doc_name,
        "total_sessions": total_sessions,
        "total_hours":    total_hours,
        "total_earnings": total_earnings,
        "avg_rating":     avg_rating
    }


@frappe.whitelist(allow_guest=False)
def update_status(booking_name, status):
    """
    Permission: WRITE on 'Mentor Session Booking'.
    Configured via Role Permission Manager — no hardcoded roles.
    """
    # ----------------------------------------------------------
    # PERMISSION CHECK
    # ----------------------------------------------------------
    session_user = frappe.session.user

    if not frappe.has_permission("Mentor Session Booking", ptype="write", user=session_user):
        frappe.throw(
            _("You do not have permission to update session status."),
            frappe.PermissionError
        )

    # ----------------------------------------------------------
    # Unchanged logic below
    # ----------------------------------------------------------
    doc = frappe.get_doc("Mentor Session Booking", booking_name)

    if doc.docstatus != 1:
        frappe.throw(_("Only submitted bookings can be updated."))

    if status not in ["Completed", "Cancelled"]:
        frappe.throw(_("Invalid status value."))

    doc.db_set("status", status)

    if doc.offering:
        offering = frappe.get_doc("Mentor Offering", doc.offering)
        offering.update_aggregates()

    _update_mentor_stats(doc.mentor)

    return {"success": True}


@frappe.whitelist(allow_guest=False)
def cancel_session(session_name):
    """
    Permission: WRITE on 'Mentor Session Booking'.
    Configured via Role Permission Manager — no hardcoded roles.
    """
    # ----------------------------------------------------------
    # PERMISSION CHECK
    # ----------------------------------------------------------
    session_user = frappe.session.user

    if not frappe.has_permission("Mentor Session Booking", ptype="write", user=session_user):
        frappe.throw(
            _("You do not have permission to cancel sessions."),
            frappe.PermissionError
        )

    # ----------------------------------------------------------
    # Unchanged logic below
    # ----------------------------------------------------------
    doc = frappe.get_doc("Mentor Session Booking", session_name)

    if doc.status != "Scheduled":
        frappe.throw(_("Only Scheduled sessions can be cancelled."))

    doc.status = "Cancelled"
    doc.save()
    frappe.db.commit()

    _update_mentor_stats(doc.mentor)

    return _("Session {0} cancelled.").format(session_name)


@frappe.whitelist(allow_guest=False)
def accept_request(booking_name, from_time, to_time, session_date=None):
    """
    Permission: WRITE on 'Mentor Session Booking'.
    Configured via Role Permission Manager — no hardcoded roles.
    """
    # ----------------------------------------------------------
    # PERMISSION CHECK
    # ----------------------------------------------------------
    session_user = frappe.session.user

    if not frappe.has_permission("Mentor Session Booking", ptype="write", user=session_user):
        frappe.throw(
            _("You do not have permission to accept session requests."),
            frappe.PermissionError
        )

    # ----------------------------------------------------------
    # Unchanged logic below
    # ----------------------------------------------------------
    doc = frappe.get_doc("Mentor Session Booking", booking_name)

    if doc.mentor_request_status != "Pending":
        frappe.throw(_("Only Pending requests can be accepted."))

    doc.session_date          = session_date or doc.session_date or doc.requested_date
    doc.from_time             = from_time
    doc.to_time               = to_time
    doc.mentor_request_status = "Accepted"
    doc.status                = "Scheduled"

    doc.save(ignore_permissions=True)

    create_notification(
        user=doc.student,
        subject="Session Accepted",
        message=f"""
            Your mentor session request has been accepted.

            Date: {doc.session_date}
            Time: {doc.from_time} - {doc.to_time}
        """,
        document_type="Mentor Session Booking",
        document_name=doc.name
    )

    frappe.db.commit()

    return {"booking_name": doc.name}


@frappe.whitelist(allow_guest=False)
def get_student_upcoming_sessions(student, limit=20):
    """
    Permission: READ on 'Mentor Session Booking'.
    Configured via Role Permission Manager — no hardcoded roles.
    """
    # ----------------------------------------------------------
    # PERMISSION CHECK
    # ----------------------------------------------------------
    session_user = frappe.session.user

    if not frappe.has_permission("Mentor Session Booking", ptype="read", user=session_user):
        frappe.throw(
            _("You do not have permission to view upcoming sessions."),
            frappe.PermissionError
        )

    # ----------------------------------------------------------
    # Unchanged logic below
    # ----------------------------------------------------------
    sessions = frappe.get_all(
        "Mentor Session Booking",
        filters={
            "student":               student,
            "status":                "Scheduled",
            "session_date":          [">=", nowdate()],
            "mentor_request_status": ["in", ["Accepted", "", None]],
        },
        fields=[
            "name", "mentor", "topic", "session_date",
            "from_time", "to_time", "duration", "status",
            "meeting_link", "offering", "offering_type",
            "lms_batch", "amount_paid"
        ],
        order_by="session_date asc, from_time asc",
        limit_page_length=int(limit),
    )

    for s in sessions:
        s["mentor"] = frappe.db.get_value("User", s.mentor, "full_name") or s.mentor
        if s.offering:
            s["offering_title"] = frappe.db.get_value("Mentor Offering", s.offering, "title") or ""

    return sessions


@frappe.whitelist(allow_guest=False)
def get_student_pending_requests(student):
    """
    Permission: READ on 'Mentor Session Booking'.
    Configured via Role Permission Manager — no hardcoded roles.
    """
    # ----------------------------------------------------------
    # PERMISSION CHECK
    # ----------------------------------------------------------
    session_user = frappe.session.user

    if not frappe.has_permission("Mentor Session Booking", ptype="write", user=session_user):
        frappe.throw(
            _("You do not have permission to view pending requests."),
            frappe.PermissionError
        )

    # ----------------------------------------------------------
    # Unchanged logic below
    # ----------------------------------------------------------
    rows = frappe.get_all(
        "Mentor Session Booking",
        filters={
            "student":               student,
            "mentor_request_status": ["in", ["Pending", "Suggested Alt Time"]],
        },
        fields=[
            "name", "mentor", "topic", "requested_date",
            "requested_time", "mentor_request_status",
            "priority", "alt_date", "alt_time", "notes",
            "offering", "amount_paid"
        ],
        order_by="requested_date asc",
    )

    for r in rows:
        r["mentor"] = frappe.db.get_value("User", r.mentor, "full_name") or r.mentor

    return rows


@frappe.whitelist(allow_guest=False)
def get_student_session_history(student, from_date=None, to_date=None, limit=50):
    """
    Permission: READ on 'Mentor Session Booking'.
    Configured via Role Permission Manager — no hardcoded roles.
    """
    # ----------------------------------------------------------
    # PERMISSION CHECK
    # ----------------------------------------------------------
    session_user = frappe.session.user

    if not frappe.has_permission("Mentor Session Booking", ptype="read", user=session_user):
        frappe.throw(
            _("You do not have permission to view session history."),
            frappe.PermissionError
        )

    # ----------------------------------------------------------
    # Unchanged logic below
    # ----------------------------------------------------------
    filters = {
        "student": student,
        "status":  ["in", ["Completed", "Cancelled"]],
    }
    if from_date and to_date:
        filters["session_date"] = ["between", [from_date, to_date]]

    sessions = frappe.get_all(
        "Mentor Session Booking",
        filters=filters,
        fields=[
            "name", "mentor", "topic", "session_date",
            "from_time", "to_time", "duration", "status",
            "offering", "offering_type", "rating", "amount_paid"
        ],
        order_by="session_date desc",
        limit_page_length=int(limit),
    )

    for s in sessions:
        s["mentor"] = frappe.db.get_value("User", s.mentor, "full_name") or s.mentor

    return sessions


@frappe.whitelist(allow_guest=False)
def save_session_notes(student, session_name, notes=None, shared_with_student=None):
    """
    Permission: WRITE on 'Mentor Session Booking'.
    Configured via Role Permission Manager — no hardcoded roles.
    """
    try:
        # ----------------------------------------------------------
        # PERMISSION CHECK
        # ----------------------------------------------------------
        session_user = frappe.session.user

        if not frappe.has_permission("Mentor Session Booking", ptype="write", user=session_user):
            return {
                "status":  "error",
                "message": _("You do not have permission to save session notes.")
            }

        # ----------------------------------------------------------
        # Unchanged logic below
        # ----------------------------------------------------------
        if not student:
            return {"status": "error", "message": "student is required"}

        if not session_name:
            return {"status": "error", "message": "session_name is required"}

        session_doc = frappe.get_doc("Mentor Session Booking", session_name)

        if session_doc.student != student:
            return {"status": "error", "message": "This session does not belong to this student"}

        is_edit = bool(session_doc.notes)

        if notes is not None:
            session_doc.notes = notes

        if shared_with_student is not None:
            session_doc.shared_with_student = shared_with_student

        session_doc.save(ignore_permissions=True)
        frappe.db.commit()

        success_message = (
            "Session note updated successfully" if is_edit else "Session note added successfully"
        )

        return {
            "status":  "success",
            "message": success_message,
            "is_edit": is_edit,
            "data": {
                "student":            session_doc.student,
                "session_name":       session_doc.name,
                "notes":              session_doc.notes,
                "shared_with_student": session_doc.shared_with_student
            }
        }

    except Exception as e:
        frappe.db.rollback()
        frappe.log_error(frappe.get_traceback(), "Save Session Notes Error")
        return {"status": "error", "message": str(e)}


@frappe.whitelist(allow_guest=False)
def get_session_note(student, session_name):
    """
    Permission: READ on 'Mentor Session Booking'.
    Configured via Role Permission Manager — no hardcoded roles.
    """
    try:
        # ----------------------------------------------------------
        # PERMISSION CHECK
        # ----------------------------------------------------------
        session_user = frappe.session.user

        if not frappe.has_permission("Mentor Session Booking", ptype="read", user=session_user):
            return {
                "status":  "error",
                "message": _("You do not have permission to view session notes.")
            }

        # ----------------------------------------------------------
        # Unchanged logic below
        # ----------------------------------------------------------
        if not student:
            return {"status": "error", "message": "student is required"}

        if not session_name:
            return {"status": "error", "message": "session_name is required"}

        session_doc = frappe.get_doc("Mentor Session Booking", session_name)

        if session_doc.student != student:
            return {"status": "error", "message": "This session does not belong to this student"}

        return {
            "status":  "success",
            "message": "Session note fetched successfully",
            "data": {
                "student":             session_doc.student,
                "session_name":        session_doc.name,
                "notes":               session_doc.notes,
                "shared_with_student": session_doc.shared_with_student
            }
        }

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Get Session Note Error")
        return {"status": "error", "message": str(e)}


@frappe.whitelist(allow_guest=False)
def email_to_student(student, session_name, subject, message):
    """
    Permission: READ on 'Mentor Session Booking' (mentor is sending, so read is sufficient).
    Configured via Role Permission Manager — no hardcoded roles.
    """
    try:
        # ----------------------------------------------------------
        # PERMISSION CHECK
        # ----------------------------------------------------------
        session_user = frappe.session.user

        if not frappe.has_permission("Mentor Session Booking", ptype="read", user=session_user):
            return {
                "status":  "error",
                "message": _("You do not have permission to email students.")
            }

        # ----------------------------------------------------------
        # Unchanged logic below
        # ----------------------------------------------------------
        session_doc = frappe.get_doc("Mentor Session Booking", session_name)

        if session_doc.student != student:
            return {"status": "error", "message": "Invalid student"}

        student_email = session_doc.student
        mentor_email  = session_doc.mentor

        if not student_email:
            return {"status": "error", "message": "Student email not found"}

        if not mentor_email:
            return {"status": "error", "message": "Mentor email not found"}

        current_user = frappe.session.user
        frappe.set_user("Administrator")

        try:
            email_queue = frappe.sendmail(
                recipients=[student_email],
                sender=mentor_email,
                reply_to=mentor_email,
                subject=subject,
                message=message,
                now=False
            )

            frappe.db.commit()

            if email_queue and hasattr(email_queue, "name"):
                send_now(email_queue.name)
            else:
                queued = frappe.db.get_value(
                    "Email Queue",
                    {"status": "Not Sent", "recipients": student_email},
                    "name",
                    order_by="creation desc"
                )
                if queued:
                    send_now(queued)
                else:
                    return {"status": "error", "message": "Email queued but could not find record to send"}

            if email_queue and hasattr(email_queue, "name"):
                status = frappe.db.get_value("Email Queue", email_queue.name, "status")
                if status != "Sent":
                    error_msg = frappe.db.get_value("Email Queue", email_queue.name, "error")
                    return {"status": "error", "message": f"Email failed. SMTP Error: {error_msg}"}

        finally:
            frappe.set_user(current_user)

        return {"status": "success", "message": f"Email sent successfully to {student_email}"}

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Email To Student Error")
        return {"status": "error", "message": str(e)}