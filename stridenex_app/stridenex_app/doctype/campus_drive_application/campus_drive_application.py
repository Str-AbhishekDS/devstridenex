# Copyright (c) 2026, QTPL and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
import re
from stridenex_app.api_stridenex_app.app_utils import (
    gen_response,
    exception_handel,get_pagination_params,make_pagination_meta
)

class CampusDriveApplication(Document):
	pass



@frappe.whitelist(allow_guest=True)
def get_placement_counts(college=None, name=None):
    try:
        # Build base conditions dynamically
        conditions = []
        values = []

        if college:
            conditions.append("college = %s")
            values.append(college)

        if name:
            conditions.append("drive = %s")   # ← name is drive name, filter on drive field
            values.append(name)

        where_clause = ("AND " + " AND ".join(conditions)) if conditions else ""

        # Placed (Selected) count
        placed = frappe.db.sql(f"""
            SELECT COUNT(*)
            FROM `tabCampus Drive Application`
            WHERE status = 'Selected'
            {where_clause}
        """, values)[0][0]

        # Shortlisted count
        shortlisted = frappe.db.sql(f"""
            SELECT COUNT(*)
            FROM `tabCampus Drive Application`
            WHERE status = 'Shortlisted'
            {where_clause}
        """, values)[0][0]

        # Applied count
        applied = frappe.db.sql(f"""
            SELECT COUNT(*)
            FROM `tabCampus Drive Application`
            WHERE status = 'Applied'
            {where_clause}
        """, values)[0][0]

        # All students
        student_conditions = []
        student_values = []

        if college:
            student_conditions.append("college = %s")
            student_values.append(college)

        if name:
            student_conditions.append("name = %s")
            student_values.append(name)

        student_where = ("WHERE " + " AND ".join(student_conditions)) if student_conditions else ""

        all_students = frappe.db.sql(f"""
            SELECT COUNT(*)
            FROM `tabStudent`
            {student_where}
        """, student_values)[0][0]

        # Distinct students who applied
        students_applied = frappe.db.sql(f"""
            SELECT COUNT(DISTINCT student)
            FROM `tabCampus Drive Application`
            WHERE 1=1
            {where_clause}
        """, values)[0][0]

        not_applied = max(0, all_students - students_applied)

        return {
            "status": 200,
            "data": {
                "placed": placed,
                "shortlisted": shortlisted,
                "applied_to_drives": applied,
                "not_applied_yet": not_applied
            }
        }

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "get_placement_counts Error")
        return {"status": 500, "message": str(e)}
    
@frappe.whitelist(allow_guest=True)
def get_placement_list(college=None, status=None, name=None):
    try:
        conditions = []
        values = []

        if college:
            conditions.append("cda.college = %s")
            values.append(college)

        if status:
            conditions.append("cda.status = %s")
            values.append(status)

        if name:
            conditions.append("drive = %s")   # ← name is drive name, filter on drive field
            values.append(name)

        where_clause = " AND ".join(conditions) if conditions else "1=1"

        data = frappe.db.sql("""
            SELECT
                cda.name                  AS application_id,
                cda.student               AS student_id,
                cda.drive                 AS drive,
                cda.college               AS college,
                cda.status                AS status,
                cda.application_date      AS application_date,
                cda.package_lpa           AS package_lpa,
                cda.selection_id          AS selection_id,
                cda.remarks               AS remarks,
                s.first_name              AS first_name,
                s.last_name               AS last_name,
                s.email_id                AS email,
                s.mobile_no               AS mobile_no,
                s.gender                  AS gender,
                s.date_of_birth           AS date_of_birth,
                s.academic_year           AS academic_year,
                s.cgpa                    AS cgpa,
                s.linkedin                AS linkedin,
                s.github                  AS github,
                s.current_year            AS current_year,
                s.resume                  AS resume,
                s.department              AS department,
                s.course                  AS course,
                s.stream                  AS stream,
                s.semester                AS semester,
                d.industry_name           AS company_name,
                d.drive_date              AS drive_date,
                d.package_offered         AS package_offered,
                d.job_title               AS job_title,
                d.criteria                AS criteria
                
            FROM `tabCampus Drive Application` cda
            LEFT JOIN `tabStudent` s
                ON s.name = cda.student
            LEFT JOIN `tabCollege Campus Drives` d
                ON d.name = cda.drive
            WHERE {where_clause}
            ORDER BY cda.creation DESC
        """.format(where_clause=where_clause), values, as_dict=True)

        return {
            "status": 200,
            "count": len(data),
            "data": data
        }

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "get_placement_list Error")
        return {"status": 500, "message": str(e)}


