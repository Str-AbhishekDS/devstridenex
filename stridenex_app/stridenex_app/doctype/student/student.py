# Copyright (c) 2026, QTPL and contributors
# For license information, please see license.txt

import frappe
import json
import math

from stridenex_app.api_stridenex_app.app_utils import (
    gen_response,
    exception_handel,get_pagination_params,make_cache_key,make_pagination_meta
)
import frappe
from frappe.model.document import Document
CACHE_TTL   = 300 

class Student(Document):
    def validate(self):
    
        self.validate_resume()
        self.validate_social_links()

    def validate_resume(self):
        if self.resume:
            file_doc = frappe.get_doc("File", {"file_url": self.resume})
            
            if not file_doc.file_name.lower().endswith(".pdf"):
                frappe.throw("Only PDF files are allowed for Resume upload.")


    def validate_social_links(self):
        if self.linkedin and "linkedin.com" not in self.linkedin.lower():
            frappe.throw("Please enter a valid LinkedIn URL.")

        if self.github and "github.com" not in self.github.lower():
            frappe.throw("Please enter a valid GitHub URL.")
            
    def after_insert(self):
        self.create_student_skills()

    def create_student_skills(self):

        if not self.skill:
            return

        for row in self.skill:

            if not row.skill:
                continue

            if not frappe.db.exists(
                "Student Skill",
                {"student": self.name, "skill": row.skill}
            ):

                student_skill = frappe.new_doc("Student Skill")
                student_skill.student = self.name
                student_skill.skill = row.skill
                student_skill.current_level = row.level
                student_skill.self_declared = 1
                student_skill.is_public = 1
                student_skill.first_acquired = frappe.utils.today()

                student_skill.insert(ignore_permissions=True)
                student_skill.save(ignore_permissions = True)
                frappe.db.commit()

    def get_total_student_count():
        return frappe.db.count("Student", {"status": "Active"})


@frappe.whitelist(allow_guest=True)
def get_student_count():
    try:
        count = frappe.db.count("Student")

        return gen_response(
            status=200,
            message="Student count fetched successfully",
            data={"total_students": count}
        )

    except Exception as e:
        return exception_handel(e)

@frappe.whitelist()
def get_student_skills(student):
    """
    Fetch all skills and levels for a student.
    """
    if not frappe.db.exists("Student", student):
        frappe.throw("Student not found")

    student_doc = frappe.get_doc("Student", student)

    skills = []
    for row in student_doc.skill:
        skills.append({
            "skill": row.skill,
            "level": row.level
        })

    return {
        "student": student,
        "skills": skills
    }


@frappe.whitelist()
def get_dashboard_stats(student=None):
    student = student or frappe.db.get_value("Student", {"email_id": frappe.session.user})
    if not student:
        frappe.throw("Student profile not found")

    s = frappe.get_doc("Student", student)

    return {
        "employability_score": s.employability_score,
        
        "total_skills": len(s.get("skill") or []),
        "cgpa": s.cgpa,
        "backlog": s.get("backlog") or 0,
       
        "profile_completeness": get_profile_completeness(s)
    }

def get_profile_completeness(student_doc):
    required_fields = ["first_name", "last_name", "email_id", "mobile_no",
                        "college", "course", "resume", "cgpa", "date_of_birth"]
    filled = sum(1 for f in required_fields if student_doc.get(f))
    return round((filled / len(required_fields)) * 100)

# DEFAULT_PAGE_SIZE = 20
# @frappe.whitelist(allow_guest=True)
# def get_student_list(college=None, page=1, page_size=DEFAULT_PAGE_SIZE):
#     try:
#         page, page_size, limit, offset = get_pagination_params(page, page_size)

#         filters = {}
#         if college:
#             filters["college"] = college

#         # ── Cache key unique to every (college, page, page_size) combo ──────
#         cache_key = make_cache_key("student_list", college=college, page=page, page_size=page_size)

#         cached = frappe.cache().get_value(cache_key)
#         if cached:
#             return cached                         # ← cache HIT, return immediately

#         # ── Total count (for pagination meta) ───────────────────ps aux | grep gunicorn────────────
#         total = frappe.db.count("Student", filters=filters)

