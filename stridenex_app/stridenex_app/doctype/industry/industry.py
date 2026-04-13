# Copyright (c) 2026, QTPL and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class Industry(Document):
	pass


@frappe.whitelist()
def get_required_roles(company_name):
    try:
        doc = frappe.get_doc("Company", company_name)

        roles = []
        for row in doc.required_roles:  # child table fieldname
            roles.append({
                "role": row.role,
                "duration": row.duration,
                "semester": row.semester,
                "description": row.description,
                "available_positions": row.available_positions
            })

        return {
            "status": "success",
            "data": roles
        }

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Get Required Roles Error")
        return {"status": "error", "message": str(e)}
    
@frappe.whitelist()
def get_hiring_process(company_name):
    try:
        doc = frappe.get_doc("Company", company_name)

        process = []
        for row in doc.hiring_process:  # child table fieldname
            process.append({
                "round": row.round,
                "based_on": row.based_on,
                "duration": row.duration
            })

        return {
            "status": "success",
            "data": process
        }

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Get Hiring Process Error")
        return {"status": "error", "message": str(e)}