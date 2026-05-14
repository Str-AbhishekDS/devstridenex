# Copyright (c) 2026, QTPL and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe import _
from stridenex_app.stridenex_app.doctype.mentor_session_booking.mentor_session_booking import get_slot_calendar


class MentorOffering(Document):

    def autoname(self):
        from frappe.model.naming import make_autoname
        self.name = make_autoname("MO-.YYYY.-.#####")

    def validate(self):
        self.validate_pricing()
        self.validate_type_fields()

    def validate_pricing(self):
        if self.price_per_session <= 0:
            frappe.throw(_("Price per session must be greater than zero."))

    def validate_type_fields(self):
        if self.offering_type == "Group Session" and not self.max_group_size:
            frappe.throw(_("Max Group Size is required for Group Sessions."))
        if self.offering_type == "Async Review" and not self.turnaround_hours:
            frappe.throw(_("Turnaround Hours is required for Async Review."))

    def on_update(self):
        self.update_aggregates()

    def update_aggregates(self):
        """Recalculate total bookings and average rating from session bookings."""
        result = frappe.db.sql("""
            SELECT COUNT(*) as total, AVG(rating) as avg_rating
            FROM `tabMentor Session Booking`
            WHERE offering = %s AND status = 'Completed'
        """, self.name, as_dict=True)

        if result:
            self.db_set("total_bookings", result[0].total or 0)
            self.db_set("average_rating", round(result[0].avg_rating or 0, 1))


# ── Whitelisted APIs ───────────────────────────────────────────────────────────

@frappe.whitelist(allow_guest=True)
def get_mentor_offerings(mentor, status=None):
    filters = {"mentor": mentor}
    if status:
        filters["status"] = status
    return frappe.get_all(
        "Mentor Offering",
        filters=filters,
        fields=[
            "name", "title", "offering_type", "category",
            "duration_minutes", "price_per_session", "status",
            "total_bookings", "average_rating"
        ],
        order_by="creation desc"
    )


@frappe.whitelist(allow_guest=True)
def toggle_offering_status(offering_name, action):
    doc = frappe.get_doc("Mentor Offering", offering_name)
    status_map = {
        "pause":    "Paused",
        "activate": "Live",
        "archive":  "Archived"
    }
    if action not in status_map:
        frappe.throw(_("Invalid action."))
    doc.status = status_map[action]
    doc.save(ignore_permissions=True)
    return {"status": doc.status}


@frappe.whitelist(allow_guest=True)
def create_lms_batch_for_offering(offering_name):
    """
    Create an LMS Batch linked to this offering.
    No lms_course field needed — the batch is linked to the offering directly
    via a custom 'offering' field on LMS Batch (or we store batch name on offering).
    """
    offering = frappe.get_doc("Mentor Offering", offering_name)

    if offering.offering_type != "Group Session":
        frappe.throw(_("LMS Batch can only be created for Group Session offerings."))

    # ── Already has a batch → return it ─────────────────────────────
    if offering.lms_batch:
        return {"batch_name": offering.lms_batch, "already_exists": True}

    # ── Get mentor's full name for instructor field ───────────────────
    mentor_full_name = frappe.db.get_value("User", offering.mentor, "full_name") or offering.mentor

    # ── Build batch doc ───────────────────────────────────────────────
    # LMS Batch uses autoname so we do NOT set 'name' manually.
    # 'title' is the display name shown in the UI.
    batch_data = {
        "doctype":    "LMS Batch",
        "title":      offering.title,
        "published":  0,
        "seat_count": int(offering.max_group_size or 0),
        "start_date": offering.start_date,
        "end_date": offering.end_date,
        "start_time": offering.start_time,
        "end_time": offering.end_time,
        "timezone": "Asia/Kolkata",
        "batch_details": offering.batch_details,
        "description": offering.description,
    }

    # Add description only if offering has one
    if offering.get("description"):
        batch_data["description"] = offering.description

    # Add instructor row — fieldname confirmed from LMS source
    # batch_data["instructors"] = [{"instructor": mentor_full_name}]
    batch_data["instructors"] = [{"instructor": offering.mentor}]
    

    # Link lms_course only if the field exists and is filled
    if offering.get("lms_course"):
        batch_data["courses"] = [{"course": offering.lms_course}]

    batch = frappe.get_doc(batch_data)
    batch.insert(ignore_permissions=True)
    frappe.db.commit()

    # ── Save batch name back on offering ─────────────────────────────
    frappe.db.set_value("Mentor Offering", offering_name, "lms_batch", batch.name)

    return {"batch_name": batch.name, "already_exists": False}


