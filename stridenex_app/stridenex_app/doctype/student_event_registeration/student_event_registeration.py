# Copyright (c) 2026, QTPL and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from stridenex_app.api_stridenex_app.app_utils import (
    gen_response,
    exception_handel
)


class StudentEventRegisteration(Document):
	pass

@frappe.whitelist(allow_guest=True)
def create_student_event_registeration():
    try:
        data = frappe.request.get_json()

        if not data:
            return {"status": 400, "message": "Request body is required"}

        doc = frappe.get_doc({
            "doctype": "Student Event Registeration",
            "event": data.get("event"),
            "student": data.get("student"),
            "status": data.get("status"),
        })

        doc.insert(ignore_permissions=True)
        frappe.db.commit()

        return {
            "status": 200,
            "message": "Student Event Registeration created successfully",
            "data": doc.name
        }

    except Exception as e:
        return exception_handel(e)