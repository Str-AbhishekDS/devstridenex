# Copyright (c) 2026, QTPL and contributors
# For license information, please see license.txt

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

        
DEFAULT_PAGE_SIZE = 20
@frappe.whitelist(allow_guest=True)
def get_student_list(college=None, page=1, page_size=DEFAULT_PAGE_SIZE):
    try:
        page, page_size, limit, offset = get_pagination_params(page, page_size)

        filters = {}
        if college:
            filters["college"] = college

        # ── Cache key unique to every (college, page, page_size) combo ──────
        cache_key = make_cache_key("student_list", college=college, page=page, page_size=page_size)

        cached = frappe.cache().get_value(cache_key)
        if cached:
            return cached                         # ← cache HIT, return immediately

        # ── Total count (for pagination meta) ───────────────────ps aux | grep gunicorn────────────
        total = frappe.db.count("Student", filters=filters)

        # ── Paginated fetch ─────────────────────────────────────────────────
        students = frappe.get_all(
            "Student",
            filters=filters,
            fields=["*"],
            order_by="creation desc",
            limit=limit,
            start=offset,
        )

        # ── Enrich with child table in one DB round-trip ─────────────────────
        if students:
            parent_names = [s["name"] for s in students]
            all_skills = frappe.get_all(
                "Student Skill Table",
                filters=[["parent", "in", parent_names]],
                fields=["parent", "skill"],
            )
            # Group skills by parent
            skills_map = {}
            for sk in all_skills:
                skills_map.setdefault(sk["parent"], []).append({"skill": sk["skill"]})
            for student in students:
                student["skills"] = skills_map.get(student["name"], [])

        # ── Build response ───────────────────────────────────────────────────
        result = gen_response(
            status=200,
            message="Student list fetched successfully",
            data={
                "students":   students,
                "pagination": make_pagination_meta(total, page, page_size),
            }
        )

        frappe.cache().set_value(cache_key, result, expires_in_sec=CACHE_TTL)
        return result

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