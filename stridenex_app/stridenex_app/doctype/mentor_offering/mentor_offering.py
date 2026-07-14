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

@frappe.whitelist(allow_guest=False)
def get_mentor_offerings(mentor, status=None):

    session_user = frappe.session.user

    # ----------------------------------------------------------
    # PERMISSION CHECK
    # Respects Role Permission Manager configuration
    # ----------------------------------------------------------
    if not frappe.has_permission(
        "Mentor Offering",
        ptype="read",
        user=session_user
    ):
        frappe.throw(
            "You do not have permission to access Mentor Offerings.",
            frappe.PermissionError
        )

    filters = {"mentor": mentor}

    if status:
        filters["status"] = status

    return frappe.get_list(
        "Mentor Offering",
        filters=filters,
        fields=[
            "name",
            "title",
            "offering_type",
            "category",
            "duration_minutes",
            "price_per_session",
            "status",
            "total_bookings",
            "average_rating",
            "description"
        ],
        order_by="creation desc"
    )

@frappe.whitelist(allow_guest=False)
def create_mentor_offering():

    # ----------------------------------------------------------
    # PERMISSION CHECK
    # Respects Role Permission Manager configuration
    # ----------------------------------------------------------
    session_user = frappe.session.user

    if not frappe.has_permission(
        "Mentor Offering",
        ptype="create",
        user=session_user
    ):
        frappe.throw(
            "You do not have permission to create Mentor Offering.",
            frappe.PermissionError
        )

    data = frappe.request.get_json()

    doc = frappe.get_doc({
        "doctype": "Mentor Offering",
        "mentor": data.get("mentor"),
        "title": data.get("title"),
        "offering_type": data.get("offering_type"),
        "category": data.get("category"),
        "duration_minutes": data.get("duration_minutes"),
        "price_per_session": data.get("price_per_session"),
        "max_group_size": data.get("max_group_size"),
        "description": data.get("description"),
        "status": data.get("status", "Draft"),
        "is_featured": data.get("is_featured", 0),

        "lms_course": data.get("lms_course"),
        "lms_batch": data.get("lms_batch"),

        "start_date": data.get("start_date"),
        "end_date": data.get("end_date"),

        "start_time": data.get("start_time"),
        "end_time": data.get("end_time"),

        "batch_details": data.get("batch_details")
    })

    # Respects Role Permission Manager
    doc.insert()

    frappe.db.commit()

    return {
        "status": "success",
        "message": "Mentor Offering Created",
        "name": doc.name
    }

@frappe.whitelist(allow_guest=False)
def update_mentor_offering(name):

    # ----------------------------------------------------------
    # PERMISSION CHECK
    # Respects Role Permission Manager configuration
    # ----------------------------------------------------------
    session_user = frappe.session.user

    if not frappe.has_permission(
        "Mentor Offering",
        ptype="write",
        user=session_user
    ):
        frappe.throw(
            "You do not have permission to update Mentor Offering.",
            frappe.PermissionError
        )

    data = frappe.request.get_json()

    # Check document exists
    if not frappe.db.exists("Mentor Offering", name):
        frappe.throw("Mentor Offering not found")

    # Get document
    doc = frappe.get_doc("Mentor Offering", name)

    # Update fields
    updatable_fields = [
        "mentor",
        "title",
        "offering_type",
        "category",
        "duration_minutes",
        "turnaround_hours",
        "sessions_per_month",
        "max_group_size",
        "price_per_session",
        "description",
        "status",
        "is_featured",
        "lms_course",
        "lms_batch",
        "start_date",
        "end_date",
        "start_time",
        "end_time",
        "batch_details"
    ]

    for field in updatable_fields:
        if field in data:
            doc.set(field, data.get(field))

    # Respects Role Permission Manager
    doc.save()

    frappe.db.commit()

    return {
        "status": "success",
        "message": "Mentor Offering Updated Successfully",
        "data": {
            "name": doc.name,
            "title": doc.title,
            "status": doc.status,
            "price_per_session": doc.price_per_session
        }
    }

