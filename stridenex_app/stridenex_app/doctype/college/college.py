# Copyright (c) 2026, QTPL and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class College(Document):

    def on_update_after_submit(self):

        old_doc = self.get_doc_before_save()

        # Check if status changed to Approved
        if (
            self.approved_status_workflow == "Approved"
            and old_doc
            and old_doc.approved_status_workflow != "Approved"
        ):

            frappe.sendmail(
                recipients=[self.email],
                subject="Welcome to Our Platform",
                message=f"""
                Dear {self.college_name},

                Congratulations!

                Your college registration has been approved.

                Welcome to our platform.

                Regards,
                Team
                """
            )

# ── HELPER FUNCTIONS ─────────────────────────────────────────────────────────

def resolve_college_name(college):
    if not college:
        return college
    if "@" in college:
        resolved = frappe.db.get_value("College", {"email": college}, "name")
        if resolved:
            return resolved
    return college


# ── 1. Summary Stats (Active Students, Avg Employability, At-Risk, Industry Partners) ──

@frappe.whitelist(allow_guest=True)
def get_dashboard_summary(college=None):
    try:
        college = resolve_college_name(college)
        conditions = []
        values = []
        if college:
            conditions.append("college = %s")
            values.append(college)
        where = ("WHERE " + " AND ".join(conditions)) if conditions else ""

        # Active students
        active_students = frappe.db.sql(f"""
            SELECT COUNT(*) FROM `tabStudent` {where}
        """, values)[0][0]

        # This semester count (current month students)
        new_this_sem = frappe.db.sql(f"""
            SELECT COUNT(*) FROM `tabStudent`
            {"WHERE" if not conditions else where + " AND"}
            {" " if not conditions else ""}
            MONTH(creation) = MONTH(CURDATE())
            AND YEAR(creation) = YEAR(CURDATE())
        """, values)[0][0] if not conditions else frappe.db.sql(f"""
            SELECT COUNT(*) FROM `tabStudent`
            WHERE college = %s
            AND MONTH(creation) = MONTH(CURDATE())
            AND YEAR(creation) = YEAR(CURDATE())
        """, values)[0][0]

        # Fetch all students for employability calculation
        students = frappe.db.sql(f"""
            SELECT name, COALESCE(employability_score, 0) AS employability_score FROM `tabStudent` {where}
        """, values, as_dict=True)

        emp_scores = []
        at_risk = 0
        for s in students:
            emp_score = float(s.employability_score)
            emp_scores.append(emp_score)
            if emp_score < 55:
                at_risk += 1

        avg_employability = round(sum(emp_scores) / len(emp_scores), 1) if emp_scores else 0

        return {
            "status": 200,
            "data": {
                "active_students":   active_students,
                "new_this_semester": new_this_sem,
                "avg_employability": avg_employability,
                "at_risk_students":  at_risk
            }
        }
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "get_dashboard_summary Error")
        return {"status": 500, "message": str(e)}


# ── 2. Employability Distribution ─────────────────────────────────────────────

@frappe.whitelist(allow_guest=True)
def get_employability_distribution(college=None):
    try:
        college = resolve_college_name(college)
        conditions = []
        values = []
        if college:
            conditions.append("college = %s")
            values.append(college)
        where = ("WHERE " + " AND ".join(conditions)) if conditions else ""

        students = frappe.db.sql(f"""
            SELECT name, COALESCE(employability_score, 0) AS score FROM `tabStudent` {where}
        """, values, as_dict=True)

        distribution = {"excellent": 0, "good": 0, "average": 0, "at_risk": 0}
        total = len(students)

        for s in students:
            score = float(s.score)

            if score >= 85:
                distribution["excellent"] += 1
            elif score >= 70:
                distribution["good"] += 1
            elif score >= 55:
                distribution["average"] += 1
            else:
                distribution["at_risk"] += 1

        def pct(n):
            return round((n / total) * 100) if total else 0

        return {
            "status": 200,
            "data": {
                "excellent": {"count": distribution["excellent"], "percent": pct(distribution["excellent"]), "range": "85-100"},
                "good":      {"count": distribution["good"],      "percent": pct(distribution["good"]),      "range": "70-84"},
                "average":   {"count": distribution["average"],   "percent": pct(distribution["average"]),   "range": "55-69"},
                "at_risk":   {"count": distribution["at_risk"],   "percent": pct(distribution["at_risk"]),   "range": "<55"},
                "total":     total
            }
        }
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "get_employability_distribution Error")
        return {"status": 500, "message": str(e)}


