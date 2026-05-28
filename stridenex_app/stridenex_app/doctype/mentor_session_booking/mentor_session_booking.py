# Copyright (c) 2024, Your Company and contributors
# For license information, please see license.txt

# ── Add this import at the top ───────────────────────────────────────────────
# from stridenex_app.api_stridenex_app.app_utils import (
#     add_student_to_batch,
#     remove_student_from_batch,
#     get_or_create_course_enrollment,

from frappe.email.doctype.email_queue.email_queue import send_now
import frappe
from frappe.utils import now_datetime
from frappe.model.document import Document
from frappe import _
from frappe.utils import getdate, nowdate, get_time, add_days
import datetime
import calendar
from frappe.utils import get_url_to_form

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

    # ------------------------------------------------------------------
    # Lifecycle Hooks
    # ------------------------------------------------------------------

    def autoname(self):
        from frappe.model.naming import make_autoname
        # Use different prefix based on booking type
        self.name = make_autoname("MSB-.YYYY.-.#####")

    def validate(self):
        self.fetch_mentor_from_offering()
        self.fetch_amount_from_offering()
        self.validate_not_self_booking()
        
        is_request_stage = (
            self.status in ("Pending", "Suggested Alt Time")
            or not self.from_time
            or not self.to_time
        )

        if is_request_stage:
            # Only validate date not past for the requested date
            if self.session_date and getdate(self.session_date) < getdate(nowdate()):
                frappe.throw(_("Preferred date cannot be in the past."))
            return

        # ── Full slot validations for confirmed bookings ───────────────
        if self.status == "Cancelled":
            return

        if self.offering_type not in ("Group Session", "Workshop"):
            self.validate_date_not_past()
            self.validate_time_range()
            self.calculate_duration()
            self.validate_mentor_availability()
            self.validate_mentor_not_blocked()
            self.check_double_booking()

        


# ── Update MentorSessionBooking class — replace on_submit and on_cancel ────────

    def on_submit(self):
        if self.status == "Scheduled":
            self.db_set("status", "Scheduled")
        if self.offering:
            self.update_offering_aggregates()
        self._refresh_seat_count()

        # LMS enrollment for group sessions
        if self.offering_type == "Group Session" and self.lms_batch and self.student:
            lms_course = frappe.db.get_value(
                "Mentor Offering", self.offering, "lms_course"
            )
            if lms_course:
                from stridenex_app.api_stridenex_app.app_utils import (
                    get_or_create_course_enrollment,
                )
                enrollment_name = get_or_create_course_enrollment(
                    lms_course, self.student, batch=self.lms_batch
                )
                self.db_set("lms_enrollment", enrollment_name)

    def on_cancel(self):
        self.db_set("status", "Cancelled")
        if self.offering:
            self.update_offering_aggregates()
        self._refresh_seat_count()

        # Remove from LMS batch on cancellation
        if self.offering_type == "Group Session" and self.lms_batch and self.student:
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

        # ── Update mentor stats on cancel ─────────────────────────────
        _update_mentor_stats(self.mentor)
        
    def _refresh_seat_count(self):
        """After booking save/cancel, update the seat counter on parent slot/workshop."""
        if self.offering_type == "Group Session" and self.group_slot:
            slot = frappe.get_doc("Group Session Slot", self.group_slot)
            slot.update_seat_count()
        elif self.offering_type == "Workshop" and self.workshop:
            ws = frappe.get_doc("Workshop", self.workshop)
            ws.update_seat_count()
    # ------------------------------------------------------------------
    # Offering-related helpers
    # ------------------------------------------------------------------
    def _fetch_session_type_from_offering(self):
        """Auto-fill session_type from offering category."""
        if self.offering and not self.session_type:
            cat = frappe.db.get_value("Mentor Offering", self.offering, "category")
            if cat:
                self.session_type = cat

    def fetch_mentor_from_offering(self):
        """Auto-fill mentor from the linked Mentor Offering."""
        if self.offering and not self.mentor:
            self.mentor = frappe.db.get_value("Mentor Offering", self.offering, "mentor")

    def fetch_amount_from_offering(self):
        """Auto-fill amount_paid from offering price if not set."""
        if self.offering and not self.amount_paid:
            price = frappe.db.get_value("Mentor Offering", self.offering, "price_per_session")
            if price:
                self.amount_paid = price

    def update_offering_aggregates(self):
        """Recalculate aggregates on the linked Mentor Offering."""
        if self.offering:
            offering = frappe.get_doc("Mentor Offering", self.offering)
            offering.update_aggregates()

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

        # Get offering type
        offering_type = frappe.db.get_value(
            "Mentor Offering",
            self.offering,
            "offering_type"
        ) if self.offering else None

        # ✅ Only validate for 1:1 Session
        if offering_type != "1:1 Session":
            return

        # ✅ Validation for 1:1
        if self.from_time and self.to_time:
            if self.from_time >= self.to_time:
                frappe.throw(_("From Time must be earlier than To Time."))
    

    def calculate_duration(self):
        if self.from_time and self.to_time:
            start = get_time(self.from_time)
            end   = get_time(self.to_time)
            self.duration = (end.hour * 60 + end.minute) - (start.hour * 60 + start.minute)

    def validate_mentor_availability(self):

        # ✅ Skip for non 1:1 sessions
        if not self.offering:
            return

        offering_type = frappe.db.get_value(
            "Mentor Offering",
            self.offering,
            "offering_type"
        )

        if offering_type != "1:1 Session":
            return

        # ✅ Continue only for 1:1 Session
        day_name = getdate(self.session_date).strftime("%A").lower()

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

            # ✅ CASE 1: Same schedule
            if avail.schedule_type == "Each Day Same Schedule":
                for row in (doc.days_multi or []):
                    if (row.day or "").strip().lower() == day_name:

                        if get_time(doc.from_time) <= self_from and get_time(doc.to_time) >= self_to:
                            fits = True
                            break

            # ✅ CASE 2: Different schedule
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