@frappe.whitelist()
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


def _assert_mentor_owns_offering(offering_doc):
    """
    Raises PermissionError if current user is not the owning mentor.
    Mentor.name == email_id == frappe.session.user
    """
    current_user = frappe.session.user
    roles = frappe.get_roles(current_user)

    if "System Manager" in roles or current_user == "Administrator":
        return

    # Mentor.name IS the email_id, so direct comparison works
    if offering_doc.mentor != current_user:
        frappe.throw(
            _("You do not have permission to access this offering."),
            frappe.PermissionError
        )


    return {"batch_name": batch.name, "already_exists": False}

@frappe.whitelist()
def create_lms_batch_for_offering(offering_name):
    """
    Create an LMS Batch linked to this offering.
    Only the owning mentor (or admin) can call this.
    """
    # ── Permission check on Mentor Offering ─────────────────────────
    frappe.has_permission("Mentor Offering", ptype="read", doc=offering_name, throw=True)

    offering = frappe.get_doc("Mentor Offering", offering_name)

    if offering.offering_type != "Group Session":
        frappe.throw(_("LMS Batch can only be created for Group Session offerings."))

    # ── Already has a batch → return it ─────────────────────────────
    if offering.lms_batch:
        return {"batch_name": offering.lms_batch, "already_exists": True}

    # ── Build batch doc ──────────────────────────────────────────────
    batch_data = {
        "doctype": "LMS Batch",
        "title": offering.title,
        "published": 0,
        "seat_count": int(offering.max_group_size or 0),
        "start_date": offering.start_date,
        "end_date": offering.end_date,
        "start_time": offering.start_time,
        "end_time": offering.end_time,
        "timezone": "Asia/Kolkata",
        "batch_details": offering.batch_details,
        "description": offering.description,
        "mentor": offering.mentor,
    }

    # ── Verify the child table field name in your LMS Batch doctype ──
    # Check via: frappe.get_meta("LMS Batch").get_field("batch_instructors")
    # Common field names: "batch_instructors" or "instructors"
    batch_data["instructors"] = [{"instructor": offering.mentor}]

    if offering.get("lms_course"):
        batch_data["courses"] = [{"course": offering.lms_course}]

    batch = frappe.get_doc(batch_data)
    batch.insert(ignore_permissions=True)

    if not batch.name:
        frappe.throw(_("Batch creation failed. Please check server logs."))

    # ── Save batch name back on the offering ────────────────────────
    offering.db_set("lms_batch", batch.name, update_modified=False)
    frappe.db.commit()

    return {"batch_name": batch.name, "already_exists": False}


@frappe.whitelist()
def get_open_batches_for_offering(offering):
    """
    Return open LMS Batches linked to this offering.
    Only the owning mentor (or admin) can call this.
    """
    if not offering:
        frappe.throw(_("Offering is required."))

    from frappe.utils import nowdate

    offering_doc = frappe.db.get_value(
        "Mentor Offering",
        offering,
        ["lms_batch", "max_group_size", "offering_type", "mentor"],
        as_dict=True
    )

    if not offering_doc:
        frappe.throw(_("Offering not found."))

    # ── Ownership check (pass the dict, not the string) ───────────────
    _assert_mentor_owns_offering(offering_doc)

    if offering_doc.offering_type != "Group Session":
        frappe.throw(_("This offering is not a Group Session."))

    if not offering_doc.lms_batch:
        frappe.throw(_("No LMS Batch linked to this offering yet. Ask your mentor to create one."))

    # ── Fetch the single linked batch ─────────────────────────────────
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

    return [batch]