# ── 3. Branch-wise Performance (Avg Employability per Department) ──────────────

@frappe.whitelist(allow_guest=True)
def get_branch_wise_performance(college=None):
    try:
        college = resolve_college_name(college)
        conditions = []
        values = []
        if college:
            conditions.append("college = %s")
            values.append(college)
        where = ("WHERE " + " AND ".join(conditions)) if conditions else ""

        students = frappe.db.sql(f"""
            SELECT name, department, COALESCE(employability_score, 0) AS employability_score FROM `tabStudent`
            {where}
        """, values, as_dict=True)

        dept_map = {}
        for s in students:
            dept = s.department or "Unknown"
            emp_score = float(s.employability_score)

            if dept not in dept_map:
                dept_map[dept] = {"scores": [], "count": 0}
            dept_map[dept]["scores"].append(emp_score)
            dept_map[dept]["count"] += 1

        branches = []
        for dept, data in dept_map.items():
            avg = round(sum(data["scores"]) / len(data["scores"]), 1)
            branches.append({
                "department":        dept,
                "student_count":     data["count"],
                "avg_employability": avg
            })

        branches.sort(key=lambda x: x["avg_employability"], reverse=True)

        return {"status": 200, "data": {"branches": branches}}

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "get_branch_wise_performance Error")
        return {"status": 500, "message": str(e)}


# ── 4. Student Onboarding Growth (Monthly) ─────────────────────────────────────

@frappe.whitelist(allow_guest=True)
def get_onboarding_growth(college=None, months=12):
    try:
        college = resolve_college_name(college)
        months = int(months)
        conditions = ["creation >= DATE_SUB(CURDATE(), INTERVAL %s MONTH)"]
        values = [months]
        if college:
            conditions.append("college = %s")
            values.append(college)
        where = "WHERE " + " AND ".join(conditions)

        rows = frappe.db.sql(f"""
            SELECT
                DATE_FORMAT(creation, '%%b') AS month_label,
                DATE_FORMAT(creation, '%%Y-%%m') AS month_key,
                COUNT(*) AS count
            FROM `tabStudent`
            {where}
            GROUP BY month_key, month_label
            ORDER BY month_key ASC
        """, values, as_dict=True)

        total = frappe.db.sql(f"""
            SELECT COUNT(*) FROM `tabStudent`
            {"WHERE college = %s" if college else ""}
        """, [college] if college else [])[0][0]

        return {
            "status": 200,
            "data": {
                "monthly": rows,
                "total":   total
            }
        }
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "get_onboarding_growth Error")
        return {"status": 500, "message": str(e)}


# ── 5. Top Skill Gaps (Skills most students are missing or weak in) ─────────────

@frappe.whitelist(allow_guest=True)
def get_top_skill_gaps(college=None, top_n=10):
    try:
        college = resolve_college_name(college)
        top_n = int(top_n)

        total_students = frappe.db.sql("""
            SELECT COUNT(*) FROM `tabStudent`
            {}
        """.format("WHERE college = %s" if college else ""),
        [college] if college else [])[0][0]

        # Students who have each skill
        conditions = ""
        values = []
        if college:
            conditions = """
                JOIN `tabStudent` s ON s.name = sst.parent
                WHERE s.college = %s AND sst.parenttype = 'Student'
            """
            values.append(college)
        else:
            conditions = "WHERE sst.parenttype = 'Student'"

        skill_counts = frappe.db.sql(f"""
            SELECT
                sst.skill,
                COUNT(DISTINCT sst.parent) AS student_count
            FROM `tabStudent Skill Table` sst
            {conditions}
            GROUP BY sst.skill
            ORDER BY student_count ASC
            LIMIT %s
        """, values + [top_n], as_dict=True)

        gaps = []
        for row in skill_counts:
            lacking = total_students - row.student_count
            pct = round((lacking / total_students) * 100) if total_students else 0
            gaps.append({
                "skill":            row.skill,
                "students_with":    row.student_count,
                "students_lacking": lacking,
                "lack_percent":     pct
            })

        gaps.sort(key=lambda x: x["lack_percent"], reverse=True)

        return {"status": 200, "data": {"skill_gaps": gaps, "total_students": total_students}}

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "get_top_skill_gaps Error")
        return {"status": 500, "message": str(e)}


