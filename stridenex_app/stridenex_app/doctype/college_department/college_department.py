# Copyright (c) 2026, QTPL and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class CollegeDepartment(Document):
	pass


@frappe.whitelist(allow_guest=True)
def get_departments_by_course():
    try:
        courses = frappe.request.args.get("courses")

        if courses:
            courses = courses.split(",")

        if not courses:
            frappe.throw("Courses are required")

        filters = {
            "courses": ["in", courses]
        }

        departments = frappe.get_all(
            "College Department",  
            filters=filters,
            fields=["name", "department_name", "courses"]
        )

        return {
            "status": 200,
            "message": "Departments fetched successfully",
            "data": departments
        }

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Get Departments Error")
        return {
            "status": 500,
            "message": str(e)
        }