## ------------------------------------------------------------------
# Notification + Email Helper
# ------------------------------------------------------------------
@frappe.whitelist(allow_guest=True)
def create_notification(
    user,
    subject,
    message,
    document_type=None,
    document_name=None
):

    if not user:
        return

    # ---------------------------------------------------------
    # Resolve User
    # ---------------------------------------------------------
    frappe.log_error(user)
    user = frappe.db.get_value(
        "User",
        {"email": user},
        "name"
    )

    # fallback if email itself is User.name
    if not user:
        user = frappe.db.get_value(
            "User",
            user,
            "name"
        )

    if not user:
        frappe.log_error(
            f"User not found: {user}",
            "NOTIFICATION ERROR"
        )
        return

    # ---------------------------------------------------------
    # EMAIL
    # ---------------------------------------------------------

    try:
        frappe.sendmail(
            recipients=[user],
            subject=subject,
            message=message,
            now=True
        )

    except Exception:
        frappe.log_error(
            frappe.get_traceback(),
            "EMAIL ERROR"
        )

    # ---------------------------------------------------------
    # NOTIFICATION LOG
    # ---------------------------------------------------------

    try:

        from_user = frappe.session.user

        if not from_user or from_user == "Guest":
            from_user = "Administrator"

        if not frappe.db.exists("User", from_user):
            from_user = "Administrator"

        notification = frappe.get_doc({
            "doctype": "Notification Log",
            "subject": subject,
            "for_user": user,
            "from_user": from_user,
            "type": "Alert",
            "document_type": document_type,
            "document_name": document_name,
            "email_content": message,
            "read": 0
        })

        notification.insert(ignore_permissions=True)

        frappe.db.commit()

        frappe.publish_realtime(
            event="notification",
            message={"user": user},
            user=user
        )

    except Exception:
        frappe.log_error(
            frappe.get_traceback(),
            "NOTIFICATION ERROR"
        )


# Existing helper
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
# Slot Calendar API
# ------------------------------------------------------------------


@frappe.whitelist(allow_guest=True)
def get_slot_calendar(mentor, from_date=None, to_date=None, offering=None):
    
    if not from_date and not to_date:
        from_date = nowdate()
        to_date = add_days(from_date, 6)
        
    if not mentor or not from_date or not to_date:
        frappe.throw(_("mentor, from_date, and to_date are required"))

    # ── Resolve slot duration ────────────────────────────────────────
    duration_minutes = 60
    if offering:
        mins = frappe.db.get_value("Mentor Offering", offering, "duration_minutes")
        if mins:
            duration_minutes = int(mins)

    start = getdate(from_date)
    end   = getdate(to_date)

    # ── 1. Availability map ──────────────────────────────────────────
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
                    "to_time":   _time_to_str(doc.to_time),
                })
        else:
            for row in (doc.daily_schedule or []):
                key = (row.day or "").strip().lower()
                avail_by_day.setdefault(key, []).append({
                    "from_time": _time_to_str(row.from_time),
                    "to_time":   _time_to_str(row.to_time),
                })

    # ── 2. Blocked slots ─────────────────────────────────────────────
    blocked_by_date = {}
    for b in frappe.get_all(
        "Mentor Blocked Time",
        filters={"mentor": mentor, "date": ["between", [from_date, to_date]]},
        fields=["date", "from_time", "to_time", "reason"]
    ):
        blocked_by_date.setdefault(str(b.date), []).append({
            "from_time": _time_to_str(b.from_time),
            "to_time":   _time_to_str(b.to_time),
            "reason":    b.reason or ""
        })

    # ── 3. Booked slots ──────────────────────────────────────────────
    booked_by_date = {}
    for b in frappe.get_all(
        "Mentor Session Booking",
        filters={
            "mentor":       mentor,
            "session_date": ["between", [from_date, to_date]],
            "status":       ["in", ["Scheduled", "Completed"]],
        },
        fields=["session_date", "from_time", "to_time", "student", "name", "topic"]
    ):
        booked_by_date.setdefault(str(b.session_date), []).append({
            "from_time":    _time_to_str(b.from_time),
            "to_time":      _time_to_str(b.to_time),
            "session_name": b.name,
            "student":      b.student,
            "topic":        b.topic,
        })

    # ── 4. Build calendar ────────────────────────────────────────────
    calendar = {}
    current  = start

    while current <= end:
        date_str     = str(current)
        day_key      = current.strftime("%A").lower()
        raw_windows  = avail_by_day.get(day_key, [])
        day_bookings = booked_by_date.get(date_str, [])
        day_blocks   = blocked_by_date.get(date_str, [])

        # All occupied intervals (booked + blocked) for free-window calc
        occupied_intervals = (
            [(b["from_time"], b["to_time"]) for b in day_bookings] +
            [(b["from_time"], b["to_time"]) for b in day_blocks]
        )

        day_result = []

        for window in raw_windows:
            win_from_min = _to_minutes(window["from_time"])
            win_to_min   = _to_minutes(window["to_time"])

            # ── A. Collect occupied chips that fall inside this window ──
            # These are shown as booked/blocked (non-clickable)
            occupied_chips = []

            for bk in day_bookings:
                bk_from = _to_minutes(bk["from_time"])
                bk_to   = _to_minutes(bk["to_time"])
                # Must overlap with this availability window
                if bk_from < win_to_min and bk_to > win_from_min:
                    # Clamp to window boundaries
                    chip_from = max(bk_from, win_from_min)
                    chip_to   = min(bk_to,   win_to_min)
                    occupied_chips.append({
                        "from_time":    _from_minutes(chip_from),
                        "to_time":      _from_minutes(chip_to),
                        "status":       "booked",
                        "session_name": bk["session_name"],
                        "student":      bk["student"],
                        "topic":        bk["topic"],
                        "reason":       "",
                    })

            for bl in day_blocks:
                bl_from = _to_minutes(bl["from_time"])
                bl_to   = _to_minutes(bl["to_time"])
                if bl_from < win_to_min and bl_to > win_from_min:
                    chip_from = max(bl_from, win_from_min)
                    chip_to   = min(bl_to,   win_to_min)
                    occupied_chips.append({
                        "from_time":    _from_minutes(chip_from),
                        "to_time":      _from_minutes(chip_to),
                        "status":       "blocked",
                        "session_name": None,
                        "student":      None,
                        "topic":        None,
                        "reason":       bl["reason"],
                    })

            # ── B. Free slots (skipping occupied intervals) ─────────────
            free_slots = split_into_duration_slots(
                window["from_time"],
                window["to_time"],
                duration_minutes=duration_minutes,
                booked_intervals=occupied_intervals,
            )
            for slot in free_slots:
                slot["status"]       = "available"
                slot["session_name"] = None
                slot["student"]      = None
                slot["topic"]        = None
                slot["reason"]       = ""

            # ── C. Merge and sort all chips by start time ───────────────
            all_chips = free_slots + occupied_chips
            all_chips.sort(key=lambda s: _to_minutes(s["from_time"]))
            day_result.extend(all_chips)

        calendar[date_str] = day_result
        current += datetime.timedelta(days=1)

    return calendar


