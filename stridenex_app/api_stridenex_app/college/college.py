import frappe
from stridenex_app.api_stridenex_app.app_utils import (
    gen_response,
    exception_handel
)


@frappe.whitelist(allow_guest=True)
def create_college():
    try:
        data = frappe.request.get_json() or {}
        email = data.get("email")
        courses = data.pop("courses", [])

        college = frappe.get_doc({
            "doctype": "College",
            **data
        })

        college.insert(ignore_permissions=True)

        if courses:
            create_college_program_details(college.name, courses)

        if email and frappe.db.exists("User", email):
            if data.get("college_name"):
                onboarding_status = 2
            else:
                onboarding_status = 1 
            frappe.db.set_value("User", email, "is_onboarded", onboarding_status)

        return gen_response(
            status=200,
            message="College registered successfully",
            data={"name": college.college_name}
        )

    except Exception as e:
        return exception_handel(e)

def parse_departments(dept_input):
    """
    Parse a department field into a list of valid single College Department names.
    dept_input can be:
    - a list of department strings: ["Civil", "Robotics"]
    - a single department string: "Civil Engineering"
    - a comma-separated string containing multiple departments: "Electrical Engineering,Computer Engineering,..."
    """
    if not dept_input:
        return []

    if isinstance(dept_input, list):
        depts = []
        for d in dept_input:
            depts.extend(parse_departments(d))
        return list(dict.fromkeys(depts))

    dept_str = str(dept_input).strip()
    if not dept_str:
        return []

    # 1. Direct match
    if frappe.db.exists("College Department", dept_str):
        return [dept_str]

    # 2. Extract valid department names from concatenated string
    all_depts = frappe.get_all("College Department", pluck="name")
    all_depts.sort(key=len, reverse=True)

    found_depts = []
    temp_str = dept_str
    for d in all_depts:
        if d in temp_str:
            found_depts.append(d)
            temp_str = temp_str.replace(d, "")

    if found_depts:
        return list(dict.fromkeys(found_depts))

    # 3. Fallback: split by comma if no DB match found
    split_depts = [s.strip() for s in dept_str.split(",") if s.strip()]
    valid_depts = []
    for d in split_depts:
        if frappe.db.exists("College Department", d):
            valid_depts.append(d)
        else:
            try:
                new_d = frappe.get_doc({
                    "doctype": "College Department",
                    "department_name": d
                })
                new_d.insert(ignore_permissions=True)
                valid_depts.append(new_d.name)
            except Exception:
                pass

    return list(dict.fromkeys(valid_depts))


def create_college_program_details(college_name, courses):
    """
    Create 'College Program Details' records for a given college.
    - Deletes previously linked records (cancelling submitted ones first)
    - Creates a new record per course and department combination
    - Submits each record since the doctype is submittable (is_submittable=1)
    """
    if not courses:
        return []

    if isinstance(courses, str):
        try:
            courses = frappe.parse_json(courses)
        except Exception:
            courses = []

    # 1. Clean up existing program detail records linked to this college
    existing_records = frappe.get_all(
        "College Program Details",
        filters={"college": college_name},
        fields=["name", "docstatus"]
    )

    for row in existing_records:
        try:
            doc = frappe.get_doc("College Program Details", row.name)
            if doc.docstatus == 1:
                doc.flags.ignore_permissions = True
                doc.cancel()
            frappe.delete_doc(
                "College Program Details",
                row.name,
                ignore_permissions=True,
                force=True
            )
        except Exception as e:
            frappe.log_error(f"Error deleting College Program Detail {row.name}: {e}")

    # 2. Create new records
    created_records = []

    for course_row in courses:
        if not isinstance(course_row, dict):
            continue

        c_type = course_row.get("course_type")
        c_stream = course_row.get("stream")
        c_course = course_row.get("course")
        dept_raw = course_row.get("department")

        departments = parse_departments(dept_raw)
        if not departments:
            departments = [None]

        for dept in departments:
            try:
                program_doc = frappe.new_doc("College Program Details")
                program_doc.flags.ignore_permissions = True

                program_doc.college = college_name
                program_doc.course_type = c_type
                program_doc.stream = c_stream
                program_doc.course = c_course
                program_doc.department = dept

                program_doc.insert(ignore_permissions=True)
                if program_doc.meta.is_submittable and program_doc.docstatus == 0:
                    program_doc.submit()
                else:
                    program_doc.save(ignore_permissions=True)

                created_records.append(program_doc.name)
            except Exception as exc:
                frappe.log_error(f"Error creating College Program Detail for {c_course} - {dept}: {exc}")

    return created_records



