# Copyright (c) 2026, QTPL and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class JobFunction(Document):
	pass
	
@frappe.whitelist(allow_guest=True)
def create_job_function():
    try:
        data = frappe.request.get_json()

        doc = frappe.get_doc({
            "doctype": "Job Function",
            "job_function": data.get("job_function")
        })

        doc.insert(ignore_permissions=True)
        frappe.db.commit()

        return {
            "status": "success",
            "message": "Job Function successfully",
            "data": doc.name
        }

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Job Function Error")
        return {
            "status": "error",
            "message": str(e)
        }
    
@frappe.whitelist(allow_guest=True)
def create_designation():
    try:
        data = frappe.request.get_json()

        doc = frappe.get_doc({
            "doctype": "Designation",
            "designation_name": data.get("designation_name")
        })

        doc.insert(ignore_permissions=True)
        frappe.db.commit()

        return {
            "status": "success",
            "message": "designation added successfully",
            "data": doc.name
        }

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "designation Error")
        return {
            "status": "error",
            "message": str(e)
        }