@frappe.whitelist(allow_guest=True)
def book_slot(mentor, student, session_date, from_time, to_time, topic, offering=None):
    """Create a new Mentor Session Booking."""

    if not frappe.has_permission("Mentor Session Booking", "create"):
        frappe.throw(_("You do not have permission to book a session."), frappe.PermissionError)

    doc = frappe.get_doc({
        "doctype":      "Mentor Session Booking",
        "offering":     offering,
        "mentor":       mentor,
        "student":      student,
        "session_date": session_date,
        "from_time":    from_time,
        "to_time":      to_time,
        "topic":        topic,
        "status":       "Pending",   # ✅ FIXED (not Scheduled)
    })

    doc.insert(ignore_permissions=False)
    frappe.db.commit()
    
    # ---------------------------------------------------
    # Notify Mentor
    # ---------------------------------------------------

    create_notification(
        user=mentor,
        subject="New Session Booking",
        message=f"""
            A new mentor session has been booked.

            Student: {student}
            Date: {session_date}
            Time: {from_time} - {to_time}
            Topic: {topic}
        """,
        document_type="Mentor Session Booking",
        document_name=doc.name
    )

    return {"session_name": doc.name}
@frappe.whitelist()
def reschedule_session(
    session_name,
    mentor,
    student,
    new_date,
    new_from_time,
    new_to_time
):


    doc = frappe.get_doc(
        "Mentor Session Booking",
        session_name
    )

    if doc.status != "Scheduled":
        frappe.throw(
            _("Only Scheduled sessions can be rescheduled.")
        )


    old_date = doc.session_date
    old_from = doc.from_time
    old_to = doc.to_time


    doc.session_date = new_date
    doc.from_time = new_from_time
    doc.to_time = new_to_time

    doc.mentor_request_status = "Suggested Alt Time"

    doc.save(ignore_permissions=True)

    student_email = frappe.db.get_value(
        "Student",
        student,
        "email_id"
    )

    if not student_email:
        frappe.throw(_("Student email not found."))


    frappe.errprint(f"Student DocType: {student}")
    frappe.errprint(f"Student Email: {student_email}")


    session_link = get_url_to_form(
        "Mentor Session Booking",
        doc.name
    )

    subject = "Mentor Session Rescheduled"

    # ---------------------------------------------------
    # EMAIL MESSAGE
    # ---------------------------------------------------

    message = f"""
        <p>Hello Student,</p>

        <p>Your mentor session has been rescheduled.</p>

        <h4>Old Slot</h4>

        <p>
            {old_date}<br>
            {old_from} - {old_to}
        </p>

        <h4>New Slot</h4>

        <p>
            {new_date}<br>
            {new_from_time} - {new_to_time}
        </p>

        <p>Mentor: {mentor}</p>

        <p>
            <a href="{session_link}">
                View Session
            </a>
        </p>

        <p>Thank You</p>
    """


    # ---------------------------------------------------
    # CREATE NOTIFICATION
    # ---------------------------------------------------

    create_notification(
        user=student_email,
        subject="Session Rescheduled",
        message=f"""
            Your mentor session has been rescheduled.

            New Slot:
            {new_date}
            {new_from_time} - {new_to_time}
        """,
        document_type="Mentor Session Booking",
        document_name=doc.name
    )

    # ---------------------------------------------------
    # NOTIFICATION LOG
    # ---------------------------------------------------

    if frappe.db.exists("User", student_email):

        notification = frappe.get_doc({
            "doctype": "Notification Log",
            "subject": "Session Rescheduled",
            "for_user": student_email,
            "type": "Alert",
            "document_type": "Mentor Session Booking",
            "document_name": doc.name,
            "email_content": f"""
                Your mentor session has been rescheduled.

                New Slot:
                {new_date}
                {new_from_time} - {new_to_time}
            """
        })

        notification.insert(ignore_permissions=True)

        # ---------------------------------------------------
        # REALTIME POPUP
        # ---------------------------------------------------

        frappe.publish_realtime(
            event="msgprint",
            message={
                "title": "Session Rescheduled",
                "message": f"""
                    Your session moved to
                    {new_date}
                    {new_from_time} - {new_to_time}
                """,
                "indicator": "green"
            },
            user=student_email
        )

    frappe.db.commit()

    # ---------------------------------------------------
    # RETURN
    # ---------------------------------------------------

    return {
        "status": "success",
        "message": "Session rescheduled successfully",
        "student_email": student_email
    }   

@frappe.whitelist()
def mark_session_completed(session_name):
    doc = frappe.get_doc("Mentor Session Booking", session_name)

    if doc.status != "Scheduled":
        frappe.throw(_("Only Scheduled sessions can be marked as Completed."))

    doc.status = "Completed"
    doc.save()
    frappe.db.commit()

    # ── Update mentor aggregate stats ─────────────────────────────────
    _update_mentor_stats(doc.mentor)

    return _("Session {0} marked as Completed.").format(session_name)