#         # ── Paginated fetch ─────────────────────────────────────────────────
#         students = frappe.get_all(
#             "Student",
#             filters=filters,
#             fields=["*"],
#             order_by="creation desc",
#             limit=limit,
#             start=offset,
#         )

#         # ── Enrich with child table in one DB round-trip ─────────────────────
#         if students:
#             parent_names = [s["name"] for s in students]
#             all_skills = frappe.get_all(
#                 "Student Skill Table",
#                 filters=[["parent", "in", parent_names]],
#                 fields=["parent", "skill"],
#             )
#             # Group skills by parent
#             skills_map = {}
#             for sk in all_skills:
#                 skills_map.setdefault(sk["parent"], []).append({"skill": sk["skill"]})
#             for student in students:
#                 student["skills"] = skills_map.get(student["name"], [])

#         # ── Build response ───────────────────────────────────────────────────
#         result = gen_response(
#             status=200,
#             message="Student list fetched successfully",
#             data={
#                 "students":   students,
#                 "pagination": make_pagination_meta(total, page, page_size),
#             }
#         )

#         frappe.cache().set_value(cache_key, result, expires_in_sec=CACHE_TTL)
#         return result

#     except Exception as e:
#         return exception_handel(e)
    
DEFAULT_PAGE_SIZE = 20

JUNK_VALUES = {"", "none", "null", "undefined", "nan"}


def _clean(value):
    """Return None if the incoming value is empty/junk, else the stripped value."""
    if value is None:
        return None
    value = str(value).strip()
    return None if value.lower() in JUNK_VALUES else value