import frappe

@frappe.whitelist()
def get_eligible_students_count(
    college=None,
    branch=None,
    cgpa=None,
    backlog=None,
    search=None
):
    try:
        filters = {}

        if college:
            filters["college"] = college

        if branch:
            branches = [b.strip() for b in branch.split(",") if b.strip()]
            filters["department"] = ["in", branches]

        if cgpa:
            filters["cgpa"] = [">=", float(cgpa)]

        if backlog is not None and str(backlog).strip() != "":
            filters["backlog"] = ["<=", int(backlog)]

        if search:
            filters["first_name"] = ["like", f"%{search}%"]

        total = frappe.db.count("Student", filters=filters)

        return {
            "status": 200,
            "message": "Eligible students count fetched successfully",
            "count": total,
            "filters": {
                "college": college,
                "branch": branch,
                "cgpa": cgpa,
                "backlog": backlog,
                "search": search
            }
        }

    except Exception as e:
        frappe.log_error(
            frappe.get_traceback(),
            "get_eligible_students_count Error"
        )
        return {
            "status": 500,
            "message": str(e)
        }
 # ── 1. ELIGIBLE STUDENTS ─────────────────────────────────────────────────────
@frappe.whitelist(allow_guest=True)
def get_eligible_students(
    college=None,
    branch=None,
    cgpa=None,
    backlog=None,
    page=1,
    page_size=10,
    search=None
):
    try:
        page      = int(page)
        page_size = int(page_size)
        offset    = (page - 1) * page_size

        filters = {}
        if college:
            filters["college"] = college
        if branch:
            branches = [b.strip() for b in branch.split(",") if b.strip()]
            filters["department"] = ["in", branches]
        if cgpa:
            filters["cgpa"] = [">=", float(cgpa)]
        if backlog is not None:
            filters["backlog"] = ["<=", int(backlog)]
        if search:
            filters["first_name"] = ["like", f"%{search}%"]

        students = frappe.get_all(
            "Student",
            filters=filters,
            fields=[
                "name", "first_name", "last_name", "email_id",
                "mobile_no", "college", "department", "course",
                "cgpa", "academic_year", "backlog","current_year"
            ],
            start=offset,
            page_length=page_size,
            order_by="first_name asc"
        )

        total = frappe.db.count("Student", filters=filters)

        return {
            "status": 200,
            "message": "Eligible students fetched successfully",
            "filters": {"college": college, "branch": branch, "cgpa": cgpa, "backlog": backlog},
            "pagination": {
                "total":       total,
                "page":        page,
                "page_size":   page_size,
                "total_pages": -(-total // page_size),
                "has_next":    offset + page_size < total,
                "has_prev":    page > 1
            },
            "data": students
        }

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "get_eligible_students Error")
        return {"status": 500, "message": str(e)}