# ------------------------------------------------------------------
# Offering-specific APIs  (previously in mentor_offering_booking.py)
# ------------------------------------------------------------------

@frappe.whitelist()
def submit_review(booking_name, rating, review, reviewed_by = frappe.session.user):

    if not frappe.db.exists("Mentor Session Booking", booking_name):
        frappe.throw(_("Invalid Booking"))

    booking = frappe.get_doc("Mentor Session Booking", booking_name)

    if booking.status != "Completed":
        frappe.throw(_("Only completed sessions can be reviewed."))

    # Add child table row
    booking.append("review", {
        "rating": float(rating),
        "review_text": review,
        "reviewed_by": reviewed_by,
        "reviewed_on": now_datetime()
    })

    booking.save(ignore_permissions=True)
    frappe.db.commit()

    # Refresh aggregates
    if booking.offering:
        offering = frappe.get_doc("Mentor Offering", booking.offering)
        offering.update_aggregates()

    return {"success": True}

@frappe.whitelist(allow_guest=True)
def get_upcoming_sessions(mentor, limit=20):

    from frappe.utils import nowdate

    sessions = frappe.get_all(
        "Mentor Session Booking",
        filters={
            "mentor": mentor,
            "status": ["in", ["Scheduled", "Accepted"]],
            "mentor_request_status": ["in", ["Accepted", "Pending"]],
            # "session_date": [">=", nowdate()]
        },
        fields=[
            "name",
            "mentor",
            "student",
            "topic",
            "session_date",
            "from_time",
            "to_time",
            "duration",
            "status",
            "meeting_link",
            "offering",
            "offering_type",
            "amount_paid",
            "mentor_request_status"
        ],
        order_by="session_date asc, from_time asc",
        limit_page_length=int(limit),
    )

    # ---------------------------------------------------------
    # Add Student Full Name
    # ---------------------------------------------------------
    for s in sessions:

        student_profile = frappe.db.get_value(
            "Student",
            {"email_id": s.student},
            ["first_name", "last_name"],
            as_dict=True
        ) or {}

        full_name = " ".join(
            filter(
                None,
                [
                    student_profile.get("first_name"),
                    student_profile.get("last_name")
                ]
            )
        ).strip()

        s["student_full_name"] = full_name or s.student

    return sessions


@frappe.whitelist(allow_guest=True)
def get_session_history(mentor, from_date=None, to_date=None, limit=50):
    filters = {"mentor": mentor, "status": ["in", ["Completed", "Cancelled"]]}
    if from_date and to_date:
        filters["session_date"] = ["between", [from_date, to_date]]
    return frappe.get_all(
        "Mentor Session Booking",
        filters=filters,
        fields=["name", "student", "topic", "session_date", "from_time",
                "to_time", "duration", "status", "offering"],
        order_by="session_date desc",
        limit_page_length=int(limit),
    )




@frappe.whitelist()
def get_weekly_booked_sessions(mentor, week_start_date=None):
    start  = getdate(week_start_date)
    monday = start - datetime.timedelta(days=start.weekday())
    sunday = monday + datetime.timedelta(days=6)
    sessions = frappe.get_all(
        "Mentor Session Booking",
        filters={
            "mentor": mentor,
            "session_date": ["between", [str(monday), str(sunday)]],
            "status": ["in", ["Scheduled", "Completed"]],
        },
        fields=["name", "student", "topic", "session_date", "from_time",
                "to_time", "duration", "status", "meeting_link", "offering"],
        order_by="session_date asc, from_time asc",
    )
    for s in sessions:
        s["student_full_name"] = frappe.db.get_value("User", s.student, "full_name") or s.student
    return sessions


@frappe.whitelist()
def get_monthly_booked_sessions(mentor, month_date=None):

    # Use current date if not provided
    if not month_date:
        month_date = nowdate()

    start = getdate(month_date)

    # First day of month
    first_day = start.replace(day=1)

    # Last day of month
    last_day_num = calendar.monthrange(start.year, start.month)[1]
    last_day = start.replace(day=last_day_num)

    sessions = frappe.get_all(
        "Mentor Session Booking",
        filters={
            "mentor": mentor,
            "session_date": ["between", [str(first_day), str(last_day)]],
            "status": ["in", ["Scheduled", "Completed"]],
        },
        fields=[
            "name",
            "student",
            "topic",
            "session_date",
            "from_time",
            "to_time",
            "duration",
            "status",
            "meeting_link",
            "offering",
        ],
        order_by="session_date asc, from_time asc",
    )

    for s in sessions:
        s["student_full_name"] = (
            frappe.db.get_value("User", s.student, "full_name")
            or s.student
        )

    return sessions



