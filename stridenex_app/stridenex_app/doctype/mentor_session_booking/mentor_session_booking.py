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

    def autoname(self):
        from frappe.model.naming import make_autoname
        # Use different prefix based on booking type
        self.name = make_autoname("MSB-.YYYY.-.#####")

    def validate(self):
        self.fetch_mentor_from_offering()
        self.fetch_amount_from_offering()
        self.validate_not_self_booking()
        self.validate_date_not_past()
        self.validate_time_range()
        self.calculate_duration()

        # Skip slot validations for Offering bookings (no fixed slots)
        if self.status == "Cancelled":
            return

        # Only validate availability for session (slot-based) bookings     
        self.validate_mentor_availability()
        self.validate_mentor_not_blocked()
        self.check_double_booking()

    def on_submit(self):
        if self.status == "Scheduled":
            self.db_set("status", "Scheduled")
        self.update_offering_aggregates()
            

    def on_cancel(self):
        self.db_set("status", "Cancelled")
        self.update_offering_aggregates()

    # ------------------------------------------------------------------
    # Offering-related helpers
    # ------------------------------------------------------------------

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
        if self.from_time and self.to_time:
            if self.from_time >= self.to_time:
                frappe.throw(_("From Time must be earlier than To Time."))

    def calculate_duration(self):
        if self.from_time and self.to_time:
            start = get_time(self.from_time)
            end   = get_time(self.to_time)
            self.duration = (end.hour * 60 + end.minute) - (start.hour * 60 + start.minute)

    def validate_mentor_availability(self):
        day_name = getdate(self.session_date).strftime("%A").lower()

        self_from = get_time(self.from_time)
        self_to   = get_time(self.to_time)

        # Get all availability docs
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

            # ✅ CASE 2: Different schedule (child table)
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

@frappe.whitelist()
def get_slot_calendar(mentor, from_date, to_date, offering=None):

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


@frappe.whitelist()
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


# ------------------------------------------------------------------
# Offering-specific APIs  (previously in mentor_offering_booking.py)
# ------------------------------------------------------------------

@frappe.whitelist()
def submit_review(booking_name, rating, review_text):
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
        "review":  review_text
    })

    # Refresh offering aggregates
    if booking.offering:
        offering = frappe.get_doc("Mentor Offering", booking.offering)
        offering.update_aggregates()

    return {"success": True}


@frappe.whitelist()
def update_status(booking_name, status):
    """Update booking status to Completed or Cancelled (submitted docs only)."""
    doc = frappe.get_doc("Mentor Session Booking", booking_name)

    if doc.docstatus != 1:
        frappe.throw(_("Only submitted bookings can be updated."))

    if status not in ["Completed", "Cancelled"]:
        frappe.throw(_("Invalid status value."))

    doc.db_set("status", status)

    if doc.offering:
        offering = frappe.get_doc("Mentor Offering", doc.offering)
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