# ── 2. NOT ELIGIBLE STUDENTS WITH REASONS ────────────────────────────────────
@frappe.whitelist()
def get_not_eligible_students(
    college=None,
    branch=None,
    cgpa=None,
    backlog=None,
    page=1,
    page_size=10,
    search=None
):
    try:
        page      = int(page)
        page_size = int(page_size)
        offset    = (page - 1) * page_size

        # Base filter — fetch all students for this college
        base_filters = {}
        if college:
            base_filters["college"] = college
        if search:
            base_filters["first_name"] = ["like", f"%{search}%"]

        all_students = frappe.get_all(
            "Student",
            filters=base_filters,
            fields=[
                "name", "first_name", "last_name", "email_id",
                "mobile_no", "college", "department", "course",
                "cgpa", "academic_year", "backlog","current_year"
            ],
            order_by="first_name asc"
        )

        # Allowed branches list
        allowed_branches = []
        if branch:
            allowed_branches = [b.strip() for b in branch.split(",") if b.strip()]

        min_cgpa    = float(cgpa)    if cgpa    is not None else None
        max_backlog = int(backlog)   if backlog is not None else None

        not_eligible = []
        for s in all_students:
            reasons = []

            # Check branch
            if allowed_branches and s.department not in allowed_branches:
                reasons.append("Branch not eligible")

            # Check CGPA
            if min_cgpa is not None and (not s.cgpa or s.cgpa < min_cgpa):
                reasons.append(f"CGPA below {min_cgpa}")

            # Check backlogs
            if max_backlog is not None and (s.backlog or 0) > max_backlog:
                reasons.append("Has backlogs")

            if reasons:
                not_eligible.append({
                    **s,
                    "reasons": reasons  # list — multiple reasons possible
                })

        total         = len(not_eligible)
        paginated     = not_eligible[offset: offset + page_size]

        return {
            "status":  200,
            "message": "Not eligible students fetched successfully",
            "filters": {"college": college, "branch": branch, "cgpa": cgpa, "backlog": backlog},
            "pagination": {
                "total":       total,
                "page":        page,
                "page_size":   page_size,
                "total_pages": -(-total // page_size),
                "has_next":    offset + page_size < total,
                "has_prev":    page > 1
            },
            "data": paginated
        }

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "get_not_eligible_students Error")
        return {"status": 500, "message": str(e)}


# ── 3. EXPORT ELIGIBLE STUDENTS (CSV) ────────────────────────────────────────
import csv
import io

@frappe.whitelist()
def export_eligible_students(
    college=None,
    branch=None,
    cgpa=None,
    backlog=None
):
    try:
        filters = {}
        if college:
            filters["college"] = college
        if branch:
            branches = [b.strip() for b in branch.split(",") if b.strip()]
            filters["department"] = ["in", branches]
        if cgpa:
            filters["cgpa"] = [">=", float(cgpa)]
        if backlog is not None:
            filters["backlog"] = ["<=", int(backlog)]

        students = frappe.get_all(
            "Student",
            filters=filters,
            fields=[
                "name", "first_name", "last_name", "email_id",
                "mobile_no", "college", "department", "course",
                "cgpa", "academic_year", "backlog","current_year"
            ],
            order_by="first_name asc"
        )

        output = io.StringIO()
        writer = csv.writer(output)

        # Header row
        writer.writerow([
            "Student ID", "First Name", "Last Name", "Email",
            "Mobile", "College", "Department", "Course",
            "CGPA", "Academic Year", "Backlogs","current_year"
        ])

        # Data rows
        for s in students:
            writer.writerow([
                s.get("name"),
                s.get("first_name"),
                s.get("last_name"),
                s.get("email_id"),
                s.get("mobile_no"),
                s.get("college"),
                s.get("department"),
                s.get("course"),
                s.get("cgpa"),
                s.get("academic_year"),
                s.get("backlog") or 0,
            ])

        frappe.response["filename"]     = "eligible_students.csv"
        frappe.response["filecontent"]  = output.getvalue().encode("utf-8")
        frappe.response["type"]         = "download"
        frappe.response["content_type"] = "text/csv; charset=utf-8"

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "export_eligible_students Error")
        return {"status": 500, "message": str(e)}