@frappe.whitelist()
def get_mentor_dashboard_stats(mentor=None):

    mentor = mentor or frappe.session.user

    if not mentor:
        return {
            "success": False,
            "message": "Mentor is required"
        }

    # ---------------------------------------------------------
    # Current Month Dates
    # ---------------------------------------------------------
    today = getdate(nowdate())

    first_day = get_first_day(today)
    last_day  = get_last_day(today)

    # ---------------------------------------------------------
    # Total Students Mentored
    # ---------------------------------------------------------
    total_students = frappe.db.sql("""
        SELECT COUNT(DISTINCT student) AS total_students
        FROM `tabMentor Session Booking`
        WHERE mentor = %(mentor)s
        AND mentor_request_status = 'Completed'
    """, {
        "mentor": mentor
    }, as_dict=True)[0].total_students or 0

    # ---------------------------------------------------------
    # This Month Students Mentored
    # ---------------------------------------------------------
    this_month_students = frappe.db.sql("""
        SELECT COUNT(DISTINCT student) AS total_students
        FROM `tabMentor Session Booking`
        WHERE mentor = %(mentor)s
        AND mentor_request_status = 'Completed'
        AND session_date BETWEEN %(first_day)s AND %(last_day)s
    """, {
        "mentor": mentor,
        "first_day": first_day,
        "last_day": last_day
    }, as_dict=True)[0].total_students or 0

    # ---------------------------------------------------------
    # Sessions This Month
    # ---------------------------------------------------------
    sessions_this_month = frappe.db.count(
        "Mentor Session Booking",
        filters={
            "mentor": mentor,
            "mentor_request_status": [
                "in",
                ["Scheduled", "Completed"]
            ],
            "session_date": [
                "between",
                [first_day, last_day]
            ]
        }
    )

    # ---------------------------------------------------------
    # Sessions Completed This Month
    # ---------------------------------------------------------
    sessions_completed = frappe.db.count(
        "Mentor Session Booking",
        filters={
            "mentor": mentor,
            "mentor_request_status": "Completed",
            "session_date": [
                "between",
                [first_day, last_day]
            ]
        }
    )

    # ---------------------------------------------------------
    # Upcoming Sessions
    # ---------------------------------------------------------
    upcoming_sessions = frappe.db.count(
        "Mentor Session Booking",
        filters={
            "mentor": mentor,
            "mentor_request_status": "Scheduled",
            "session_date": [">=", today]
        }
    )

    # ---------------------------------------------------------
    # 5 Star Reviews
    # ---------------------------------------------------------
    five_star_reviews = frappe.db.sql("""
        SELECT COUNT(mor.name) AS total_reviews
        FROM `tabMentor Offering Review` mor
        INNER JOIN `tabMentor Session Booking` msb
            ON msb.name = mor.parent
        WHERE
            msb.mentor = %(mentor)s
            AND mor.rating = 5
            AND msb.session_date BETWEEN %(first_day)s AND %(last_day)s
    """, {
        "mentor": mentor,
        "first_day": first_day,
        "last_day": last_day
    }, as_dict=True)[0].total_reviews or 0
    
    
    # # ---------------------------------------------------------
    # # Notes Shared
    # # ---------------------------------------------------------
    # notes_shared = frappe.db.count(
    #     "Mentor Notes",
    #     filters={
    #         "mentor": mentor,
    #         "creation": [
    #             "between",
    #             [first_day, last_day]
    #         ]
    #     }
    # )

    # ---------------------------------------------------------
    # Skills Verified
    # ---------------------------------------------------------
    skills_verified = frappe.db.count(
        "Skill Evidence",
        filters={
            "allocated_mentor": mentor,
            "verification_status": "Verified",
            "modified": [
                "between",
                [first_day, last_day]
            ]
        }
    )

    # ---------------------------------------------------------
    # Hours Mentored
    # ---------------------------------------------------------
    session_rows = frappe.get_all(
        "Mentor Session Booking",
        filters={
            "mentor": mentor,
            "mentor_request_status": "Completed",
            "session_date": [
                "between",
                [first_day, last_day]
            ]
        },
        fields=["from_time", "to_time"]
    )

    total_minutes = 0

    for row in session_rows:

        if row.from_time and row.to_time:

            start_minutes = (
                row.from_time.hour * 60
                + row.from_time.minute
            )

            end_minutes = (
                row.to_time.hour * 60
                + row.to_time.minute
            )

            total_minutes += max(
                end_minutes - start_minutes,
                0
            )

    total_hours = round(total_minutes / 60, 1)

 
    # ---------------------------------------------------------
    # Final Response
    # ---------------------------------------------------------
    return {
        "success": True,
        "mentor": mentor,

        "total_students_mentored": total_students,

        "this_month_mentored_students": this_month_students,

        "sessions_this_month": sessions_this_month,

        "upcoming_sessions": upcoming_sessions,

        "month_start": str(first_day),

        "month_end": str(last_day),

        "this_month": {
            "sessions_completed": sessions_completed,
            "five_star_reviews": five_star_reviews,
            # "notes_shared": notes_shared,
            "skills_verified": skills_verified,
            "hours_mentored": f"{total_hours}h",
            # "profile_views": profile_views
        }
    }    
# ─────────────────────────────────────────────────────────────────────────────
# Slot Generation  (replaces split_into_hour_slots)
# ─────────────────────────────────────────────────────────────────────────────

def _to_minutes(t):
    """Convert time object or HH:MM:SS string → total minutes from midnight."""
    if isinstance(t, str):
        t = get_time(t)
    if isinstance(t, datetime.timedelta):
        return int(t.total_seconds()) // 60
    return t.hour * 60 + t.minute


def _from_minutes(m):
    """Convert total minutes from midnight → HH:MM:SS string."""
    h = m // 60
    mn = m % 60
    return f"{h:02}:{mn:02}:00"


def _get_free_windows(avail_from, avail_to, booked_intervals):
    """
    Given one availability window (avail_from → avail_to, in minutes)
    and a list of booked intervals [(start_min, end_min), …],
    return a list of free sub-windows [(start_min, end_min), …].
    Booked intervals that fall outside the window are ignored.
    """
    # Only keep bookings that actually overlap with this window
    overlapping = []
    for (bs, be) in booked_intervals:
        # Clamp to availability window
        cs = max(bs, avail_from)
        ce = min(be, avail_to)
        if cs < ce:
            overlapping.append((cs, ce))

    # Sort and merge overlapping/adjacent bookings
    overlapping.sort(key=lambda x: x[0])
    merged = []
    for interval in overlapping:
        if merged and interval[0] <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], interval[1]))
        else:
            merged.append(list(interval))

    # Build free windows by filling gaps
    free = []
    cursor = avail_from
    for (bs, be) in merged:
        if cursor < bs:
            free.append((cursor, bs))
        cursor = max(cursor, be)
    if cursor < avail_to:
        free.append((cursor, avail_to))

    return free


@frappe.whitelist(allow_guest=True)
def get_booked_sessions(student_email=None):
    if not student_email:
        frappe.throw("Student email is required")

    sessions = frappe.get_all(
        "Mentor Session Booking",
        filters={"student": student_email, "status": ["in", ["Pending", "Scheduled", "Accepted"]], "mentor_request_status": ["not in", ["Declined"]]},
        fields=["name", "mentor","offering_type", "session_date","session_date", "session_type", "status", "priority", "topic", "from_time", "to_time", "duration"]
    )

    return sessions

