import frappe
from bs4 import BeautifulSoup
from frappe import _
from frappe.utils import cstr
from frappe.utils import now_datetime, nowdate
from frappe import cache
import hashlib
import json


def gen_response(status, message, data=None):
    if data is None:
        data = []

    frappe.response["http_status_code"] = status
    frappe.response["status"] = status

    if status == 500:
        frappe.response["message"] = BeautifulSoup(str(message)).get_text()
    else:
        frappe.response["message"] = message

    frappe.response["data"] = data


def exception_handel(e):
    frappe.log_error(title="Backend Error", message=frappe.get_traceback())
    if hasattr(e, "http_status_code"):
        return gen_response(e.http_status_code, cstr(e))
    else:
        return gen_response(500, cstr(e))


def generate_key(user):
    user_details = frappe.get_doc("User", user)
    api_secret = api_key = ""
    if not user_details.api_key and not user_details.api_secret:
        api_secret = frappe.generate_hash(length=15)
        api_key = frappe.generate_hash(length=15)
        user_details.api_key = api_key
        user_details.api_secret = api_secret
        user_details.save(ignore_permissions=True)
    else:
        api_secret = user_details.get_password("api_secret")
        api_key = user_details.get("api_key")
    return {"api_secret": api_secret, "api_key": api_key}


def prepare_json_data(key_list, data):
    return_data = {}
    for key in data:
        if key in key_list:
            return_data[key] = data.get(key)
    return return_data


@frappe.whitelist()
def delete_expired_otps():
    current_time = now_datetime()

    expired_records = frappe.get_all(
        "Validate Email OTP",
        filters={"expiry_time": ["<", current_time]},
        pluck="name"
    )

    for record in expired_records:
        frappe.delete_doc("Validate Email OTP", record, ignore_permissions=True)

    # Same for Mobile OTP (if you have separate doctype)
    expired_mobile = frappe.get_all(
        "Validate Mobile OTP",
        filters={"expiry_time": ["<", current_time]},
        pluck="name"
    )

    for record in expired_mobile:
        frappe.delete_doc("Validate Mobile OTP", record, ignore_permissions=True)

    frappe.db.commit()
    
    
    # stridenex_app/utils/lms_utils.py
# ─────────────────────────────────────────────────────────────────────────────
# All Frappe LMS integration helpers used by Mentor Offering & Session Booking
# ─────────────────────────────────────────────────────────────────────────────


# ─────────────────────────────────────────────────────────────────────────────
# LMS Batch helpers
# ─────────────────────────────────────────────────────────────────────────────
def get_batch_seat_info(batch_name):
    """
    Return seat info using LMS Batch Enrollment doctype (not child table).
    LMS Batch field is seat_count (not max_participants).
    """
    seat_count = frappe.db.get_value("LMS Batch", batch_name, "seat_count") or 0
    seat_count = int(seat_count)

    current_count = frappe.db.count(
        "LMS Batch Enrollment",
        filters={"batch": batch_name}
    )

    seats_left = (seat_count - current_count) if seat_count else 999

    return {
        "seat_count":    seat_count,
        "current_count": current_count,
        "seats_left":    seats_left,
        "is_full":       seat_count > 0 and current_count >= seat_count,
    }


def is_student_in_batch(batch_name, student_email):
    """
    Check via LMS Batch Enrollment doctype.
    Field is 'member' (Link → User), not 'student'.
    """
    return frappe.db.exists(
        "LMS Batch Enrollment",
        {"batch": batch_name, "member": student_email}
    )


def add_student_to_batch(batch_name, student_email):
    """
    Enroll student by creating an LMS Batch Enrollment record.
    LMS Batch Enrollment is a standalone doctype — NOT a child table.
    Fields: batch (Link→LMS Batch), member (Link→User).
    """
    info = get_batch_seat_info(batch_name)

    if info["is_full"]:
        frappe.throw(_("This batch is full. No seats available."))

    if is_student_in_batch(batch_name, student_email):
        frappe.throw(_("You are already enrolled in this batch."))

    # Create standalone LMS Batch Enrollment record
    enrollment = frappe.get_doc({
        "doctype": "LMS Batch Enrollment",
        "batch":   batch_name,
        "member":  student_email,
    })
    enrollment.insert(ignore_permissions=True)
    frappe.db.commit()


def remove_student_from_batch(batch_name, student_email):
    """
    Delete the LMS Batch Enrollment record on booking cancellation.
    """
    enrollment_name = frappe.db.get_value(
        "LMS Batch Enrollment",
        {"batch": batch_name, "member": student_email},
        "name"
    )

    if enrollment_name:
        frappe.delete_doc(
            "LMS Batch Enrollment",
            enrollment_name,
            ignore_permissions=True
        )
        frappe.db.commit()

# ─────────────────────────────────────────────────────────────────────────────
# LMS Enrollment helpers
# ─────────────────────────────────────────────────────────────────────────────

