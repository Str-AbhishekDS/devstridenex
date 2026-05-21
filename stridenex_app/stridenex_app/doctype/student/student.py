# Copyright (c) 2026, QTPL and contributors
# For license information, please see license.txt

from stridenex_app.api_stridenex_app.app_utils import (
    gen_response,
    exception_handel
)
import frappe
from frappe.model.document import Document

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
            
    def before_submit(self):
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
    
@frappe.whitelist(allow_guest=True)
def get_student_list(college=None):
    try:
        filters = {}
        if college:
            filters["college"] = college
    
        
        students = frappe.get_all(
            "Student",
            filters=filters,
            fields=["*"
            ],
            order_by="creation desc"
        )
        for domain in students:
            # 👇 Skills child table
            skills = frappe.get_all(
                "Student Skill Table",
                filters={"parent": domain["name"]},
                fields=["skill"]
            )
            domain["skills"] = skills


        return gen_response(
            status=200,
            message="Student list fetched successfully",
            data=students
        )

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