@frappe.whitelist()
def export_not_eligible_students(
    college=None,
    branch=None,
    cgpa=None,
    backlog=None
):
    try:
        base_filters = {}
        if college:
            base_filters["college"] = college

        all_students = frappe.get_all(
            "Student",
            filters=base_filters,
            fields=[
                "name", "first_name", "last_name", "email_id",
                "mobile_no", "college", "department", "course",
                "cgpa", "academic_year", "backlog"
            ],
            order_by="first_name asc"
        )

        allowed_branches = []
        if branch:
            allowed_branches = [b.strip() for b in branch.split(",") if b.strip()]

        min_cgpa    = float(cgpa)  if cgpa    is not None else None
        max_backlog = int(backlog) if backlog is not None else None

        output = io.StringIO()
        writer = csv.writer(output)

        # Header row
        writer.writerow([
            "Student ID", "First Name", "Last Name", "Email",
            "Mobile", "College", "Department", "Course",
            "CGPA", "Academic Year", "Backlogs", "Reason(s)"
        ])

        count = 0
        for s in all_students:
            reasons = []

            if allowed_branches and s.get("department") not in allowed_branches:
                reasons.append("Branch not eligible")

            if min_cgpa is not None and (not s.get("cgpa") or s.get("cgpa") < min_cgpa):
                reasons.append(f"CGPA below {min_cgpa}")

            if max_backlog is not None and (s.get("backlog") or 0) > max_backlog:
                reasons.append("Has backlogs")

            if reasons:
                count += 1
                writer.writerow([
                    s.get("name"),
                    s.get("first_name"),
                    s.get("last_name"),
                    s.get("email_id"),
                    s.get("mobile_no"),
                    s.get("college"),
                    s.get("department"),
                    s.get("course"),
                    s.get("cgpa"),
                    s.get("academic_year"),
                    s.get("backlog") or 0,
                    " | ".join(reasons)
                ])

        frappe.response["filename"]     = "not_eligible_students.csv"
        frappe.response["filecontent"]  = output.getvalue().encode("utf-8")
        frappe.response["type"]         = "download"
        frappe.response["content_type"] = "text/csv; charset=utf-8"

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "export_not_eligible_students Error")
        return {"status": 500, "message": str(e)}
       
@frappe.whitelist(allow_guest=True)
def update_application_status(application_name, status):
    try:
        valid_statuses = [
            "Applied",
            "Shortlisted",
            "Selected",
            "Rejected",
            "Not Applied"
        ]

        if status not in valid_statuses:
            return {
                "status": 400,
                "message": f"Invalid status. Allowed values: {', '.join(valid_statuses)}"
            }

        if not frappe.db.exists("Campus Drive Application", application_name):
            return {
                "status": 404,
                "message": "Application not found"
            }

        doc = frappe.get_doc("Campus Drive Application", application_name)
        doc.status = status

        doc.save(ignore_permissions=True)
        frappe.db.commit()

        return {
            "status": 200,
            "message": f"Application status updated to {status}",
            "data": {
                "application": doc.name,
                "student": doc.student,
                "drive": doc.drive,
                "status": doc.status
            }
        }

    except Exception as e:
        frappe.log_error(
            frappe.get_traceback(),
            "Update Application Status Error"
        )
        return {
            "status": 500,
            "message": str(e)
        }

EMAIL_TEMPLATES = {
    "eligible": {
        "subject": "Congratulations! You are Eligible for the Drive",
        "body": lambda d: f"""
            <p>Dear {d['name']},</p>
            <p>We are pleased to inform you that you are
            <strong>eligible</strong> for the
            <strong>{d['drive']}</strong>.</p>
            <p>Our team will reach out with further details soon.
            Stay tuned!</p>
            <br>
            <p>Best regards,<br>Stridenex HR Team</p>
        """
    },
    "shortlisted": {
        "subject": "You Have Been Shortlisted for the Drive",
        "body": lambda d: f"""
            <p>Dear {d['name']},</p>
            <p>Great news! You have been <strong>shortlisted</strong>
            for the <strong>{d['drive']}</strong>.</p>
            <p>Further rounds and schedule details will be shared
            with you shortly.</p>
            <br>
            <p>Best regards,<br>Stridenex HR Team</p>
        """
    },
    "selected": {
        "subject": "Congratulations! You Have Been Selected",
        "body": lambda d: f"""
            <p>Dear {d['name']},</p>
            <p>We are delighted to inform you that you have been
            <strong>selected</strong> for the
            <strong>{d['drive']}</strong>!</p>
            <p>HR will be in touch with your offer letter and
            onboarding details within 2 working days.</p>
            <br>
            <p>Best regards,<br>Stridenex HR Team</p>
        """
    }
}