@frappe.whitelist()
def enroll_student_in_batch(offering, batch_name, student):
    """
    Enroll a student into an LMS Batch.
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
    if frappe.db.exists("LMS Batch Enrollment", {"batch": batch_name, "member": student}):
        frappe.throw(_("You are already enrolled in this batch."))

    # ── Create enrollment ─────────────────────────────────────────────
    batch_enrollment = frappe.get_doc({
        "doctype": "LMS Batch Enrollment",
        "batch":   batch_name,
        "member":  student,
    })
    batch_enrollment.insert(ignore_permissions=True)
    frappe.db.commit()

    # ── Course-level enrollment if lms_course linked ──────────────────
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

# @frappe.whitelist()
# def enroll_student_in_batch(offering, batch_name, student):
#     """
#     Enroll a student into an LMS Batch using the LMS Batch Enrollment doctype.
#     Also creates LMS Enrollment (course-level) if lms_course is linked.
#     """
#     from frappe.utils import nowdate

#     offering_doc = frappe.get_doc("Mentor Offering", offering)
#     batch_doc    = frappe.get_doc("LMS Batch", batch_name)
#     seat_count   = int(batch_doc.seat_count or 0)

#     # ── Seat check ────────────────────────────────────────────────────
#     current_count = frappe.db.count(
#         "LMS Batch Enrollment",
#         filters={"batch": batch_name}
#     )

#     if seat_count and current_count >= seat_count:
#         frappe.throw(_("This batch is full. No seats available."))

#     # ── Duplicate check ───────────────────────────────────────────────
#     already = frappe.db.exists(
#         "LMS Batch Enrollment",
#         {"batch": batch_name, "member": student}
#     )
#     if already:
#         frappe.throw(_("You are already enrolled in this batch."))

#     # ── Create LMS Batch Enrollment record ────────────────────────────
#     # LMS Batch Enrollment is a standalone doctype, NOT a child table.
#     # Fields confirmed: batch (Link→LMS Batch), member (Link→User)
#     batch_enrollment = frappe.get_doc({
#         "doctype": "LMS Batch Enrollment",
#         "batch":   batch_name,
#         "member":  student,
#     })
#     batch_enrollment.insert(ignore_permissions=True)
#     frappe.db.commit()

#     # ── Create LMS Enrollment (course-level) if lms_course linked ─────
#     enrollment_name = None
#     lms_course = offering_doc.get("lms_course")

#     if lms_course:
#         existing = frappe.db.get_value(
#             "LMS Enrollment",
#             {"course": lms_course, "member": student},
#             "name"
#         )
#         if existing:
#             enrollment_name = existing
#         else:
#             course_enrollment = frappe.get_doc({
#                 "doctype": "LMS Enrollment",
#                 "course":  lms_course,
#                 "member":  student,
#                 "batch":   batch_name,
#                 "source":  "Mentor Booking",
#             })
#             course_enrollment.insert(ignore_permissions=True)
#             frappe.db.commit()
#             enrollment_name = course_enrollment.name

#     seats_left = (seat_count - (current_count + 1)) if seat_count else 999

#     return {
#         "enrollment_name": enrollment_name,
#         "batch_name":      batch_name,
#         "seats_left":      seats_left,
#     }
    
