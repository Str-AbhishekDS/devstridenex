# Copyright (c) 2024, Your Company and contributors
# For license information, please see license.txt

# ── Add this import at the top ───────────────────────────────────────────────
from stridenex_app.api_stridenex_app.app_utils import (
    add_student_to_batch,
    remove_student_from_batch,
    get_or_create_course_enrollment,
)

import frappe
from frappe.model.document import Document
from frappe import _
from frappe.utils import getdate, nowdate, get_time, add_days
from frappe.utils import getdate, nowdate, get_time, add_days
import datetime


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


# ------------------------------------------------------------------
# Shared Helpers
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
# Slot Calendar API
# ------------------------------------------------------------------

# In mentor_session_booking.py
# ─────────────────────────────────────────────────────────────────────────────
# Replace get_slot_calendar in mentor_session_booking.py
# ─────────────────────────────────────────────────────────────────────────────


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
        "status":       "Scheduled",   # ✅ FIXED (not Scheduled)
    })

    doc.insert(ignore_permissions=False)
    frappe.db.commit()

    return {"session_name": doc.name}


@frappe.whitelist()
def reschedule_session(session_name, new_date, new_from_time, new_to_time):
    doc = frappe.get_doc("Mentor Session Booking", session_name)

    if doc.status != "Scheduled":
        frappe.throw(_("Only Scheduled sessions can be rescheduled."))

    old_date = doc.session_date
    old_from = doc.from_time
    old_to   = doc.to_time

    doc.session_date = new_date
    doc.from_time    = new_from_time
    doc.to_time      = new_to_time
    doc.save()
    frappe.db.commit()

    return {
        "message":  _("Session rescheduled successfully"),
        "old_slot": f"{old_date} {old_from}-{old_to}",
        "new_slot": f"{new_date} {new_from_time}-{new_to_time}"
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
def submit_review(booking_name, rating, review):
    """Submit a star rating + review text for a completed offering booking."""
    if not frappe.db.exists("Mentor Session Booking", booking_name):
        frappe.throw(_("Invalid Booking"))

    booking = frappe.db.get_value(
        "Mentor Session Booking",
        booking_name,
        ["status", "docstatus", "offering"],
        as_dict=True
    )

    if booking.docstatus != 1:
        frappe.throw(_("Booking must be submitted before reviewing."))

    if booking.status != "Completed":
        frappe.throw(_("Only completed sessions can be reviewed."))

    frappe.db.set_value("Mentor Session Booking", booking_name, {
        "rating":  float(rating),
        "review":  review
    })

    # Refresh offering aggregates
    if booking.offering:
        offering = frappe.get_doc("Mentor Offering", booking.offering)
        offering.update_aggregates()

    return {"success": True}

@frappe.whitelist()
def get_upcoming_sessions(mentor, limit=20):
    return frappe.get_all(
        "Mentor Session Booking",
        filters={"mentor": mentor, "session_date": [">=", nowdate()], "status": "Scheduled"},
        fields=["name", "student", "topic", "session_date", "from_time",
                "to_time", "duration", "status", "meeting_link", "offering"],
        order_by="session_date asc, from_time asc",
        limit_page_length=int(limit),
    )


@frappe.whitelist()
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
def get_weekly_booked_sessions(mentor, week_start_date):
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

@frappe.whitelist()
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
        "status":                "Scheduled",          # will update on accept
        "mentor_request_status": "Pending",
    })
    doc.insert(ignore_permissions=True)
    frappe.db.commit()

    return {"booking_name": doc.name}


