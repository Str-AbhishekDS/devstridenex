import frappe
from stridenex_app.api_stridenex_app.app_utils import (
    gen_response,
    exception_handel
)

import frappe
import time
import frappe
from frappe.utils.pdf import get_pdf
from frappe import _


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
    try:
        student.insert(ignore_permissions=True)
    except Exception:
        frappe.log_error(
            frappe.get_traceback(),
            "Student Creation Error"
        )
        raise

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
    


import frappe
from frappe.utils import get_url

@frappe.whitelist(allow_guest=True)
def get_student_by_email(email_id):
    try:
        if not email_id:
            return {
                "status": 400,
                "message": "Email is required",
                "data": {}
            }

        name = frappe.db.get_value("Student", {"email_id": email_id}, "name")

        if not name:
            return {
                "status": 404,
                "message": "No record found",
                "data": {}
            }

        doc = frappe.get_doc("Student", name)
        data = doc.as_dict()

        # Parent-level image/attach fields — update these fieldnames to match your Student doctype
        parent_image_fields = ["student_image", "profile_picture"]
        for f in parent_image_fields:
            if data.get(f):
                data[f] = get_url(data.get(f))

        # Child table image/attach fields — update fieldnames to match your child doctypes
        child_image_fields = {
            "certificates": ["certificate_name","certificate_file"],
            "resume_details": [],  
            "internship": [],
            "project": [],
        }

        for child_fieldname, attach_fields in child_image_fields.items():
            rows = data.get(child_fieldname) or []
            for row in rows:
                for af in attach_fields:
                    if row.get(af):
                        row[af] = get_url(row.get(af))

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
def update_student(name=None, email_id=None):
    try:
        data = frappe.request.get_json()

        if not name and not email_id:
            return {"status": 400, "message": "Student name or email_id is required"}

        if not name:
            name = frappe.db.get_value("Student", {"email_id": email_id}, "name")
            if not name:
                return {"status": 404, "message": "No student found for this email"}

        doc = frappe.get_doc("Student", name)

        # ---- Simple parent fields ----
        fields = [
            "first_name", "middle_name", "last_name",
            "email_id", "mobile_no", "college",
            "department", "course", "semester",
            "academic_year", "date_of_birth", "current_year",
            "stream", "linkedin", "github", "gender", "cgpa", "backlog"
        ]

        for field in fields:
            if field in data:
                doc.set(field, data.get(field))

        # ---- Parent-level image/attach field ----
        if "resume" in data:
            doc.set("resume", data.get("resume"))

        # ---- Child tables (verified against actual GET response) ----
        child_tables = {
            "table_apwt": [
                "education_level", "institution_name", "board_university",
                "specialization", "passing_year", "percentage_cgpa", "grade",
                "education_certificate"
            ],
            "certificates": [
                "certificate_name", "issuing_organization",
                "issue_date", "expiry_date", "credential_id",
                "credential_url", "certificate_file"
            ],
            "internship": [
                "company_name", "job_title", "employment_type",
                "location", "start_date", "end_date", "currently_working",
                "duration", "mentor_name", "technologies", "description",
                "internship_certificate"
            ],
            "project": [
                "project_name", "company_name",
                "start_date", "end_date", "project_description"
            ],
            "courses_type": ["course_type"],
            "skill": ["skill", "level"],
            "career_interest": ["career_interest"],
        }

        for table_fieldname, row_fields in child_tables.items():
            if table_fieldname in data:
                doc.set(table_fieldname, [])
                for row in data.get(table_fieldname) or []:
                    row_data = {f: row.get(f) for f in row_fields if f in row}
                    doc.append(table_fieldname, row_data)

        doc.save(ignore_permissions=True)
        frappe.db.commit()

        return {
            "status": 200,
            "message": "Student updated successfully",
            "data": doc.name
        }

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Update Student Error")
        return {"status": 500, "message": str(e)}





@frappe.whitelist(allow_guest=True)
def get_student_resume(student, template):

    if not student:
        frappe.throw("Student is required")

    if not template:
        frappe.throw("Template is required")

    if not frappe.db.exists("Student", student):
        frappe.throw("Student not found", frappe.DoesNotExistError)

    doc = frappe.get_doc("Student", student)

    template_path = f"stridenex_app/templates/{template}.html"

    html = frappe.render_template(
        template_path,
        {"doc": doc}
    )

    pdf = get_pdf(html)

    frappe.local.response.filename = (
        f"{doc.first_name}_{doc.last_name}_Resume.pdf"
    )
    frappe.local.response.filecontent = pdf
    frappe.local.response.type = "download"

