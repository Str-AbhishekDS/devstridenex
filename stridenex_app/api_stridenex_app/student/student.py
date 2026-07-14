import frappe
from stridenex_app.api_stridenex_app.app_utils import (
    gen_response,
    exception_handel
)

import frappe
import time


@frappe.whitelist(allow_guest=True)
def create_student():
    """
    Manual retry loop around a savepoint handles deadlock correctly inside Frappe.
    The @decorator approach does NOT work because Frappe catches 1213 before the
    decorator wrapper sees it.
    """
    max_retries = 3

    for attempt in range(max_retries):
        try:
            return _do_create_student()

        except Exception as e:
            error_str = str(e)

            # Deadlock — rollback to clean state and retry
            if "1213" in error_str or "Deadlock" in error_str:
                frappe.db.rollback()
                if attempt < max_retries - 1:
                    time.sleep(0.1 * (attempt + 1))   # 100ms, 200ms back-off
                    continue
                # All retries exhausted
                return exception_handel(e)

            # Any other error — return immediately
            frappe.db.rollback()
            return exception_handel(e)


def _do_create_student():
    import json
    import re
    # ── Read body based on Content-Type ──────────────────────────────────────
    content_type = frappe.request.content_type or ""

    if "application/json" in content_type:
        # Postman / JSON body — parse raw request data
        raw_data = frappe.request.get_data(as_text=True)
        data = json.loads(raw_data) if raw_data else {}
    else:
        # Form-data / x-www-form-urlencoded
        data = dict(frappe.form_dict)

    email = data.get("email_id")
  

    def _generate_username(email):
        # Use email prefix as username → "ac2@g.com" → "ac2"
        base = re.sub(r'[^a-z0-9_]', '', email.split("@")[0].lower())
        # Ensure it's unique
        username = base
        counter = 1
        while frappe.db.exists("User", {"username": username}):
            username = f"{base}_{counter}"
            counter += 1
        return username
    
    
    # ── Save child table data BEFORE stripping from data ──────────────────────
    def parse_field(key):
        val = data.get(key)
        if isinstance(val, str):
            try:
                return json.loads(val)
            except Exception:
                return []
        return val if isinstance(val, list) else []

    skills        = parse_field("skill")
    career_interests = parse_field("career_interest")
    courses_types = parse_field("courses_type")

    # ── Strip child/file fields from data before passing to Student doc ───────
    for key in list(data.keys()):
        if key.startswith(("skill[", "career_interest[", "courses_type[")):
            data.pop(key)
    data.pop("resume", None)
    data.pop("skill", None)
    data.pop("career_interest", None)
    data.pop("courses_type", None)

    # ── STEP 1: Lock User row first ───────────────────────────────────────────
    if email:
        if frappe.db.exists("User", email):
            frappe.db.sql(
                "SELECT name FROM `tabUser` WHERE name = %s FOR UPDATE",
                (email,)
            )
            user_doc = frappe.get_doc("User", email)
            if "Student" not in [r.role for r in user_doc.roles]:
                user_doc.append("roles", {"role": "Student"})
                user_doc.save(ignore_permissions=True)
        else:
            user_doc = frappe.get_doc({
                "doctype": "User",
                "email": email,
                "first_name": data.get("first_name", ""),
                "last_name": data.get("last_name", ""),
                "enabled": 1,
                "username": _generate_username(email),  # ← fixes the warning
                "send_welcome_email": 0,
                "roles": [{"role": "Student"}]
            })
            user_doc.insert(ignore_permissions=True)

    # ── STEP 2: Build Student doc in memory ───────────────────────────────────
    ALLOWED_FIELDS = {
        "first_name", "last_name", "mobile_no", "stream", "college",
        "course", "department", "academic_year", "semester", "current_year",
        "date_of_birth", "gender", "linkedin", "github", "cgpa", "backlog"
    }

    clean_data = {k: v for k, v in data.items() if k in ALLOWED_FIELDS}

    student = frappe.get_doc({
        "doctype": "Student",
        "name": email,
        "email_id": email,
        "user": email,
        **clean_data
    })

    # ── Append child rows ─────────────────────────────────────────────────────
    for row in skills:
        student.append("skill", {
            "skill": row.get("skill")
        })

    for row in career_interests:
        student.append("career_interest", {
            "career_interest": row.get("career_interest")
        })

    for row in courses_types:
        student.append("courses_type", {
            "course_type": row.get("course_type")
        })

    # ── STEP 3: Single insert ─────────────────────────────────────────────────
    student.insert(ignore_permissions=True)

    # ── STEP 4: File upload ───────────────────────────────────────────────────
    if "resume" in frappe.request.files:
        file_obj = frappe.request.files["resume"]
        file_doc = frappe.get_doc({
            "doctype": "File",
            "file_name": file_obj.filename,
            "attached_to_doctype": "Student",
            "attached_to_name": student.name,
            "content": file_obj.read(),
            "is_private": 1
        })
        file_doc.insert(ignore_permissions=True)

    # ── STEP 5: is_onboarded update ───────────────────────────────────────────
    if email:
        frappe.db.set_value("User", email, "is_onboarded", 2)

    frappe.db.commit()

    return gen_response(
        status=200,
        message="Student registered successfully",
        data={"name": student.name}
    )
    
