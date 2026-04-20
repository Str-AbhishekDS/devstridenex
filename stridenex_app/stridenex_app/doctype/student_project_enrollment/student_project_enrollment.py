# Copyright (c) 2026, QTPL and contributors
# For license information, please see license.txt

# import frappe
from frappe.model.document import Document
from stridenex_app.api_stridenex_app.app_utils import (
    gen_response,
    exception_handel
)

import frappe
class StudentProjectEnrollment(Document):
	pass


@frappe.whitelist(allow_guest=True)
def create_student_project_enrollment():
    try:
        data = frappe.request.get_json()

        doc = frappe.get_doc({
            "doctype": "Student Project Enrollment",

            # 👇 fields based on your response
            "student": data.get("student"),
            "project": data.get("project"),
            "status": data.get("status") or "Applied",
            "applied_on": data.get("applied_on"),
            "resume": data.get("resume"),
            "match_score": data.get("match_score") or 0.0,
            "notes": data.get("notes"),
            "industry":data.get("industry")
        })

        doc.insert(ignore_permissions=True)
        frappe.db.commit()

        return gen_response(
            status=200,
            message="Student Project Enrollemnt created successfully",
            data=doc
        )

    except Exception as e:
        return exception_handel(e)