@frappe.whitelist(allow_guest=True)
def get_open_batches_for_offering(offering):
    """
    Return open LMS Batches linked to this offering.
    Filters by lms_batch stored on Mentor Offering — no course join needed.
    """
    if not offering:
        frappe.throw(_("Offering is required."))

    from frappe.utils import nowdate

    offering_doc = frappe.db.get_value(
        "Mentor Offering",
        offering,
        ["lms_batch", "max_group_size", "offering_type"],
        as_dict=True
    )

    if not offering_doc:
        frappe.throw(_("Offering not found."))

    if offering_doc.offering_type != "Group Session":
        frappe.throw(_("This offering is not a Group Session."))

    if not offering_doc.lms_batch:
        frappe.throw(_("No LMS Batch linked to this offering yet. Ask your mentor to create one."))

    # ── Fetch the single linked batch ────────────────────────────────
    batch = frappe.db.get_value(
        "LMS Batch",
        offering_doc.lms_batch,
        ["name", "title", "start_date", "end_date",
         "seat_count", "published", "description"],
        as_dict=True
    )

    if not batch:
        frappe.throw(_("Linked LMS Batch not found. It may have been deleted."))

    if not batch.published:
        frappe.throw(_("The batch is not published yet. Ask your mentor to publish it."))

    # Check if batch end_date has passed
    if batch.end_date and str(batch.end_date) < nowdate():
        frappe.throw(_("This batch has already ended."))

    # ── Count current enrollments ─────────────────────────────────────
    current_count = frappe.db.count(
        "LMS Batch Enrollment",
        filters={"batch": offering_doc.lms_batch}
    )

    seat_count = int(batch.seat_count or 0)
    seats_left = (seat_count - current_count) if seat_count else 999

    batch["current_count"] = current_count
    batch["seats_left"]    = seats_left
    batch["is_full"]       = seat_count > 0 and current_count >= seat_count

    # Return as list so JS can use same card-picker pattern
    return [batch]

@frappe.whitelist(allow_guest=True)
def enroll_student_in_batch(offering, batch_name, student):
    """
    Enroll a student into an LMS Batch using the LMS Batch Enrollment doctype.
    Also creates LMS Enrollment (course-level) if lms_course is linked.
    """
    from frappe.utils import nowdate

    offering_doc = frappe.get_doc("Mentor Offering", offering)
    batch_doc    = frappe.get_doc("LMS Batch", batch_name)
    seat_count   = int(batch_doc.seat_count or 0)

    # ── Seat check ────────────────────────────────────────────────────
    current_count = frappe.db.count(
        "LMS Batch Enrollment",
        filters={"batch": batch_name}
    )

    if seat_count and current_count >= seat_count:
        frappe.throw(_("This batch is full. No seats available."))

    # ── Duplicate check ───────────────────────────────────────────────
    already = frappe.db.exists(
        "LMS Batch Enrollment",
        {"batch": batch_name, "member": student}
    )
    if already:
        frappe.throw(_("You are already enrolled in this batch."))

    # ── Create LMS Batch Enrollment record ────────────────────────────
    # LMS Batch Enrollment is a standalone doctype, NOT a child table.
    # Fields confirmed: batch (Link→LMS Batch), member (Link→User)
    batch_enrollment = frappe.get_doc({
        "doctype": "LMS Batch Enrollment",
        "batch":   batch_name,
        "member":  student,
    })
    batch_enrollment.insert(ignore_permissions=True)
    frappe.db.commit()

    # ── Create LMS Enrollment (course-level) if lms_course linked ─────
    enrollment_name = None
    lms_course = offering_doc.get("lms_course")

    if lms_course:
        existing = frappe.db.get_value(
            "LMS Enrollment",
            {"course": lms_course, "member": student},
            "name"
        )
        if existing:
            enrollment_name = existing
        else:
            course_enrollment = frappe.get_doc({
                "doctype": "LMS Enrollment",
                "course":  lms_course,
                "member":  student,
                "batch":   batch_name,
                "source":  "Mentor Booking",
            })
            course_enrollment.insert(ignore_permissions=True)
            frappe.db.commit()
            enrollment_name = course_enrollment.name

    seats_left = (seat_count - (current_count + 1)) if seat_count else 999

    return {
        "enrollment_name": enrollment_name,
        "batch_name":      batch_name,
        "seats_left":      seats_left,
    }
    