@frappe.whitelist()
def get_student(name=None, first_name=None, last_name=None, email_id=None, college=None):
    try:
        conditions = []
        values = {}

        if name:
            conditions.append("name = %(name)s")
            values["name"] = name

        if first_name:
            conditions.append("first_name = %(first_name)s")
            values["first_name"] = first_name

        if last_name:
            conditions.append("last_name = %(last_name)s")
            values["last_name"] = last_name

        if email_id:
            conditions.append("email_id = %(email_id)s")
            values["email_id"] = email_id

        if college:
            conditions.append("college = %(college)s")
            values["college"] = college

        where_clause = " AND ".join(conditions)

        sql = f"""
            SELECT name, first_name, last_name, email_id, college
            FROM `tabStudent`
            WHERE docstatus = 1
            {f'AND {where_clause}' if where_clause else ''}
        """

        result = frappe.db.sql(sql, values, as_dict=True)

        if not result:
            return gen_response(404, "No student found.")

        return gen_response(200, "Student fetched successfully.", result)

    except Exception as e:
        return exception_handel(e)
    


@frappe.whitelist(allow_guest=True)
def get_student_by_email(email_id):
    try:
        if not email_id:
            return {
                "status": 400,
                "message": "Email is required",
                "data": {}
            }

        # Fetch record using email
        data = frappe.db.get_value(
            "Student",  
            {"email_id": email_id},
            ["*"],
            as_dict=True
        )

        if not data:
            return {
                "status": 404,
                "message": "No record found",
                "data": {}
            }

        return {
            "status": 200,
            "message": "Data fetched successfully",
            "data": data
        }

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Get Details By Email Error")
        return {
            "status": 500,
            "message": str(e),
            "data": {}
        }
@frappe.whitelist(allow_guest=True)
def update_student(name=None):
    try:
        data = frappe.request.get_json()

        if not name:
            return {"status": 400, "message": "Student name (ID) is required"}

        doc = frappe.get_doc("Student", name)

        # Update only fields that are provided
        fields = [
            "first_name", "middle_name", "last_name",
            "email_id", "mobile_no", "college",
            "department", "course", "semester",
            "academic_year", "date_of_birth","current_year",
            "stream", "linkedin", "github", "gender","cgpa"
        ]

        for field in fields:
            if field in data:
                doc.set(field, data.get(field))

        doc.save(ignore_permissions=True)

        return {
            "status": 200,
            "message": "Student updated successfully",
            "data": doc.name
        }

    except Exception as e:
        return {"status": 500, "message": str(e)}