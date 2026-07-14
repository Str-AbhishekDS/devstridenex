# Copyright (c) 2026, QTPL and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class CollegeDepartment(Document):
	pass


import frappe

@frappe.whitelist(allow_guest=True)
def get_departments_by_course():
    try:
        

        # -----------------------------
        # Get Courses
        # ----------------------------- 
        courses = frappe.form_dict.get("courses")

        if not courses:
            frappe.throw("Courses are required")

        # Convert comma-separated string to list
        if isinstance(courses, str):
            courses = [c.strip() for c in courses.split(",") if c.strip()]

        # -----------------------------
        # Get Parent Departments
        # -----------------------------
        department_names = frappe.get_all(
            "Course Table",
            filters={
                "course": ["in", courses],
                "parenttype": "College Department"
            },
            pluck="parent"
        )

        if not department_names:
            return {
                "status": 200,
                "message": "No departments found",
                "data": []
            }

        departments = frappe.get_all(
            "College Department",
            filters={
                "name": ["in", department_names]
            },
            fields=["name", "department_name"]
        )

        return {
            "status": 200,
            "message": "Departments fetched successfully",
            "data": departments
        }

    except frappe.PermissionError as e:
        return {
            "status": 403,
            "message": str(e)
        }

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Get Departments Error")
        return {
            "status": 400,
            "message": str(e)
        }