@frappe.whitelist(allow_guest=True)
def update_college(email):
    try:
        data = None
        if frappe.request and hasattr(frappe.request, "get_json"):
            try:
                data = frappe.request.get_json()
            except Exception:
                pass

        if not data:
            data = frappe.form_dict.copy() if frappe.form_dict else {}

        if not data:
            return gen_response(
                status=400,
                message="Invalid request data"
            )

        # Find College by email
        college_name = frappe.db.get_value(
            "College",
            {"email": email},
            "name"
        )

        if not college_name:
            return gen_response(
                status=404,
                message="College not found"
            )

        contact_details = data.pop("contact_details", [])
        courses = data.pop("courses", []) 
       

        college = frappe.get_doc("College", college_name)
        college.flags.ignore_permissions = True

        # Update parent fields
        for key, value in data.items():
            if frappe.get_meta("College").has_field(key):
                college.set(key, value)

        # Update child table
        if contact_details:
            college.set("contact_details", [])

            for row in contact_details:
                designation = row.get("designation")
                if designation and not frappe.db.exists("Designation", designation):
                    try:
                        des_doc = frappe.get_doc({
                            "doctype": "Designation",
                            "designation_name": designation
                        })
                        des_doc.insert(ignore_permissions=True)
                    except Exception:
                        pass

                contact_no = str(row.get("contact_no") or "").strip()
                if contact_no and not contact_no.startswith("+"):
                    contact_no = f"+91-{contact_no}"

                mapped_row = {
                    "salutation": row.get("title"),
                    "first_name": row.get("first_name"),
                    "last_name": row.get("last_name"),
                    "designation": designation if (designation and frappe.db.exists("Designation", designation)) else None,
                    "contact_no": contact_no,
                    "email": row.get("email"),
                    "is_admin": row.get("is_admin", 0),
                }
                college.append("contact_details", mapped_row)

            create_college_users(contact_details)

        college.save(ignore_permissions=True)
    
        if courses:
            create_college_program_details(college.name, courses)

        # Update onboarding status
        user_email = college.email

        if user_email and frappe.db.exists("User", user_email):
            onboarding_status = 0

            if college.country:
                onboarding_status = 3

            if contact_details:
                onboarding_status = 4

            frappe.db.set_value(
                "User",
                user_email,
                "is_onboarded",
                onboarding_status
            )

        frappe.db.commit()

        return gen_response(
            status=200,
            message="College updated successfully",
            data={
                "name": college.name,
                "college_name": college.college_name,
                "email": college.email
            }
        )

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Update College Error")
        return exception_handel(e)




def create_college_users(contact_details):

    for contact in contact_details:

        email = contact.get("email")
        if not email:
            continue
        if frappe.db.exists("User", email):
            continue

        is_admin = int(contact.get("is_admin", 0))
        role = "College Admin" if is_admin == 1 else "College Base"

        # User already exists
        if frappe.db.exists("User", email):
            user = frappe.get_doc("User", email)

            user.salutation = contact.get("title")
            user.first_name = contact.get("first_name")
            user.last_name = contact.get("last_name")
            user.mobile_no = contact.get("contact_no")

            existing_roles = [r.role for r in user.roles]

            if role not in existing_roles:
                user.append("roles", {"role": role})

            user.save(ignore_permissions=True)
            continue

        # Create new user
        user = frappe.get_doc({
            "doctype": "User",
            "email": email,
            "salutation":contact.get("title"),
            "first_name": contact.get("first_name"),
            "last_name": contact.get("last_name"),
            "mobile_no": contact.get("contact_no"),
            "send_welcome_email": 0,
            "roles": [
                {"role": "College Base"}
            ]
        })

        user.insert(ignore_permissions=True)

    return True


