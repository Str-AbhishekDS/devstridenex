import frappe
from stridenex_app.api_stridenex_app.app_utils import (
    gen_response,
    exception_handel
)


@frappe.whitelist(allow_guest=True)
def create_college():
    try:
        data = frappe.request.get_json()
        email = data.get("email")

        

        college = frappe.get_doc({
            "doctype": "College",
            **data
        })

        college.insert(ignore_permissions=True)

        
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


@frappe.whitelist(allow_guest=True)
def update_college(email):
    try:
        data = frappe.request.get_json()

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
                # Remap 'title' to 'salutation' if your child table field is named 'salutation'
                mapped_row = {
                    "salutation": row.get("title"),       # <-- key fix here
                    "first_name": row.get("first_name"),
                    "last_name": row.get("last_name"),
                    "designation": row.get("designation"),
                    "contact_no": row.get("contact_no"),
                    "email": row.get("email"),
                    "is_admin": row.get("is_admin", 0),
                }
                college.append("contact_details", mapped_row)

            create_college_users(contact_details)

        college.save(ignore_permissions=True)

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


# ---------------------------------------------------------------------
# INTERNAL HELPERS
# ---------------------------------------------------------------------

def _get_students_in_range(category: str, college: str = None):
    """Returns student rows strictly within the category's score range."""
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