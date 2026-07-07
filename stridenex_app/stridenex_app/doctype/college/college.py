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

# ── 1. Summary Stats (Active Students, Avg Employability, At-Risk, Industry Partners) ──

@frappe.whitelist(allow_guest=True)
def get_dashboard_summary(college=None):
    try:
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
            SELECT name, cgpa FROM `tabStudent` {where}
        """, values, as_dict=True)

        skill_rows = frappe.db.sql("""
            SELECT parent, level FROM `tabStudent Skill Table`
            WHERE parenttype = 'Student'
        """, as_dict=True)

        level_scores = {"Beginner": 25, "Intermediate": 50, "Advanced": 75, "Expert": 100}
        skill_map = {}
        for row in skill_rows:
            score = level_scores.get(row.level, 50)
            if row.parent not in skill_map:
                skill_map[row.parent] = []
            skill_map[row.parent].append(score)

        emp_scores = []
        at_risk = 0
        for s in students:
            cgpa = float(s.cgpa or 0)
            cgpa_norm = (cgpa / 10.0) * 100
            skill_scores = skill_map.get(s.name, [])
            avg_skill = (sum(skill_scores) / len(skill_scores)) if skill_scores else 0
            emp_score = round((0.6 * cgpa_norm) + (0.4 * avg_skill), 2)
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
        conditions = []
        values = []
        if college:
            conditions.append("college = %s")
            values.append(college)
        where = ("WHERE " + " AND ".join(conditions)) if conditions else ""

        students = frappe.db.sql(f"""
            SELECT name, cgpa FROM `tabStudent` {where}
        """, values, as_dict=True)

        skill_rows = frappe.db.sql("""
            SELECT parent, level FROM `tabStudent Skill Table`
            WHERE parenttype = 'Student'
        """, as_dict=True)

        level_scores = {"Beginner": 25, "Intermediate": 50, "Advanced": 75, "Expert": 100}
        skill_map = {}
        for row in skill_rows:
            score = level_scores.get(row.level, 50)
            if row.parent not in skill_map:
                skill_map[row.parent] = []
            skill_map[row.parent].append(score)

        distribution = {"excellent": 0, "good": 0, "average": 0, "at_risk": 0}
        total = len(students)

        for s in students:
            cgpa = float(s.cgpa or 0)
            cgpa_norm = (cgpa / 10.0) * 100
            skill_scores = skill_map.get(s.name, [])
            avg_skill = (sum(skill_scores) / len(skill_scores)) if skill_scores else 0
            score = round((0.6 * cgpa_norm) + (0.4 * avg_skill), 2)

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
        conditions = []
        values = []
        if college:
            conditions.append("college = %s")
            values.append(college)
        where = ("WHERE " + " AND ".join(conditions)) if conditions else ""

        students = frappe.db.sql(f"""
            SELECT name, cgpa, department FROM `tabStudent`
            {where}
        """, values, as_dict=True)

        skill_rows = frappe.db.sql("""
            SELECT parent, level FROM `tabStudent Skill Table`
            WHERE parenttype = 'Student'
        """, as_dict=True)

        level_scores = {"Beginner": 25, "Intermediate": 50, "Advanced": 75, "Expert": 100}
        skill_map = {}
        for row in skill_rows:
            score = level_scores.get(row.level, 50)
            if row.parent not in skill_map:
                skill_map[row.parent] = []
            skill_map[row.parent].append(score)

        dept_map = {}
        for s in students:
            dept = s.department or "Unknown"
            cgpa = float(s.cgpa or 0)
            cgpa_norm = (cgpa / 10.0) * 100
            skill_scores = skill_map.get(s.name, [])
            avg_skill = (sum(skill_scores) / len(skill_scores)) if skill_scores else 0
            emp_score = round((0.6 * cgpa_norm) + (0.4 * avg_skill), 2)

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