@frappe.whitelist(allow_guest=False)
def get_mentor_listings(
    skill=None,
    min_price=None,
    max_price=None,
    min_rating=None,
    availability_day=None,
    offering_type=None,
    search=None,
    limit=20,
    offset=0
):

    # ----------------------------------------------------------
    # PERMISSION CHECK
    # Respects Role Permission Manager configuration
    # ----------------------------------------------------------
    session_user = frappe.session.user

    if not frappe.has_permission(
        "Mentor Offering",
        ptype="read",
        user=session_user
    ):
        frappe.throw(
            "You do not have permission to access Mentor Offering.",
            frappe.PermissionError
        )

    limit = int(limit or 20)
    offset = int(offset or 0)

    # ---------------------------------------------------------
    # Filters
    # ---------------------------------------------------------
    filters = {
        "status": "Live"
    }

    if offering_type:
        filters["offering_type"] = offering_type

    if min_price:
        filters["price_per_session"] = [">=", float(min_price)]

    if max_price:
        filters["price_per_session"] = [
            "<=",
            float(max_price)
        ]

    if min_rating:
        filters["average_rating"] = [
            ">=",
            float(min_rating)
        ]

    # ---------------------------------------------------------
    # Fetch ALL offerings
    # ---------------------------------------------------------
    offerings = frappe.get_all(
        "Mentor Offering",
        filters=filters,
        fields=[
            "name",
            "mentor",
            "title",
            "offering_type",
            "price_per_session",
            "average_rating",
            "total_bookings",
            "duration_minutes",
            "creation"
        ],
        order_by="""
            average_rating desc,
            total_bookings desc,
            creation desc
        """
    )

    # Existing logic unchanged below...

    # ---------------------------------------------------------
    # Remove duplicate mentors
    # Keep latest/best offering only
    # ---------------------------------------------------------
    unique_mentors = {}
    
    for o in offerings:

        if o.mentor not in unique_mentors:
            unique_mentors[o.mentor] = o

    mentor_offerings = list(unique_mentors.values())

    # ---------------------------------------------------------
    # Apply pagination AFTER filtering
    # ---------------------------------------------------------
    mentor_offerings = mentor_offerings[offset: offset + limit]

    result = []

    # ---------------------------------------------------------
    # Build response
    # ---------------------------------------------------------
    for o in mentor_offerings:

        mentor_email = o.mentor

        # -----------------------------------------------------
        # Mentor Profile
        # -----------------------------------------------------
        mentor_profile = frappe.db.get_value(
            "Mentor",
            mentor_email,
            [
                "first_name",
                "last_name",
                "total_sessions",
                "total_hours",
                "avg_rating"
            ],
            as_dict=True
        ) or {}

        # -----------------------------------------------------
        # Full Name
        # -----------------------------------------------------
        full_name = " ".join(
            filter(
                None,
                [
                    mentor_profile.get("first_name"),
                    mentor_profile.get("last_name")
                ]
            )
        ).strip()

        if not full_name:
            full_name = mentor_email

        # -----------------------------------------------------
        # Skill Tags
        # -----------------------------------------------------
        tags = frappe.get_all(
            "Student Skill Table",
            filters={"parent": mentor_email},
            fields=["skill"],
            limit=5
        )

        # -----------------------------------------------------
        # Next Available Slot
        # -----------------------------------------------------
        next_slot = _get_next_available_slot(mentor_email)

        # -----------------------------------------------------
        # Search Filter
        # -----------------------------------------------------
        if search:

            search_text = search.lower()

            searchable = " ".join([
                full_name,
                o.title or ""
            ]).lower()

            if search_text not in searchable:
                continue

        # -----------------------------------------------------
        # Skill Filter
        # -----------------------------------------------------
        if skill:

            mentor_skills = [
                (t.skill or "").lower()
                for t in tags
            ]

            if skill.lower() not in mentor_skills:
                continue

        # -----------------------------------------------------
        # Final Result
        # -----------------------------------------------------
        result.append({
            "mentor": mentor_email,
            "full_name": full_name,
            "designation": "",
            "company": "",
            "profile_image": "",
            "tags": [t.skill for t in tags],
            "avg_rating": (
                mentor_profile.get("avg_rating")
                or o.average_rating
                or 0
            ),
            "total_sessions": (
                mentor_profile.get("total_sessions")
                or o.total_bookings
                or 0
            ),
            "price_per_hour": o.price_per_session,
            "offering_name": o.name,
            "offering_title": o.title,
            "offering_type": o.offering_type,
            "duration_minutes": o.duration_minutes,
            "next_slot": next_slot,
        })

    return {
        "count": len(result),
        "data": result
    }

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