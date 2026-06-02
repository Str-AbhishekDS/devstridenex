# Copyright (c) 2026, QTPL and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class JobFunction(Document):
	pass

@frappe.whitelist(allow_guest=False)
def create_job_function():
    try:
        # ----------------------------------------------------------
        # PERMISSION CHECK
        # Respects Role Permission Manager configuration
        # ----------------------------------------------------------
        session_user = frappe.session.user

        if not frappe.has_permission(
            "Job Function",
            ptype="create",
            user=session_user
        ):
            frappe.throw(
                "You do not have permission to create Job Function.",
                frappe.PermissionError
            )

        data = frappe.request.get_json()

        doc = frappe.get_doc({
            "doctype": "Job Function",
            "job_function": data.get("job_function")
        })

        # Respects Role Permission Manager
        doc.insert()

        frappe.db.commit()

        return {
            "status": "success",
            "message": "Job Function successfully",
            "data": doc.name
        }

    except Exception as e:
        frappe.log_error(
            frappe.get_traceback(),
            "Job Function Error"
        )

        return {
            "status": "error",
            "message": str(e)
        }
        
@frappe.whitelist(allow_guest=False)
def create_designation():
    try:
        session_user = frappe.session.user

        if not frappe.has_permission(
            "Industry Designation",
            ptype="create",
            user=session_user
        ):
            frappe.throw(
                "You do not have permission to create Industry Designation.",
                frappe.PermissionError
            )

        data = frappe.form_dict

        doc = frappe.get_doc({
            "doctype": "Industry Designation",
            "designation_name": data.get("designation_name")
        })

        doc.insert()
        frappe.db.commit()

        return {
            "status": "success",
            "message": "designation added successfully",
            "data": doc.name
        }

    except Exception as e:
        frappe.log_error(
            frappe.get_traceback(),
            "designation Error"
        )
        return {
            "status": "error",
            "message": str(e)
        }