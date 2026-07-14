import random
import time

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

# ============================================================
# SHARED HELPER — call this at the end of every module update
# ============================================================
def sync_billing_account_master(email, data=None, module_type=None):
    """
    Finds the Billing Account Master record by email and updates
    the fields relevant for invoice generation.

    Args:
        email       : the user's email (used as the BAM name/key)
        data        : the raw request dict (used to pull address fields etc.)
        module_type : "mentor" | "student" | "college" | "industry"
                      used to derive account_type where needed
    """
    if not email or not frappe.db.exists("Billing Account Master", email):
        return  # nothing to sync; record may not exist yet

    data = data or {}
    bam  = frappe.get_doc("Billing Account Master", email)
    bam.flags.ignore_permissions = True

    # ── account type ──────────────────────────────────────────
    if module_type in ("college", "industry"):
        bam.account_type = "Organization"
    elif module_type in ("mentor", "student"):
        bam.account_type = "Individual"

    # ── name fields ───────────────────────────────────────────
    for field in ("first_name", "middle_name", "last_name"):
        if data.get(field) is not None:
            bam.set(field, data[field])

    # rebuild full_name if any name part was updated
    name_parts = [
        bam.first_name or "",
        bam.middle_name or "",
        bam.last_name  or "",
    ]
    bam.full_name = " ".join(p for p in name_parts if p).strip()

    # ── company / organisation name ───────────────────────────
    # College uses "college_name", Industry uses "company_name",
    # Mentor/Student don't have a company field — just skip.
    for src_field in ("company_name", "college_name"):
        if data.get(src_field) is not None:
            bam.company_name = data[src_field]
            break

    # ── country ───────────────────────────────────────────────
    if data.get("country") is not None:
        bam.country = data["country"]

    # ── address ───────────────────────────────────────────────
    # Industry sends address inside a nested "location" dict;
    # other modules send flat fields.
    location = data.get("location", {}) if isinstance(data.get("location"), dict) else {}

    addr_map = {
        "address_line_1": "address_line1",   # Industry/location key → BAM field
        "address_line_2": "address_line2",
        "pincode":        "pincode",
        "address_line1":  "address_line1",   # flat key (college/mentor/student)
        "address_line2":  "address_line2",
        "city":           "city",
        "state":          "state",
    }

    # Flat fields first, then location dict overrides (industry)
    for src, dest in addr_map.items():
        if data.get(src) is not None:
            bam.set(dest, data[src])
    for src, dest in addr_map.items():
        if location.get(src) is not None:
            bam.set(dest, location[src])
            
    if data.get("gst_number") is not None:
        bam.gstin = data["gst_number"]

    bam.save(ignore_permissions=True)
    frappe.db.commit()
    
    
    
    
def _process_student_job(data, resume_bytes=None, resume_filename=None):
    """
    Runs inside a background worker.
    Retries up to 3 times on deadlock (MySQL error 1213).
    Tables are always touched in the same order:
        Student → User → File
    This fixed order eliminates the circular-wait condition that causes deadlocks.
    """
    max_retries = 3
    for attempt in range(max_retries):
        try:
            _do_create_student(data, resume_bytes, resume_filename)
            return  # success — exit retry loop
        except Exception as e:
            is_deadlock = "1213" in str(e) or "Deadlock" in str(e)
            if is_deadlock and attempt < max_retries - 1:
                # Exponential backoff with jitter: 0.1s, 0.2s, 0.4s …
                delay = (0.1 * (2 ** attempt)) + random.uniform(0, 0.05)
                frappe.logger().warning(
                    f"Deadlock on attempt {attempt + 1}, retrying in {delay:.2f}s"
                )
                time.sleep(delay)
                frappe.db.rollback()   # clean slate before retry
            else:
                frappe.log_error(
                    title="Student Job Failed",
                    message=frappe.get_traceback()
                )
                raise


def _do_create_student(data, resume_bytes=None, resume_filename=None):
    """
    All DB work in one transaction, tables locked in fixed order:
    1. Student  2. User  3. File
    Never deviate from this order — that's what prevents deadlocks.
    """
    email = data.get("email_id")

    # Clean up fields that are handled separately
    data = {k: v for k, v in data.items()
            if k not in ("resume", "skill", "career_interest", "courses_type")}

    # ── LOCK ORDER 1: Student ────────────────────────────────────────────────
    student = frappe.get_doc({"doctype": "Student", **data})

    skills  = frappe.form_dict.getlist("skill[0][skill]") if hasattr(frappe, "form_dict") else []
    careers = frappe.form_dict.getlist("career_interest[0][career_interest]") if hasattr(frappe, "form_dict") else []
    courses = frappe.form_dict.getlist("courses_type[0][course_type]") if hasattr(frappe, "form_dict") else []

    for s in skills:
        student.append("skill", {"skill": s})
    for c in careers:
        student.append("career_interest", {"career_interest": c})
    for c in courses:
        student.append("courses_type", {"course_type": c})

    student.insert(ignore_permissions=True)

    # ── LOCK ORDER 2: User ───────────────────────────────────────────────────
    if email:
        _upsert_user(student, email)

    # ── LOCK ORDER 3: File ───────────────────────────────────────────────────
    if resume_bytes and resume_filename:
        file_doc = frappe.get_doc({
            "doctype": "File",
            "file_name": resume_filename,
            "attached_to_doctype": "Student",
            "attached_to_name": student.name,
            "content": resume_bytes,
        })
        file_doc.save(ignore_permissions=True)

    frappe.db.commit()


def _upsert_user(student, email):
    """Separated so lock order is obvious at a glance."""
    if frappe.db.exists("User", email):
        user = frappe.get_doc("User", email)
        if "Student" not in [r.role for r in user.roles]:
            user.append("roles", {"role": "Student"})
            user.save(ignore_permissions=True)
        frappe.db.set_value("User", email, "is_onboarded", 2)
    else:
        user = frappe.get_doc({
            "doctype": "User",
            "email": email,
            "first_name": student.first_name,
            "last_name": student.last_name,
            "enabled": 1,
            "send_welcome_email": 0,
            "roles": [{"role": "Student"}],
        })
        user.insert(ignore_permissions=True)

    student.user = email
    student.save(ignore_permissions=True)