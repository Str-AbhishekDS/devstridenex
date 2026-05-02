# Copyright (c) 2026, QTPL and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from stridenex_app.api_stridenex_app.app_utils import (
    gen_response,
    exception_handel
)


class CollegeEvent(Document):
	pass

@frappe.whitelist(allow_guest=True)
def get_college_event_list(college=None, student=None):
    try:
        filters = {}

        # ✅ Optional filter
        if college:
            filters["college"] = college

        events = frappe.get_all(
            "College Event",
            filters=filters,
            fields=[
                "*"
            ],
            order_by="creation desc"
        )

        # ✅ Get registration status (if student provided)
        registration_map = {}
        if student:
            registrations = frappe.get_all(
                "Student Event Registeration",
                filters={"student": student},
                fields=["event", "status"]
            )

            registration_map = {
                r["event"]: r["status"] for r in registrations
            }

        # ✅ Attach status
        for event in events:
            if student:
                event["registration_status"] = registration_map.get(
                    event["name"], "Not Registered"
                )
            else:
                event["registration_status"] = "Not Registered"

        return gen_response(
            status=200,
            message="College event list fetched successfully",
            data=events
        )

    except Exception as e:
        return exception_handel(e)
    

@frappe.whitelist(allow_guest=True)
def create_college_event():
    try:
        data = frappe.request.get_json()

        if not data:
            return {"status": 400, "message": "Request body is required"}

        doc = frappe.get_doc({
            "doctype": "College Event",
            "event": data.get("event"),
            "college": data.get("college"),
            "start_date": data.get("start_date"),
            "end_date": data.get("end_date"),
            "price": data.get("price"),
            "event_type": data.get("event_type")
        })

        doc.insert(ignore_permissions=True)

        return {
            "status": 200,
            "message": "College Event created successfully",
            "data": doc.name
        }

    except Exception as e:
        return {"status": 500, "message": str(e)}

@frappe.whitelist(allow_guest=True)
def update_college_event(name):
    try:
        data = frappe.request.get_json()

        if not name:
            return {"status": 400, "message": "Document name is required"}

        doc = frappe.get_doc("College Event", name)

        # Update only provided fields
        for field in ["event", "college", "start_date", "end_date", "price", "event_type"]:
            if field in data:
                doc.set(field, data.get(field))

        doc.save(ignore_permissions=True)

        return {
            "status": 200,
            "message": "College Event updated successfully"
        }

    except Exception as e:
        return {"status": 500, "message": str(e)}

@frappe.whitelist(allow_guest=True)
def delete_college_event(name):
    try:
        if not name:
            return {"status": 400, "message": "Document name is required"}

        frappe.delete_doc("College Event", name, ignore_permissions=True)

        return {
            "status": 200,
            "message": "College Event deleted successfully"
        }

    except Exception as e:
        return {"status": 500, "message": str(e)}