import frappe
from frappe.utils import getdate


@frappe.whitelist(allow_guest=True)
def get_student_onboarding_graph(year=None, college=None):
    try:
        college = resolve_college_name(college)
        # Default year = current year
        if not year:
            year = getdate().year

        year = int(year)

        # Base filters
        filters = {
            "creation": [
                "between",
                [
                    f"{year}-01-01 00:00:00",
                    f"{year}-12-31 23:59:59"
                ]
            ]
        }

        # College filter
        if college:
            filters["college"] = college

        # Get students month-wise
        students = frappe.get_all(
            "Student",
            filters=filters,
            fields=["name", "creation", "college"]
        )

        # Initialize all months
        monthly_data = {
            1: {"month": "January", "count": 0},
            2: {"month": "February", "count": 0},
            3: {"month": "March", "count": 0},
            4: {"month": "April", "count": 0},
            5: {"month": "May", "count": 0},
            6: {"month": "June", "count": 0},
            7: {"month": "July", "count": 0},
            8: {"month": "August", "count": 0},
            9: {"month": "September", "count": 0},
            10: {"month": "October", "count": 0},
            11: {"month": "November", "count": 0},
            12: {"month": "December", "count": 0}
        }

        # Count students month-wise
        for student in students:
            month = getdate(student.creation).month
            monthly_data[month]["count"] += 1

        return {
            "status": "success",
            "year": year,
            "college": college,
            "data": list(monthly_data.values())
        }

    except Exception as e:
        frappe.log_error(
            frappe.get_traceback(),
            "Student Onboarding Graph Error"
        )

        return {
            "status": "error",
            "message": str(e)
        }




import frappe

# Levels counted as "not yet proficient" -> contributes to the gap
LOW_LEVELS = ["Beginner"]

# Minimum number of students that must have logged the skill before it's
# considered statistically meaningful (avoids 1/1 = 100% gap noise)
MIN_SAMPLE_SIZE = 3


def execute(filters=None):
    filters = filters or {}
    college = filters.get("college")

    columns = get_columns()
    data = get_data(college)
    return columns, data

@frappe.whitelist(allow_guest=True)
def get_columns():
    return [
        {"label": "Skill", "fieldname": "skill", "fieldtype": "Data", "width": 200},
        {"label": "Total Students", "fieldname": "total", "fieldtype": "Int", "width": 130},
        {"label": "At Low Level", "fieldname": "low_count", "fieldtype": "Int", "width": 130},
        {"label": "Gap %", "fieldname": "gap_pct", "fieldtype": "Percent", "width": 100},
        {"label": "Avg Evidence Count", "fieldname": "avg_evidence", "fieldtype": "Float", "width": 150},
    ]

@frappe.whitelist(allow_guest=True)
 # requires login; drop allow_guest=True unless you truly want it public
def get_data(college=None):
    college = resolve_college_name(college)
    conditions = ""
    values = {"low_levels": tuple(LOW_LEVELS) if len(LOW_LEVELS) > 1 else (LOW_LEVELS[0], LOW_LEVELS[0])}

    if college:
        conditions = "AND st.college = %(college)s"
        values["college"] = college

    query = f"""
        SELECT
            ss.skill AS skill,
            COUNT(DISTINCT ss.student) AS total,
            SUM(CASE WHEN ss.current_level IN %(low_levels)s THEN 1 ELSE 0 END) AS low_count,
            AVG(ss.evidence_count) AS avg_evidence
        FROM `tabStudent Skill` ss
        INNER JOIN `tabStudent` st ON st.name = ss.student
        WHERE ss.status != 'Rejected'
        {conditions}
        GROUP BY ss.skill
        HAVING total >= {MIN_SAMPLE_SIZE}
        ORDER BY (SUM(CASE WHEN ss.current_level IN %(low_levels)s THEN 1 ELSE 0 END)
                  / COUNT(DISTINCT ss.student)) DESC
        LIMIT 10
    """

    rows = frappe.db.sql(query, values, as_dict=True)

    for r in rows:
        r["gap_pct"] = round((r["low_count"] / r["total"]) * 100, 1) if r["total"] else 0
        r["avg_evidence"] = round(r["avg_evidence"] or 0, 2)

    return rows