def split_into_duration_slots(from_time, to_time, duration_minutes, booked_intervals=None):
    """
    Split an availability window into bookable slots of `duration_minutes`,
    skipping over already-booked intervals (free-window approach).

    Args:
        from_time         (str):  "HH:MM:SS" — window start
        to_time           (str):  "HH:MM:SS" — window end
        duration_minutes  (int):  slot length in minutes (e.g. 60, 90, 120)
        booked_intervals  (list): [(from_str, to_str), …] already-booked ranges
                                  inside this window (optional)

    Returns:
        list of {"from_time": "HH:MM:SS", "to_time": "HH:MM:SS"}
    """
    duration_minutes = int(duration_minutes or 60)
    booked_intervals = booked_intervals or []

    avail_from = _to_minutes(from_time)
    avail_to   = _to_minutes(to_time)

    # Convert booked interval strings → minute tuples
    booked_min = [
        (_to_minutes(b[0]), _to_minutes(b[1]))
        for b in booked_intervals
    ]

    # Get free sub-windows within this availability block
    free_windows = _get_free_windows(avail_from, avail_to, booked_min)

    slots = []
    for (win_start, win_end) in free_windows:
        window_len = win_end - win_start
        if window_len < duration_minutes:
            # Window too small for even one slot — skip
            continue

        cursor = win_start
        while cursor + duration_minutes <= win_end:
            slots.append({
                "from_time": _from_minutes(cursor),
                "to_time":   _from_minutes(cursor + duration_minutes),
            })
            cursor += duration_minutes

    return slots


# Keep old name as a thin wrapper so nothing else breaks
@frappe.whitelist()
def split_into_hour_slots(from_time, to_time):
    return split_into_duration_slots(from_time, to_time, duration_minutes=60)

# ── New whitelisted API — add at module level (outside class) ────────────────

@frappe.whitelist(allow_guest=True)
def create_group_session_booking(offering, batch_name, student):
    """
    Called from JS after enroll_student_in_batch succeeds.
    Creates the Mentor Session Booking record for a Group Session.
    The LMS enrollment is already done; this just records the booking.
    """
    offering_doc = frappe.get_doc("Mentor Offering", offering)
    batch_doc    = frappe.get_doc("LMS Batch", batch_name)

    doc = frappe.get_doc({
        "doctype":       "Mentor Session Booking",
        "offering_type": "Group Session",
        "offering":      offering,
        "mentor":        offering_doc.mentor,
        "student":       student,
        "lms_batch":     batch_name,
        # Use batch start_date as session_date
        "session_date":  batch_doc.start_date,
        "from_time":     "00:00:00",
        "to_time":       "00:00:00",
        "topic":         batch_doc.title,
        "status":        "Scheduled",
    })
    doc.insert(ignore_permissions=True)
    frappe.db.commit()

    return {"session_name": doc.name}

@frappe.whitelist()
def create_session_request(mentor, student, offering, topic,
                           requested_date, requested_time=None,
                           student_message=None):
    """
    Student submits a session request.
    Creates a Mentor Session Booking in 'Pending' request state
    (no from_time/to_time yet — mentor sets those when accepting).
    """
    if not frappe.has_permission("Mentor Session Booking", "create"):
        frappe.throw(_("Permission denied."), frappe.PermissionError)

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
        # No session_date / from_time / to_time yet
        "status":                "Pending",          # will update on accept
        "mentor_request_status": "Pending",
    })
    doc.insert(ignore_permissions=True)
    frappe.db.commit()

    return {"booking_name": doc.name}


@frappe.whitelist(allow_guest=True)
def get_pending_requests(mentor, limit=None):

    filters = {
        "mentor": mentor,
        "mentor_request_status": "Pending",
    }

    # -----------------------------------------
    # Total Pending Count
    # -----------------------------------------
    total_pending_count = frappe.db.count(
        "Mentor Session Booking",
        filters=filters
    )

    # -----------------------------------------
    # Query Arguments
    # -----------------------------------------
    query_args = {
        "doctype": "Mentor Session Booking",
        "filters": filters,
        "fields": [
            "name",
            "student",
            "offering",
            "topic",
            "session_date",
            "from_time",
            "to_time",
            "session_type",
            "priority",
            "student_message",
            "amount_paid",
        ],
        # "order_by": "FIELD(priority,'High','Medium','Low'), requested_date asc",
    }

    # -----------------------------------------
    # Apply Limit
    # -----------------------------------------
    if limit:
        query_args["limit_page_length"] = int(limit)

    rows = frappe.get_all(**query_args)

    # -----------------------------------------
    # Extra Details
    # -----------------------------------------
    for r in rows:

        r["student_name"] = (
            frappe.db.get_value(
                "User",
                r.student,
                "full_name"
            )
            or r.student
        )

        r["offering_title"] = (
            frappe.db.get_value(
                "Mentor Offering",
                r.offering,
                "title"
            )
            if r.offering else ""
        )

    # -----------------------------------------
    # Final Response
    # -----------------------------------------
    return {
        "total_pending_count": total_pending_count,
        "records": rows
    }


@frappe.whitelist()
def get_request_counts(mentor):
    """
    Summary counts for mentor dashboard request tab.
    """
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

    # Skill verification requests (separate doctype — keep as-is)
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

@frappe.whitelist()
def decline_request(booking_name, notes=None):
    """Mentor declines a pending session request."""
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


@frappe.whitelist()
def suggest_alt_time(booking_name, alt_date, alt_time, notes=None):
    """
    Mentor suggests a different date/time.
    Student can see this and confirm or cancel.
    """
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
    frappe.db.commit()

    return {"status": "Suggested Alt Time"}