@frappe.whitelist(allow_guest=True)
def get_mentor_listings(skill=None, min_price=None, max_price=None,
                        min_rating=None, availability_day=None,
                        offering_type=None, search=None, limit=20, offset=0):
    """
    Main API for the Mentors tab card grid.
    Returns mentor cards with: name, designation, company, tags,
    avg_rating, total_sessions, price_per_session, next available slot.
    """
    filters = {"status": "Live"}

    if offering_type:
        filters["offering_type"] = offering_type

    if min_price:
        filters["price_per_session"] = [">=", float(min_price)]

    if max_price:
        filters.setdefault("price_per_session", ["between", [float(min_price or 0), float(max_price)]])

    if min_rating:
        filters["average_rating"] = [">=", float(min_rating)]

    offerings = frappe.get_all(
        "Mentor Offering",
        filters=filters,
        fields=["name", "mentor", "title", "offering_type",
                "price_per_session", "average_rating",
                "total_bookings", "duration_minutes"],
        order_by="average_rating desc, total_bookings desc",
        limit_page_length=int(limit),
        limit_start=int(offset),
    )

    result = []
    seen_mentors = set()

    for o in offerings:
        mentor_email = o.mentor
        if mentor_email in seen_mentors:
            continue
        seen_mentors.add(mentor_email)

        # Get mentor profile details
        mentor_profile = frappe.db.get_value(
            "Mentor",       # ← your mentor doctype name
            mentor_email,
            ["first_name","last_name", 
              "total_sessions",
             "total_hours", "avg_rating"],
            as_dict=True
        ) or {}

        # Get skill tags
        tags = frappe.get_all(
            "Student Skill Table",         # ← your skills child table / doctype
            filters={"parent": mentor_email},
            fields=["skill"],
            limit=5
        )

        # Get next available slot (preview shown on card)
        next_slot = _get_next_available_slot(mentor_email)

        result.append({
            "mentor":        mentor_email,
            "full_name":     mentor_profile.get("full_name") or mentor_email,
            "designation":   mentor_profile.get("designation", ""),
            "company":       mentor_profile.get("company", ""),
            "profile_image": mentor_profile.get("profile_image", ""),
            "tags":          [t.skill for t in tags],
            "avg_rating":    mentor_profile.get("avg_rating") or o.average_rating or 0,
            "total_sessions":mentor_profile.get("total_sessions") or o.total_bookings or 0,
            "price_per_hour":o.price_per_session,
            "offering_name": o.name,
            "offering_type": o.offering_type,
            "next_slot":     next_slot,   # e.g. "Feb 27, 4PM" or "Available"
        })

    return result

@frappe.whitelist(allow_guest=True)
def _get_next_available_slot(mentor):
    from frappe.utils import nowdate, add_days
    import datetime

    today = nowdate()
    current_time = datetime.datetime.now().time()  # ✅ current system time

    for i in range(7):
        check_date = add_days(today, i)

        calendar = get_slot_calendar(
            mentor=mentor,
            from_date=check_date,
            to_date=check_date,
        )

        # ✅ FIX: use string key
        day_slots = calendar.get(str(check_date), [])

        # ✅ only available slots
        available = [s for s in day_slots if s["status"] == "available"]

        # ✅ IMPORTANT: filter past time ONLY for today
        if str(check_date) == today:
            future_slots = []
            for s in available:
                slot_time = datetime.datetime.strptime(
                    s["from_time"], "%H:%M:%S"
                ).time()

                if slot_time > current_time:
                    future_slots.append(s)

            available = future_slots

        # ✅ if valid slot found
        if available:
            slot_time = available[0]["from_time"][:5]

            dt = datetime.datetime.strptime(str(check_date), "%Y-%m-%d")
            day_label = dt.strftime("%b %d")   # safer format

            # Convert to 12-hour format
            h, m = map(int, slot_time.split(":"))
            ampm = "AM" if h < 12 else "PM"
            h12 = h % 12 or 12

            time_label = f"{h12}:{m:02d} {ampm}" if m else f"{h12} {ampm}"

            return f"{day_label}, {time_label}"

    return "No Slots Available"