@frappe.whitelist(allow_guest=True)
def get_pending_requests(mentor):
    """
    Return all Pending session requests for a mentor.
    Ordered: High priority first, then soonest requested_date.
    """
    rows = frappe.get_all(
        "Mentor Session Booking",
        filters={
            "mentor":                mentor,
            "mentor_request_status": "Pending",
        },
        fields=[
            "name", "student", "offering", "topic",
            "requested_date", "requested_time",
            "session_type", "priority", "student_message",
            "amount_paid",
        ],
        # order_by="FIELD(priority,'High','Medium','Low'), requested_date asc",
    )

    for r in rows:
        r["student_name"]   = frappe.db.get_value("User", r.student, "full_name") or r.student
        r["offering_title"] = frappe.db.get_value("Mentor Offering", r.offering, "title") if r.offering else ""

    return rows


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
    if frappe.session.user != doc.student:
        frappe.throw(_("Only the student can confirm the alternate time."))

    doc.requested_date        = doc.alt_date
    doc.requested_time        = doc.alt_time
    doc.alt_date              = None
    doc.alt_time              = None
    doc.mentor_request_status = "Pending"
    doc.save(ignore_permissions=True)
    frappe.db.commit()

    return {"status": "Pending"}



# ── Add this standalone function at module level ──────────────────────────────

def _update_mentor_stats(mentor):
    """
    Recalculate and update mentor's aggregate stats on the Mentor doctype.
    Called whenever a session is Completed or Cancelled.

    Calculates:
      total_sessions  → count of Completed bookings
      total_hours     → sum of duration (minutes) / 60
      total_earnings  → sum of amount_paid for Completed bookings
      avg_rating      → average of non-zero ratings on Completed bookings
    """
    if not mentor:
        return

    # ── Check which doctype stores mentor profile ─────────────────────
    # Change "Mentor" to your actual mentor doctype name
    MENTOR_DOCTYPE = "Mentor"

    if not frappe.db.exists(MENTOR_DOCTYPE, mentor):
        # Try by mentor field (if name ≠ user email)
        mentor_doc_name = frappe.db.get_value(MENTOR_DOCTYPE, {"mentor": mentor}, "name")
        if not mentor_doc_name:
            return   # No mentor profile found — skip silently
    else:
        mentor_doc_name = mentor

    # ── Single SQL query for all stats ────────────────────────────────
    result = frappe.db.sql("""
        SELECT
            COUNT(*)                                    AS total_sessions,
            COALESCE(SUM(duration), 0)                  AS total_minutes,
            COALESCE(SUM(amount_paid), 0)               AS total_earnings,
            COALESCE(AVG(NULLIF(rating, 0)), 0)         AS avg_rating
        FROM `tabMentor Session Booking`
        WHERE
            mentor  = %(mentor)s
            AND status = 'Completed'
    """, {"mentor": mentor}, as_dict=True)

    if not result:
        return

    row            = result[0]
    total_sessions = int(row.total_sessions or 0)
    total_hours    = round(float(row.total_minutes or 0) / 60, 2)
    total_earnings = float(row.total_earnings or 0)
    avg_rating     = round(float(row.avg_rating or 0), 1)

    # ── Update mentor profile doc ─────────────────────────────────────
    frappe.db.set_value(
        MENTOR_DOCTYPE,
        mentor_doc_name,
        {
            "total_sessions": total_sessions,
            "total_hours":    total_hours,
            "total_earnings": total_earnings,
            "avg_rating":     avg_rating,
        },
        update_modified=False   # don't bump modified timestamp for stat updates
    )
    frappe.db.commit()

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


# ── Add accept_request trigger too ────────────────────────────────────────────
@frappe.whitelist()
def accept_request(booking_name, from_time, to_time, session_date=None):
    doc = frappe.get_doc("Mentor Session Booking", booking_name)

    if doc.mentor_request_status != "Pending":
        frappe.throw(_("Only Pending requests can be accepted."))

    doc.session_date          = session_date or doc.requested_date
    doc.from_time             = from_time
    doc.to_time               = to_time
    doc.mentor_request_status = "Accepted"
    doc.status                = "Scheduled"

    doc.save(ignore_permissions=True)
    frappe.db.commit()

    return {"booking_name": doc.name}


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
        s["mentor_name"] = frappe.db.get_value("User", s.mentor, "full_name") or s.mentor
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
        r["mentor_name"] = frappe.db.get_value("User", r.mentor, "full_name") or r.mentor
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
        s["mentor_name"] = frappe.db.get_value("User", s.mentor, "full_name") or s.mentor
    return sessions