VALID_STATUSES = set(EMAIL_TEMPLATES.keys())


@frappe.whitelist(allow_guest=True)
def send_candidate_status_mail(
    email=None,
    status=None,
    candidate_name=None,
    drive_name=None,
    page=1,
    page_size=10,
):
    try:
        # ── validation ──────────────────────────────────────
        
        if not email:
            return gen_response(400, "Email is required")

        if not frappe.utils.validate_email_address(email, throw=False):
            return gen_response(400, "Invalid email address")

        if not status:
            return gen_response(400, "Status is required")

        status = status.lower().strip()
        if status not in VALID_STATUSES:
            return gen_response(400,
                f"Invalid status. Allowed: {', '.join(VALID_STATUSES)}"
            )

        # ── build template data ─────────────────────────────
        data = {
            "name" : candidate_name or "Candidate",
            "drive": drive_name     or "the placement drive",
        }

        template = EMAIL_TEMPLATES[status]

        # ── send email ──────────────────────────────────────
        frappe.sendmail(
            recipients=[email],
            subject=template["subject"],
            message=template["body"](data),
            now=True
        )

        frappe.db.commit()

        return {
            "status" : "success",
            "message": f"{status.capitalize()} email sent to {email}",
            "email"  : email,
            "type"   : status
            
        }

    except Exception as e:
        frappe.log_error(
            frappe.get_traceback(),
            "Send Candidate Status Mail Error"
        )
        return {"status": "error", "message": str(e)}


def gen_response(code, msg):
    frappe.response["http_status_code"] = code
    return {"status": "error", "message": msg}


DEFAULT_PAGE_SIZE = 20