@frappe.whitelist(allow_guest=True)
def get_college(email):
    try:
        college_name = frappe.db.get_value(
            "College",
            {"email": email},
            "name"
        )

        if not college_name:
            return gen_response(
                status=404,
                message="College not found"
            )

        college = frappe.get_doc("College", college_name)

        # Get user details
        user_details = frappe.db.get_value(
            "User",
            email,
            ["first_name", "last_name", "mobile_no"],
            as_dict=True
        )

        data = college.as_dict()
        data["user_details"] = user_details or {}

        # Include saved courses / program details
        program_details = frappe.get_all(
            "College Program Details",
            filters={"college": college_name},
            fields=["name", "course_type", "stream", "course", "department"]
        )
        data["courses"] = program_details or []

        return gen_response(
            status=200,
            message="College fetched successfully",
            data=data
        )

    except Exception as e:
        return exception_handel(e)
    
    
    
    """
employability_report.py

Whitelisted API endpoints for college-level Employability reporting.

Location in your app:
    apps/stridenex_app/stridenex_app/api/employability_report.py

(Create the `api` folder + an empty `__init__.py` inside it if it
doesn't exist yet — see setup notes at the bottom of this file.)

Categories (bucketed by employability_score, 0-100 scale):

    Critical            : score < 40
    High Risk           : 40 <= score < 55
    Declining Progress  : 55 <= score < 75
    Placement Ready      : score >= 75

Ranges are half-open on the lower bound and exclusive on the upper
bound (except the top bucket) so every score falls into EXACTLY one
category — no double-counting at the boundaries (e.g. a score of
exactly 55 lands in "Declining Progress", not "High Risk").

ASSUMPTION: Student doctype has a field called `college` (Link).
If your fieldname differs, change COLLEGE_FIELD below — nothing else
needs to change.
"""

import frappe

# ---------------------------------------------------------------------
# CONFIG
# ---------------------------------------------------------------------

COLLEGE_FIELD = "college"  # change if your Student doctype uses a different fieldname
SCORE_FIELD = "employability_score"

THRESHOLDS = {
    "critical": (0, 40),              # score < 40
    "high_risk": (40, 55),            # 40 <= score < 55
    "declining_progress": (55, 75),   # 55 <= score < 75
    "placement_ready": (75, 100.0001) # score >= 75 (upper bound padded to include 100)
}

CATEGORY_LABELS = {
    "critical": "Critical",
    "high_risk": "High Risk",
    "declining_progress": "Declining Progress",
    "placement_ready": "Placement Ready",
}

STUDENT_LIST_FIELDS = [
    "name",
    "email_id",
    COLLEGE_FIELD,
    SCORE_FIELD,
    "cgpa",
]


def resolve_college_name(college):
    if not college:
        return college
    if "@" in college:
        resolved = frappe.db.get_value("College", {"email": college}, "name")
        if resolved:
            return resolved
    return college


def _get_students_in_range(category: str, college: str = None):
    """Returns student rows strictly within the category's score range."""
    college = resolve_college_name(college)
    low, high = THRESHOLDS[category]

    conditions = [f"`{SCORE_FIELD}` >= %(low)s"]
    values = {"low": low}

    if category != "placement_ready":
        conditions.append(f"`{SCORE_FIELD}` < %(high)s")
        values["high"] = high

    if category == "critical":
        # no lower bound needed, just score < 40
        conditions = [f"`{SCORE_FIELD}` < %(high)s"]
        values = {"high": high}

    if college:
        conditions.append(f"`{COLLEGE_FIELD}` = %(college)s")
        values["college"] = college

    where_clause = " AND ".join(conditions)

    students = frappe.db.sql(
        f"""
        SELECT name email_id, {COLLEGE_FIELD} as college,
               {SCORE_FIELD} as employability_score, cgpa
        FROM `tabStudent`
        WHERE {where_clause}
        ORDER BY {SCORE_FIELD} ASC
        """,
        values,
        as_dict=True,
    )
    return students


