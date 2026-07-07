# Copyright (c) 2026, QTPL and contributors
# For license information, please see license.txt

# import frappe
from frappe.model.document import Document


class StudentMentorMapping(Document):
	pass


import frappe
from frappe import _

@frappe.whitelist(allow_guest=True)
def create_student_mentor_mapping():
    try:
        data = frappe.request.get_json()

        if not data:
            return {
                "status": 400,
                "message": "Request body is required"
            }

        student = data.get("student")
        mentor = data.get("mentor")

        if not student:
            return {
                "status": 400,
                "message": "Student is required"
            }

        if not mentor:
            return {
                "status": 400,
                "message": "Mentor is required"
            }

        # Check duplicate mapping
        existing_mapping = frappe.db.exists(
            "Student Mentor Mapping",
            {
                "student": student,
                "mentor": mentor,
                "docstatus": ["!=", 2]
            }
        )

        if existing_mapping:
            return {
                "status": 409,
                "message": f"Mentor '{mentor}' is already assigned to Student '{student}'"
            }

        doc = frappe.new_doc("Student Mentor Mapping")
        doc.student = student
        doc.mentor = mentor
        doc.insert(ignore_permissions=True)

        return {
            "status": 201,
            "message": "Student Mentor Mapping created successfully",
            "data": {
                "name": doc.name,
                "student": doc.student,
                "mentor": doc.mentor
            }
        }

    except Exception as e:
        frappe.log_error(
            frappe.get_traceback(),
            "Create Student Mentor Mapping Error"
        )

        return {
            "status": 500,
            "message": "Something went wrong",
            "error": str(e)
        }