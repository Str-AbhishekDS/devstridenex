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
        # ----------------------------------------------------------
        # PERMISSION CHECK
        # Respects Role Permission Manager configuration
        # ----------------------------------------------------------
        # session_user = frappe.session.user

        # if not frappe.has_permission(
        #     "Student Project Enrollment",
        #     ptype="create",
        #     user=session_user
        # ):
        #     frappe.throw(
        #         "You do not have permission to create Student Project Enrollment.",
        #         frappe.PermissionError
        #     )

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
            "industry": data.get("industry")
        })

        # Respects Role Permission Manager
        doc.insert(ignore_permissions=True)

        frappe.db.commit()

        return gen_response(
            status=200,
            message="Student Project Enrollemnt created successfully",
            data=doc
        )

    except Exception as e:
        return exception_handel(e)
    
    
@frappe.whitelist(allow_guest=False)
def get_application_count_by_industry(
    industry=None,
    project=None,
    status=None
):
    try:
        # ----------------------------------------------------------
        # PERMISSION CHECK
        # Respects Role Permission Manager configuration
        # ----------------------------------------------------------
        session_user = frappe.session.user

        if not frappe.has_permission(
            "Student Project Enrollment",
            ptype="read",
            user=session_user
        ):
            frappe.throw(
                "You do not have permission to access Student Project Enrollment.",
                frappe.PermissionError
            )

        filters = {}

        # ✅ Optional filter
        if industry:
            filters["industry"] = industry

        if project:
            filters["project"] = project

        if status:
            filters["status"] = status

        # ✅ Count total applications
        total_count = frappe.db.count(
            "Student Project Enrollment",
            filters
        )

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