@frappe.whitelist(allow_guest=True)
def get_student_list(
    search=None,
    college=None,
    current_year=None,
    skills=None,          # "Python,SQL" or '["Python","SQL"]'
    min_match=0,           # e.g. 80 -> only candidates with >=80% skill match
    sort_by="best_match",  # best_match | name | year
    page=1,
    page_size=DEFAULT_PAGE_SIZE,
):
    """
    Response shape (UNCHANGED):
    {
        students: [
            { student_name, college, course, department, stream, match_percentage, skills }
        ],
        pagination: {...}
    }
    """
    try:
        page = int(page)
        page_size = int(page_size)
        min_match = float(min_match or 0)
        limit = page_size
        offset = (page - 1) * page_size

        # ---- FIX: sanitize filter inputs so "None"/"null"/"" strings from the
        # frontend are treated as no-filter, not as literal filter values ----
        search = _clean(search)
        college = _clean(college)
        current_year = _clean(current_year)

        # ---- normalize skills param ----
        skill_list = []
        if skills:
            if isinstance(skills, str):
                try:
                    skill_list = json.loads(skills)
                except (ValueError, TypeError):
                    skill_list = [s.strip() for s in skills.split(",") if s.strip()]
            elif isinstance(skills, list):
                skill_list = skills
        skill_list = [s for s in skill_list if _clean(s)]

        # ---- cache key ----
        cache_key = make_cache_key(
            "student_search",
            search=search or "", college=college or "", current_year=current_year or "",
            skills=",".join(sorted(s.lower() for s in skill_list)), min_match=min_match,
            sort_by=sort_by, page=page, page_size=page_size,
        )
        cached = frappe.cache().get_value(cache_key)
        if cached:
            return cached

        # ---- shared WHERE conditions on tabStudent (built once, reused) ----
        conditions = []
        values = {}
        if college:
            conditions.append("s.college = %(college)s")
            values["college"] = college
        if current_year:
            conditions.append("s.current_year = %(current_year)s")
            values["current_year"] = current_year
        if search:
            conditions.append("s.email_id LIKE %(search)s")
            values["search"] = f"%{search}%"

        where_clause = ("WHERE " + " AND ".join(conditions)) if conditions else ""

        # =========================================================
        # CASE 1: skills selected -> join + score + filter + sort
        #         all done in SQL, only the final page comes back.
        # =========================================================
        if skill_list:
            skill_placeholders = []
            for i, sk in enumerate(skill_list):
                key = f"skill_{i}"
                values[key] = sk
                skill_placeholders.append(f"%({key})s")
            skill_in_clause = ", ".join(skill_placeholders)

            total_selected = len(skill_list)
            min_count = math.ceil((min_match / 100) * total_selected) if min_match else 0
            values["min_count"] = min_count

            order_clause = "ORDER BY matched_count DESC, s.creation DESC"
            if sort_by == "name":
                order_clause = "ORDER BY s.email_id ASC"   # FIX: was "eamil_id" (typo, undefined column -> caused errors)
            elif sort_by == "year":
                order_clause = "ORDER BY s.current_year DESC"

            base_query = f"""
                FROM `tabStudent` s
                INNER JOIN (
                    SELECT parent, COUNT(DISTINCT skill) AS matched_count
                    FROM `tabStudent Skill Table`
                    WHERE skill IN ({skill_in_clause})
                    GROUP BY parent
                    HAVING matched_count >= %(min_count)s
                ) t ON t.parent = s.name
                {where_clause}
            """

            total = frappe.db.sql(f"SELECT COUNT(*) {base_query}", values)[0][0]

            values["limit"] = limit
            values["offset"] = offset
            rows = frappe.db.sql(
                f"""
                SELECT s.*, t.matched_count
                {base_query}
                {order_clause}
                LIMIT %(limit)s OFFSET %(offset)s
                """,
                values,
                as_dict=True,
            )

            students = rows
            for student in students:
                matched = student.pop("matched_count", 0)
                student["match_percentage"] = round((matched / total_selected) * 100)

        # =========================================================
        # CASE 2: no skills selected -> plain fast filtered query
        # =========================================================
        else:
            order_clause = "ORDER BY s.creation DESC"
            if sort_by == "name":
                order_clause = "ORDER BY s.email_id ASC"   # FIX: same typo fixed here
            elif sort_by == "year":
                order_clause = "ORDER BY s.current_year DESC"

            total = frappe.db.sql(
                f"SELECT COUNT(*) FROM `tabStudent` s {where_clause}", values
            )[0][0]

            values["limit"] = limit
            values["offset"] = offset
            students = frappe.db.sql(
                f"""
                SELECT s.*
                FROM `tabStudent` s
                {where_clause}
                {order_clause}
                LIMIT %(limit)s OFFSET %(offset)s
                """,
                values,
                as_dict=True,
            )
            for student in students:
                student["match_percentage"] = None

        # ---- attach skills only for the page we're returning (cheap) ----
        if students:
            parent_names = [s["name"] for s in students]
            all_skills = frappe.get_all(
                "Student Skill Table",
                filters=[["parent", "in", parent_names]],
                fields=["parent", "skill"],
            )
            skills_map = {}
            for sk in all_skills:
                skills_map.setdefault(sk["parent"], []).append({"skill": sk["skill"]})
            for student in students:
                student["skills"] = skills_map.get(student["name"], [])

        # ---- response (UNCHANGED shape) ----
        result = gen_response(
            status=200,
            message="Student list fetched successfully",
            data={
                "students": students,
                "pagination": make_pagination_meta(total, page, page_size),
            },
        )

        frappe.cache().set_value(cache_key, result, expires_in_sec=CACHE_TTL)
        return result

    except Exception as e:
        return exception_handel(e)

@frappe.whitelist(allow_guest=True)
def export_students(search=None, college=None, current_year=None, skills=None, min_match=0, sort_by="best_match"):
    """
    Same filtering/scoring logic as get_student_list but returns the FULL
    result set (no pagination) for CSV/Excel export.
    """
    try:
        full = get_student_list(
            search=search, college=college, current_year=current_year,
            skills=skills, min_match=min_match, sort_by=sort_by,
            page=1, page_size=10**9,   # effectively "all"
        )
        return full
    except Exception as e:
        return exception_handel(e)




@frappe.whitelist(allow_guest=True)
def create_skill():
    try:
        data = frappe.request.get_json()

        doc = frappe.get_doc({
            "doctype": "Skill",
            "skill_name": data.get("skill_name")
        })

        doc.insert(ignore_permissions=True)
        frappe.db.commit()

        return {
            "status": "success",
            "message": "Skill created successfully",
            "data": doc.name
        }

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Create Skill Error")
        return {
            "status": "error",
            "message": str(e)
        }