def get_or_create_course_enrollment(course, student_email, batch=None):
    """
    Ensure an LMS Enrollment record exists for (course, student).
    Returns the enrollment name.
    """
    existing = frappe.db.get_value(
        "LMS Enrollment",
        {"course": course, "member": student_email},
        "name",
    )
    if existing:
        return existing

    enrollment = frappe.get_doc({
        "doctype":  "LMS Enrollment",
        "course":   course,
        "member":   student_email,
        "batch":    batch,
        "source":   "Mentor Booking",
    })
    enrollment.insert(ignore_permissions=True)
    frappe.db.commit()
    return enrollment.name


# ─────────────────────────────────────────────────────────────────────────────
# Batch listing  (used by JS slot picker)
# ─────────────────────────────────────────────────────────────────────────────

@frappe.whitelist()
def get_open_batches_for_offering(offering):
    """
    Return LMS Batches linked to this offering's LMS Course that:
      - are published
      - have a start_date >= today  OR  are currently running
      - have seats available
    Called from mentor_session_booking.js batch picker.
    """
    if not offering:
        frappe.throw(_("Offering is required."))

    # lms_course = frappe.db.get_value("Mentor Offering", offering, "lms_course")
    # if not lms_course:
    #     frappe.throw(
    #         _("No LMS Course linked to this offering. Please link a course first.")
    #     )

    today = nowdate()

    batches = frappe.get_all(
        "LMS Batch",
        filters={
            # "courses.course": lms_course,   # child table filter
            "published":      1,
            "end_date":       [">=", today],
        },
        fields=[
            "name", "title", "start_date", "end_date",
            "seat_count", "description", "meta_image",
        ],
        order_by="start_date asc",
    )

    result = []
    for b in batches:
        info = get_batch_seat_info(b.name)
        if info["is_full"]:
            continue   # skip full batches

        b["seats_left"]     = info["seats_left"]
        b["current_count"]  = info["current_count"]
        result.append(b)

    return result


@frappe.whitelist()
def enroll_student_in_batch(offering, batch_name, student):
    """
    Full enrollment flow called when a student joins a Group Session:
      1. Seat check
      2. Add to LMS Batch → Batch Student
      3. Create LMS Enrollment for the course
      4. Return enrollment nameenroll_student_in_batch
    """
    if not frappe.has_permission("Mentor Session Booking", "create"):
        frappe.throw(_("Permission denied."), frappe.PermissionError)

    offering_doc = frappe.get_doc("Mentor Offering", offering)
    lms_course   = offering_doc.lms_course

    if not lms_course:
        frappe.throw(_("No LMS Course linked to this offering."))


    add_student_to_batch(batch_name, student)   # raises if full / duplicate

    # ── LMS Course enrollment ───────────────────────────────────────
    enrollment_name = get_or_create_course_enrollment(lms_course, student, batch=batch_name)

    return {
        "enrollment_name": enrollment_name,
        "batch_name":      batch_name,
        "seats_left":      get_batch_seat_info(batch_name)["seats_left"],
    }

    
@frappe.whitelist()
def append_child_rows(doc, table_field, values, child_key):
    for val in values:
        value = val if isinstance(val, str) else val.get(child_key)

        doc.append(table_field, {
            child_key: value
        })



# ─── Config ────────────────────────────────────────────────────────────────────
CACHE_TTL   = 300   # seconds (5 min) — change per endpoint as needed
DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE     = 100


# ─── Helpers ───────────────────────────────────────────────────────────────────

# ─── Helpers ───────────────────────────────────────────────────────────────────

def make_cache_key(*args, **kwargs) -> str:
    """Stable cache key from any args/kwargs."""
    raw = json.dumps({"args": args, "kwargs": kwargs}, sort_keys=True, default=str)
    return "api_cache:" + hashlib.md5(raw.encode()).hexdigest()


def get_pagination_params(page=1, page_size=DEFAULT_PAGE_SIZE):
    """
    Parse and validate pagination inputs.
    Returns (page, page_size, limit, offset).
    Call this at the top of any endpoint.
    """
    page      = max(1, int(page or 1))
    page_size = max(1, min(int(page_size or DEFAULT_PAGE_SIZE), MAX_PAGE_SIZE))
    limit     = page_size
    offset    = (page - 1) * page_size
    return page, page_size, limit, offset


def make_pagination_meta(total: int, page: int, page_size: int) -> dict:
    """
    Build the pagination block returned in every response.
    Paste this object straight into your gen_response data.
    """
    total_pages = max(1, -(-total // page_size))   # ceiling division
    return {
        "total":       total,
        "page":        page,
        "page_size":   page_size,
        "total_pages": total_pages,
        "has_next":    page < total_pages,
        "has_prev":    page > 1,
        "next_page":   page + 1 if page < total_pages else None,
        "prev_page":   page - 1 if page > 1 else None,
    }

