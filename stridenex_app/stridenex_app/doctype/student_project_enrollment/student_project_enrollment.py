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

@frappe.whitelist(allow_guest=True)
def get_application_count_by_industry(industry=None):
    try:
        filters = {}

        # ✅ Optional filter
        if industry:
            filters["industry"] = industry
        
        # ✅ Count total applications
        total_count = frappe.db.count("Student Project Enrollment", filters)

        return gen_response(
            status=200,
            message="Application count fetched successfully",
            data={
                "industry": industry if industry else "All",
                "total_applications": total_count
            }
        )

    except Exception as e:
        return exception_handel(e)

@frappe.whitelist(allow_guest=True)
def update_student_project_enrollment():
    try:
        data = frappe.request.get_json()

        enrollment_id = data.get("name")
        industry = data.get("industry")
        status = data.get("status")

        # ✅ Validation
        if not enrollment_id:
            return gen_response(400, "Enrollment ID (name) is required")

        # ✅ Fetch document
        doc = frappe.get_doc("Student Project Enrollment", enrollment_id)

        # ✅ Update industry (if provided)
        if industry:
            doc.industry = industry

        # ✅ Update status ONLY if not empty
        if status:
            doc.status = status

            # Optional date logic
            if status.lower() == "approved":
                doc.approved_on = frappe.utils.nowdate()

            if status.lower() == "completed":
                doc.completed_on = frappe.utils.nowdate()

        doc.save(ignore_permissions=True)
        frappe.db.commit()

        return gen_response(
            200,
            "Enrollment updated successfully",
            doc
        )

    except Exception as e:
        return exception_handel(e)