@frappe.whitelist()
def student_confirm_alt_time(booking_name):
    """
    Student confirms the mentor's suggested alt time.
    Moves alt_date/alt_time → session_date/requested_time
    and sets mentor_request_status back to Pending
    so mentor can then Accept with from_time/to_time.
    """
    doc = frappe.get_doc("Mentor Session Booking", booking_name)

    if doc.mentor_request_status != "Suggested Alt Time":
        frappe.throw(_("No alternate time to confirm."))
    # if frappe.session.user != doc.student:
    #     frappe.throw(_("Only the student can confirm the alternate time."))

    doc.requested_date        = doc.alt_date
    doc.requested_time        = doc.alt_time
    doc.alt_date              = None
    doc.alt_time              = None
    doc.mentor_request_status = "Pending"
    doc.status                = "Accepted"
    doc.save(ignore_permissions=True)
    frappe.db.commit()
    
    # ---------------------------------------------------
    # Notify Mentor
    # ---------------------------------------------------

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


# ── Add this standalone function at module level ──────────────────────────────
@frappe.whitelist()
def _update_mentor_stats(mentor):

    if not mentor:
        return {"success": False, "message": "Mentor is required"}

    MENTOR_DOCTYPE = "Mentor"

    if not frappe.db.exists(MENTOR_DOCTYPE, mentor):
        mentor_doc_name = frappe.db.get_value(
            MENTOR_DOCTYPE,
            {"mentor": mentor},
            "name"
        )

        if not mentor_doc_name:
            return {
                "success": False,
                "message": "Mentor profile not found"
            }
    else:
        mentor_doc_name = mentor

    result = frappe.db.sql("""
        SELECT
            COUNT(*)                            AS total_sessions,
            COALESCE(SUM(duration), 0)          AS total_minutes,
            COALESCE(SUM(amount_paid), 0)       AS total_earnings,
            COALESCE(AVG(NULLIF(rating, 0)), 0) AS avg_rating
        FROM `tabMentor Session Booking`
        WHERE mentor = %(mentor)s
        AND status = 'Completed'
    """, {"mentor": mentor}, as_dict=True)

    row = result[0]

    total_sessions = int(row.total_sessions or 0)
    total_hours = round(float(row.total_minutes or 0) / 60, 2)
    total_earnings = float(row.total_earnings or 0)
    avg_rating = round(float(row.avg_rating or 0), 1)

    frappe.db.set_value(
        MENTOR_DOCTYPE,
        mentor_doc_name,
        {
            "total_sessions": total_sessions,
            "total_hours": total_hours,
            "total_earnings": total_earnings,
            "avg_rating": avg_rating,
        },
        update_modified=False
    )

    frappe.db.commit()

    return {
        "success": True,
        "mentor": mentor_doc_name,
        "total_sessions": total_sessions,
        "total_hours": total_hours,
        "total_earnings": total_earnings,
        "avg_rating": avg_rating
    }

# ── Update update_status API (used for submitted offering bookings) ────────────
@frappe.whitelist()
def update_status(booking_name, status):
    doc = frappe.get_doc("Mentor Session Booking", booking_name)

    if doc.docstatus != 1:
        frappe.throw(_("Only submitted bookings can be updated."))

    if status not in ["Completed", "Cancelled"]:
        frappe.throw(_("Invalid status value."))

    doc.db_set("status", status)

    if doc.offering:
        offering = frappe.get_doc("Mentor Offering", doc.offering)
        offering.update_aggregates()

    # ── Update mentor stats whenever status changes ────────────────────
    _update_mentor_stats(doc.mentor)

    return {"success": True}


# ── Also update cancel_session to trigger stats ───────────────────────────────

@frappe.whitelist()
def cancel_session(session_name):
    doc = frappe.get_doc("Mentor Session Booking", session_name)
    if doc.status != "Scheduled":
        frappe.throw(_("Only Scheduled sessions can be cancelled."))
    doc.status = "Cancelled"
    doc.save()
    frappe.db.commit()

    # ── Update mentor stats on cancel ─────────────────────────────────
    _update_mentor_stats(doc.mentor)

    return _("Session {0} cancelled.").format(session_name)


@frappe.whitelist()
def accept_request(booking_name, from_time, to_time, session_date=None):

    doc = frappe.get_doc(
        "Mentor Session Booking",
        booking_name
    )

    if doc.mentor_request_status != "Pending":
        frappe.throw(_("Only Pending requests can be accepted."))

    # -----------------------------------------
    # Preserve Existing Session Date
    # -----------------------------------------
    doc.session_date = (
        session_date
        or doc.session_date
        or doc.requested_date
    )

    doc.from_time = from_time
    doc.to_time = to_time

    doc.mentor_request_status = "Accepted"
    doc.status = "Scheduled"

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

    return {
        "booking_name": doc.name
    }


@frappe.whitelist(allow_guest=True)
def get_student_upcoming_sessions(student, limit=20):
    """All upcoming scheduled sessions for the student."""
    sessions = frappe.get_all(
        "Mentor Session Booking",
        filters={
            "student":      student,
            "status":       "Scheduled",
            "session_date": [">=", nowdate()],
            "mentor_request_status": ["in", ["Accepted", "", None]],
        },
        fields=["name", "mentor", "topic", "session_date",
                "from_time", "to_time", "duration", "status",
                "meeting_link", "offering", "offering_type",
                "lms_batch", "amount_paid"],
        order_by="session_date asc, from_time asc",
        limit_page_length=int(limit),
    )
    for s in sessions:
        s["mentor"] = frappe.db.get_value("User", s.mentor, "full_name") or s.mentor
        if s.offering:
            s["offering_title"] = frappe.db.get_value("Mentor Offering", s.offering, "title") or ""
    return sessions


@frappe.whitelist()
def get_student_pending_requests(student):
    """Session requests the student sent that are still awaiting mentor action."""
    rows = frappe.get_all(
        "Mentor Session Booking",
        filters={
            "student": student,
            "mentor_request_status": ["in", ["Pending", "Suggested Alt Time"]],
        },
        fields=["name", "mentor", "topic", "requested_date",
                "requested_time", "mentor_request_status",
                "priority", "alt_date", "alt_time", "notes",
                "offering", "amount_paid"],
        order_by="requested_date asc",
    )
    for r in rows:
        r["mentor"] = frappe.db.get_value("User", r.mentor, "full_name") or r.mentor
    return rows


