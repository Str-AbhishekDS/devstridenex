# Copyright (c) 2026, QTPL and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from stridenex_app.api_stridenex_app.app_utils import (
    gen_response,
    exception_handel
)


class StudentInvitation(Document):
	pass


@frappe.whitelist(allow_guest=True)
def create_email_format():
    try:
        data = frappe.request.get_json()

        if not data or not data.get("form"):
            return {"status": 400, "message": "Form content is required"}

        # ✅ Create new document
        doc = frappe.new_doc("Student Invitation")

        # Optional fields (if you have them)
        doc.industry = data.get("industry")

        # ✅ Save Text Editor field
        doc.form = data.get("form")

        # Insert
        doc.insert(ignore_permissions=True)
        frappe.db.commit()

        return {
            "status": 200,
            "message": "Email format created successfully",
            "data": {
                "name": doc.name,
                "form": doc.form
            }
        }

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "create_email_format")
        return {"status": 500, "message": str(e)}

@frappe.whitelist()
def update_form(industry):
    try:
        data = frappe.request.get_json()

        doc = frappe.get_doc("Industry list", industry)
        doc.form = data.get("form")
        doc.save(ignore_permissions=True)

        return {
            "status": 200,
            "message": "Form saved successfully",
            "data": doc.form
        }

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Update Form Error")
        return {"status": 500, "message": str(e)}