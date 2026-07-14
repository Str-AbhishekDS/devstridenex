# Copyright (c) 2026, QTPL and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from stridenex_app.api_stridenex_app.app_utils import (
    gen_response,
    exception_handel,get_pagination_params,make_cache_key,make_pagination_meta
)


class CollegeEvent(Document):
	pass

DEFAULT_PAGE_SIZE = 20

@frappe.whitelist(allow_guest=True)
def get_college_event_list(college=None, student=None, page=1, page_size=DEFAULT_PAGE_SIZE):
    try:
        page, page_size, limit, offset = get_pagination_params(page, page_size)

        filters = {}

        # Optional filter
        if college:
            filters["college"] = college

        # Get paginated events
        events = frappe.get_all(
            "College Event",
            filters=[
                [
                    "College Event",
                    "participation_scope",
                    "=",
                    "Intra College"
                ],
                "or",
                [
                    "College Event",
                    "college",
                    "=",
                    college
                ]
            ],
            fields=["*"],
            order_by="creation desc",
            limit_page_length=limit,
            limit_start=offset
        )

        total = frappe.db.count("College Event", filters=[
                [
                    "College Event",
                    "participation_scope",
                    "=",
                    "Intra College"
                ],
                "or",
                [
                    "College Event",
                    "college",
                    "=",
                    college
                ]
            ],)

        # Get registration status (if student provided)
        registration_map = {}

        if student:
            registrations = frappe.get_all(
                "Student Event Registeration",
                filters={"student": student},
                fields=["event", "status"]
            )

            registration_map = {
                r["event"]: r["status"]
                for r in registrations
            }

        # Attach registration status
        for event in events:
            event["registration_status"] = (
                registration_map.get(event["name"], "Not Registered")
                if student
                else "Not Registered"
            )

        return gen_response(
            status=200,
            message="College event list fetched successfully",
            data={
                "events": events,
                "pagination": make_pagination_meta(
                    total,
                    page,
                    page_size
                )
            }
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
            "event_type": data.get("event_type"),
            "participation_scope":data.get("participation_scope")
        })

        doc.insert(ignore_permissions=True)
        frappe.db.commit()

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

        if not data:
            return {"status": 400, "message": "No data provided"}

        doc = frappe.get_doc("College Event", name)
       

        doc.update(data)

        doc.save(ignore_permissions=True)
        frappe.db.commit()

        return {
            "status": 200,
            "message": "College Event updated successfully",
            "data": doc.as_dict()
        }

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Update College Event Error")
        return {
            "status": 500,
            "message": str(e)
        }

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