@frappe.whitelist(allow_guest=True)
def get_student_Analytics_list(college=None, name=None, department=None,skill_match="any",  current_year=None,skill=None, risk_level=None, search=None, page=1, page_size=DEFAULT_PAGE_SIZE):
    try:
        page, page_size, limit, offset = get_pagination_params(page, page_size)

        conditions = []
        values = []

        if college:
            conditions.append("s.college = %s")
            values.append(college)

        if department:
            if isinstance(department, str):
                dept_list = [d.strip() for d in department.split(",") if d.strip()]
            else:
                dept_list = list(department)

            if len(dept_list) == 1:
                conditions.append("s.department = %s")
                values.append(dept_list[0])
            elif len(dept_list) > 1:
                placeholders = ", ".join(["%s"] * len(dept_list))
                conditions.append(f"s.department IN ({placeholders})")
                values.extend(dept_list)

        if current_year:
            conditions.append("s.current_year = %s")
            values.append(current_year)

        if name:
            conditions.append("s.name = %s")
            values.append(name)

        if search:
            tokens = search.split()
            for token in tokens:
                conditions.append("""
                    (s.first_name LIKE %s 
                    OR s.last_name LIKE %s 
                    OR s.department LIKE %s
                    OR CONCAT(s.first_name, ' ', s.last_name) LIKE %s)
                """)
                values.extend([f"%{token}%"] * 4)
        if skill:
            skill_list = _parse_list_param(skill)

            if skill_list:
                if skill_match == "all":
                    # Student must have EVERY skill in the list (AND semantics)
                    for sk in skill_list:
                        conditions.append(
                            """
                            EXISTS (
                                SELECT 1
                                FROM `tabStudent Skill Table` sst
                                WHERE sst.parent = s.name
                                  AND sst.skill = %s
                            )
                            """
                        )
                        values.append(sk)
                else:
                    # Default: student must have AT LEAST ONE skill (OR semantics)
                    placeholders = ", ".join(["%s"] * len(skill_list))
                    conditions.append(
                        f"""
                        EXISTS (
                            SELECT 1
                            FROM `tabStudent Skill Table` sst
                            WHERE sst.parent = s.name
                              AND sst.skill IN ({placeholders})
                        )
                        """
                    )
                    values.extend(skill_list)
        if risk_level:
            risk_level = risk_level.strip().lower() 
                    
        if risk_level and risk_level != "all risk levels":
            if risk_level == "low":
                conditions.append("s.employability_score >= 70")

            elif risk_level == "medium":
                conditions.append("s.employability_score >= 40")
                conditions.append("s.employability_score < 70")

            elif risk_level == "high":
                conditions.append("s.employability_score < 40")

        where_clause = ("WHERE " + " AND ".join(conditions)) if conditions else ""  

        # ✅ Count total using raw SQL to match same filters
        count_sql = f"""
            SELECT COUNT(*) FROM `tabStudent` s
            {where_clause}
        """
        total = frappe.db.sql(count_sql, values)[0][0]

        # ✅ Pagination values added at end AFTER total count
        paginated_values = values + [limit, offset]

        data = frappe.db.sql("""
            SELECT
                s.name                  AS student_id,
                s.first_name            AS first_name,
                s.last_name             AS last_name,
                s.department            AS branch,
                s.academic_year         AS year,
                s.cgpa                  AS cgpa,
                s.email_id              AS email,
                s.mobile_no             AS mobile_no,
                s.resume                AS resume,
                s.current_year          AS current_year,

                (
                    SELECT cda.status
                    FROM `tabCampus Drive Application` cda
                    WHERE cda.student = s.name
                    ORDER BY cda.creation DESC
                    LIMIT 1
                ) AS placement_status,
                COALESCE(s.employability_score, 0) AS employability_score,
                CASE
                    WHEN COALESCE(s.employability_score, 0) >= 70 THEN 'Low'
                    WHEN COALESCE(s.employability_score, 0) >= 40 THEN 'Medium'
                    ELSE 'High'
                END AS risk_level,
                (
                    SELECT COUNT(*)
                    FROM `tabCampus Drive Application` cda2
                    WHERE cda2.student = s.name
                    AND cda2.status = 'Selected'
                ) AS internship_count
            FROM `tabStudent` s
            
            {where_clause}
            ORDER BY s.creation DESC
            LIMIT %s OFFSET %s
        """.format(where_clause=where_clause), paginated_values, as_dict=True)

        # ✅ risk_level filter applied BEFORE pagination ideally, but if computed field, filter here
        # NOTE: filtering after pagination will reduce page results — move to SQL HAVING if possible
        # if risk_level and risk_level != "All Risk Levels":
        #     data = [d for d in data if d.get("risk_level") == risk_level]

        return {
            "status": 200,
            "count": len(data),
            "data": {
                "data": data,
                "pagination": make_pagination_meta(total, page, page_size)
            }
        }

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "get_student_Analytics_list Error")
        return {"status": 500, "message": str(e)}

def _parse_list_param(value):
    """Normalize a skill/department param into a plain Python list of strings."""
    import json

    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]

    if isinstance(value, str):
        value = value.strip()
        # Try JSON array first: ["Python","Pandas"]
        if value.startswith("["):
            try:
                parsed = json.loads(value)
                return [str(v).strip() for v in parsed if str(v).strip()]
            except (json.JSONDecodeError, TypeError):
                pass
        # Fall back to comma-separated: "Python,Pandas"
        return [v.strip() for v in value.split(",") if v.strip()]

    return []