# ---------------------------------------------------------------------
# PUBLIC API — CATEGORY STUDENT LISTS
# ---------------------------------------------------------------------

@frappe.whitelist()
def get_students_by_category(category: str, college: str = None):
    """
    Returns the list of students + count for ONE category.

    category: one of "critical" | "high_risk" | "declining_progress" | "placement_ready"
    college : optional, filters to a single college. Omit for all colleges.

    Example call from client:
        frappe.call({
            method: "stridenex_app.api.employability_report.get_students_by_category",
            args: { category: "critical", college: "COL-0001" }
        })
    """
    category = (category or "").strip().lower()
    if category not in THRESHOLDS:
        frappe.throw(
            "Invalid category. Must be one of: "
            + ", ".join(THRESHOLDS.keys())
        )

    students = _get_students_in_range(category, college)

    return {
        "category": category,
        "label": CATEGORY_LABELS[category],
        "college": college,
        "count": len(students),
        "students": students,
    }


@frappe.whitelist()
def get_critical_students(college: str = None):
    """Convenience wrapper: score < 40"""
    return get_students_by_category("critical", college)


@frappe.whitelist()
def get_high_risk_students(college: str = None):
    """Convenience wrapper: 40 <= score < 55"""
    return get_students_by_category("high_risk", college)


@frappe.whitelist()
def get_declining_progress_students(college: str = None):
    """Convenience wrapper: 55 <= score < 75"""
    return get_students_by_category("declining_progress", college)


@frappe.whitelist()
def get_placement_ready_students(college: str = None):
    """Convenience wrapper: score >= 75"""
    return get_students_by_category("placement_ready", college)


# ---------------------------------------------------------------------
# PUBLIC API — COLLEGE-WISE SUMMARY (counts only, for dashboards)
# ---------------------------------------------------------------------

@frappe.whitelist(allow_guest= True)
def get_college_employability_summary(college: str = None):
    """
    Returns counts (not full lists) per category.

    If `college` is passed -> summary for that one college.
    If omitted -> summary broken down per college, plus a grand total.

    Example response (single college):
    {
        "college": "COL-0001",
        "total_students": 240,
        "critical": 12,
        "high_risk": 30,
        "declining_progress": 90,
        "placement_ready": 108
    }

    Example response (all colleges):
    {
        "colleges": [
            {"college": "COL-0001", "total_students": 240, "critical": 12, ...},
            {"college": "COL-0002", "total_students": 180, "critical": 5, ...}
        ],
        "grand_total": {
            "total_students": 420, "critical": 17, "high_risk": 55,
            "declining_progress": 150, "placement_ready": 198
        }
    }
    """
    college = resolve_college_name(college)
    if college:
        return _summary_for_college(college)

    colleges = frappe.get_all(
        "Student",
        distinct=True,
        pluck=COLLEGE_FIELD,
        filters={COLLEGE_FIELD: ["is", "set"]},
    )

    result = []
    grand_total = {
        "total_students": 0,
        "critical": 0,
        "high_risk": 0,
        "declining_progress": 0,
        "placement_ready": 0,
    }

    for c in colleges:
        summary = _summary_for_college(c)
        result.append(summary)
        grand_total["total_students"] += summary["total_students"]
        for key in ("critical", "high_risk", "declining_progress", "placement_ready"):
            grand_total[key] += summary[key]

    return {"colleges": result, "grand_total": grand_total}


def _summary_for_college(college: str) -> dict:
    counts = {"college": college}
    total = 0
    for category in THRESHOLDS.keys():
        students = _get_students_in_range(category, college)
        counts[category] = len(students)
        total += len(students)
    counts["total_students"] = total
    return counts