@frappe.whitelist()
def get_student_session_history(student, from_date=None, to_date=None, limit=50):
    """Completed and cancelled sessions for history tab."""
    filters = {
        "student": student,
        "status":  ["in", ["Completed", "Cancelled"]],
    }
    if from_date and to_date:
        filters["session_date"] = ["between", [from_date, to_date]]

    sessions = frappe.get_all(
        "Mentor Session Booking",
        filters=filters,
        fields=["name", "mentor", "topic", "session_date",
                "from_time", "to_time", "duration", "status",
                "offering", "offering_type", "rating",
                "amount_paid"],
        order_by="session_date desc",
        limit_page_length=int(limit),
    )
    for s in sessions:
        s["mentor"] = frappe.db.get_value("User", s.mentor, "full_name") or s.mentor
    return sessions


@frappe.whitelist()
def save_session_notes(
    student,
    session_name,
    notes=None,
    shared_with_student=None
):

    try:

        # -----------------------------------
        # Validate Required Parameters
        # -----------------------------------
        if not student:
            return {
                "status": "error",
                "message": "student is required"
            }

        if not session_name:
            return {
                "status": "error",
                "message": "session_name is required"
            }

        # -----------------------------------
        # Fetch Session Document
        # -----------------------------------
        session_doc = frappe.get_doc(
            "Mentor Session Booking",
            session_name
        )

        # -----------------------------------
        # Validate Student
        # -----------------------------------
        if session_doc.student != student:
            return {
                "status": "error",
                "message": "This session does not belong to this student"
            }

        # -----------------------------------
        # Detect Add or Edit
        # -----------------------------------
        is_edit = False

        if session_doc.notes:
            is_edit = True

        # -----------------------------------
        # Save Notes
        # -----------------------------------
        if notes is not None:
            session_doc.notes = notes

        if shared_with_student is not None:
            session_doc.shared_with_student = shared_with_student

        # -----------------------------------
        # Save Document
        # -----------------------------------
        session_doc.save(ignore_permissions=True)

        frappe.db.commit()

        # -----------------------------------
        # Dynamic Success Message
        # -----------------------------------
        success_message = (
            "Session note updated successfully"
            if is_edit
            else "Session note added successfully"
        )

        return {
            "status": "success",
            "message": success_message,
            "is_edit": is_edit,
            "data": {
                "student": session_doc.student,
                "session_name": session_doc.name,
                "notes": session_doc.notes,
                "shared_with_student": session_doc.shared_with_student
            }
        }

    except Exception as e:

        frappe.db.rollback()

        frappe.log_error(
            frappe.get_traceback(),
            "Save Session Notes Error"
        )

        return {
            "status": "error",
            "message": str(e)
        }
        

@frappe.whitelist()
def get_session_note(student, session_name):

    try:

        # -----------------------------------
        # Validate Required Parameters
        # -----------------------------------
        if not student:
            return {
                "status": "error",
                "message": "student is required"
            }

        if not session_name:
            return {
                "status": "error",
                "message": "session_name is required"
            }

        # -----------------------------------
        # Fetch Session Document
        # -----------------------------------
        session_doc = frappe.get_doc(
            "Mentor Session Booking",
            session_name
        )

        # -----------------------------------
        # Validate Student
        # -----------------------------------
        if session_doc.student != student:
            return {
                "status": "error",
                "message": "This session does not belong to this student"
            }

        # -----------------------------------
        # Return Existing Notes
        # -----------------------------------
        return {
            "status": "success",
            "message": "Session note fetched successfully",
            "data": {
                "student": session_doc.student,
                "session_name": session_doc.name,
                "notes": session_doc.notes,
                "shared_with_student": session_doc.shared_with_student
            }
        }

    except Exception as e:

        frappe.log_error(
            frappe.get_traceback(),
            "Get Session Note Error"
        )

        return {
            "status": "error",
            "message": str(e)
        }
  

@frappe.whitelist()
def email_to_student(student, session_name, subject, message):
    try:
        session_doc = frappe.get_doc("Mentor Session Booking", session_name)

        if session_doc.student != student:
            return {"status": "error", "message": "Invalid student"}

        student_email = session_doc.student
        mentor_email = session_doc.mentor

        if not student_email:
            return {"status": "error", "message": "Student email not found"}

        if not mentor_email:
            return {"status": "error", "message": "Mentor email not found"}

        # ── Run email operations as Administrator to bypass permission issues ──
        current_user = frappe.session.user  # save current user
        frappe.set_user("Administrator")

        try:
            # Step 1: Queue the email
            email_queue = frappe.sendmail(
                recipients=[student_email],
                sender=mentor_email,
                reply_to=mentor_email,
                subject=subject,
                message=message,
                now=False
            )

            frappe.db.commit()

            # Step 2: Manually trigger send_now
            if email_queue and hasattr(email_queue, "name"):
                send_now(email_queue.name)
            else:
                queued = frappe.db.get_value(
                    "Email Queue",
                    {
                        "status": "Not Sent",
                        "recipients": student_email
                    },
                    "name",
                    order_by="creation desc"
                )
                if queued:
                    send_now(queued)
                else:
                    return {
                        "status": "error",
                        "message": "Email queued but could not find record to send"
                    }

            # Step 3: Verify sent status
            if email_queue and hasattr(email_queue, "name"):
                status = frappe.db.get_value(
                    "Email Queue",
                    email_queue.name,
                    "status"
                )
                if status != "Sent":
                    error_msg = frappe.db.get_value(
                        "Email Queue",
                        email_queue.name,
                        "error"
                    )
                    return {
                        "status": "error",
                        "message": f"Email failed. SMTP Error: {error_msg}"
                    }

        finally:
            frappe.set_user(current_user)  # ← Always restore original user

        return {
            "status": "success",
            "message": f"Email sent successfully to {student_email}"
        }

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Email To Student Error")
        return {"status": "error", "message": str(e)}
    
