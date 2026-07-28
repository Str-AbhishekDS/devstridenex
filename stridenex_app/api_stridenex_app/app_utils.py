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
    Paste this object straight into  gen_response data.
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
    
    
import frappe
from frappe.utils import now_datetime, add_to_date, get_datetime

ROLE_STEP_MAP = {
    "Student Base": 2,
    "Mentor": 3,
    "College Base": 4,
    "Industry Base": 3,
}

REMINDER_INTERVAL_DAYS = 2


def send_onboarding_reminders():
    """Runs daily (scheduled). Sends onboarding reminder mail to users
    whose is_onboarded < required steps for their role, throttled to
    once every 2 days using 'User Reminder Tracking' doctype."""

    for role, total_steps in ROLE_STEP_MAP.items():
        users = get_users_with_role(role)

        for user in users:
            user_values = frappe.db.get_value(
                "User", user, ["is_onboarded", "full_name", "enabled"], as_dict=True
            )

            if not user_values or not user_values.enabled:
                continue

            is_onboarded = safe_int(user_values.is_onboarded)

            if is_onboarded >= total_steps:
                continue  # onboarding already complete

            tracking = get_or_create_tracking(user)

            if was_reminded_recently(tracking.last_onboarding_reminder):
                continue  # reminded within last 2 days

            send_reminder_mail(user, role, is_onboarded, total_steps, user_values.full_name)
            update_tracking(tracking)


def get_users_with_role(role):
    return frappe.get_all(
        "Has Role",
        filters={"role": role, "parenttype": "User"},
        pluck="parent",
        distinct=True,
    ) or []


def safe_int(value):
    if value and str(value).strip().isdigit():
        return int(value)
    return 0


def get_or_create_tracking(user):
    """Fetch existing tracking record for user, or create a fresh one."""
    if frappe.db.exists("User Reminder Tracking", {"user": user}):
        return frappe.get_doc("User Reminder Tracking", {"user": user})

    new_doc = frappe.get_doc({
        "doctype": "User Reminder Tracking",
        "user": user,
        "reminder_count": 0,
    })
    new_doc.insert(ignore_permissions=True)
    return new_doc


def was_reminded_recently(last_reminder_datetime):
    if not last_reminder_datetime:
        return False
    cutoff = add_to_date(now_datetime(), days=-REMINDER_INTERVAL_DAYS)
    return get_datetime(last_reminder_datetime) >= cutoff


def update_tracking(tracking_doc):
    tracking_doc.last_onboarding_reminder = now_datetime()
    tracking_doc.reminder_count = (tracking_doc.reminder_count or 0) + 1
    tracking_doc.save(ignore_permissions=True)
    frappe.db.commit()


def send_reminder_mail(user, role, completed, total, full_name=None):
    remaining = total - completed
    user_full_name = full_name or user

    subject = "Action Required: Complete Your Onboarding Process"

    message = f"""
        <div style="margin:0;padding:0;background:#f6f6f8;font-family:'Inter',-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;">
            <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background:#f6f6f8;padding:30px 15px;">
                <tr>
                    <td align="center">

                        <table role="presentation" width="100%" cellspacing="0" cellpadding="0"
                            style="max-width:600px;background:#ffffff;border:1px solid #e2e8f0;border-radius:16px;overflow:hidden;">

                            <!-- Header -->
                            <tr>
                                <td style="background:#0f0fbd;padding:30px;text-align:center;">
                                    <h1 style="margin:0;color:#ffffff;font-size:24px;font-weight:700;">
                                        Complete Your Onboarding
                                    </h1>
                                    <p style="margin:8px 0 0;color:#dbeafe;font-size:14px;">
                                        Action Required to Unlock Full Platform Access
                                    </p>
                                </td>
                            </tr>

                            <!-- Body -->
                            <tr>
                                <td style="padding:32px;">

                                    <p style="margin:0 0 20px;color:#1E293B;font-size:16px;line-height:1.8;">
                                        Hi <strong>{user_full_name}</strong>,
                                    </p>

                                    <p style="margin:0 0 24px;color:#1E293B;font-size:15px;line-height:1.8;">
                                        We noticed that your onboarding process is still incomplete.
                                        Complete the remaining steps to access all features available to your account.
                                    </p>

                                    <!-- Progress Card -->
                                    <div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:12px;padding:20px;margin-bottom:24px;">

                                        <table width="100%" style="border-collapse:collapse;">
                                            <tr>
                                                <td style="padding:8px 0;color:#64748B;font-size:14px;">
                                                    <strong>Role</strong>
                                                </td>
                                                <td style="padding:8px 0;color:#1E293B;font-size:14px;text-align:right;">
                                                    {role}
                                                </td>
                                            </tr>

                                            <tr>
                                                <td style="padding:8px 0;color:#64748B;font-size:14px;">
                                                    <strong>Steps Completed</strong>
                                                </td>
                                                <td style="padding:8px 0;color:#10b981;font-size:14px;font-weight:600;text-align:right;">
                                                    {completed} / {total}
                                                </td>
                                            </tr>

                                            <tr>
                                                <td style="padding:8px 0;color:#64748B;font-size:14px;">
                                                    <strong>Steps Remaining</strong>
                                                </td>
                                                <td style="padding:8px 0;color:#ff6b00;font-size:14px;font-weight:600;text-align:right;">
                                                    {remaining}
                                                </td>
                                            </tr>
                                        </table>

                                    </div>

                                    <!-- Progress Indicator -->
                                    <div style="background:#eef2ff;border-left:4px solid #0f0fbd;padding:16px 18px;border-radius:8px;margin-bottom:24px;">
                                        <p style="margin:0;color:#1E293B;font-size:14px;line-height:1.8;">
                                            Complete the remaining <strong>{remaining}</strong> step(s) to finish onboarding and unlock full access to StrideNex features, opportunities, and recommendations.
                                        </p>
                                    </div>

                                    <!-- Reminder -->
                                    <div style="background:#fff7ed;border-left:4px solid #ff6b00;padding:16px 18px;border-radius:8px;">
                                        <p style="margin:0;color:#9a3412;font-size:14px;line-height:1.8;">
                                            If you've completed your onboarding recently, you may safely ignore this reminder.
                                        </p>
                                    </div>

                                </td>
                            </tr>

                            <!-- Footer -->
                            <tr>
                                <td style="background:#0F172A;padding:24px;text-align:center;">
                                    <p style="margin:0;color:#ffffff;font-size:15px;font-weight:600;">
                                        StrideNex Team
                                    </p>

                                    <p style="margin:10px 0 0;color:#94a3b8;font-size:13px;">
                                        Empowering Skills • Building Careers • Creating Opportunities
                                    </p>

                                    <div style="margin-top:16px;padding-top:16px;border-top:1px solid #334155;">
                                        <p style="margin:0;color:#94a3b8;font-size:12px;">
                                            Complete your onboarding to get the best experience on StrideNex.
                                        </p>
                                    </div>
                                </td>
                            </tr>

                        </table>

                    </td>
                </tr>
            </table>
        </div>
        """

    frappe.sendmail(
        recipients=[user],
        subject=subject,
        message=message,
        reference_doctype="User",
        reference_name=user,
    )