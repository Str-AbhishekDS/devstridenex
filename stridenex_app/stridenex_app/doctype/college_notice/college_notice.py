# Copyright (c) 2026, QTPL and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from stridenex_app.api_stridenex_app.app_utils import (
    gen_response,
    exception_handel,get_pagination_params,make_cache_key,make_pagination_meta
)
DEFAULT_PAGE_SIZE = 20
class CollegeNotice(Document):
	pass

@frappe.whitelist(allow_guest=True)
def get_college_notice_list(college=None, page=1, page_size=DEFAULT_PAGE_SIZE):
    try:
        page, page_size, limit, offset = get_pagination_params(page, page_size)

        filters = {}

        # Optional filter
        if college:
            filters["college"] = college

        # Get paginated events
        events = frappe.get_all(
            "College Notice",
            filters=filters,
            fields=["*"],
            order_by="creation desc",
            limit_page_length=limit,
            limit_start=offset
        )

        total = frappe.db.count("College Notice", filters=filters)

        return gen_response(
            status=200,
            message="College event list fetched successfully",
            data={
                "notice": events,
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
def create_college_notice():
    try:
        data = frappe.request.get_json()

        if not data:
            return {
                "status": 400,
                "message": "Request body is required"
            }

        doc = frappe.get_doc({
            "doctype": "College Notice",
            "college": data.get("college"),
            "notice": data.get("notice"),
            "date": data.get("date"),
            "notice_type": data.get("notice_type"),
            "company": data.get("company")
        })

        doc.insert(ignore_permissions=True)
        frappe.db.commit()

        return {
            "status": 200,
            "message": "College Notice created successfully",
            "data": {
                "name": doc.name
            }
        }

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Create College Notice Error")
        return {
            "status": 500,
            "message": str(e)
        }

@frappe.whitelist(allow_guest=True)
def update_college_notice(name):
    try:
        data = frappe.request.get_json()

        if not name:
            return {
                "status": 400,
                "message": "Document name is required"
            }

        doc = frappe.get_doc("College Notice", name)

        fields = [
            "college",
            "notice",
            "date",
            "notice_type",
            "company"
        ]

        for field in fields:
            if field in data:
                doc.set(field, data.get(field))

        doc.save(ignore_permissions=True)

        return {
            "status": 200,
            "message": "College Notice updated successfully"
        }

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Update College Notice Error")
        return {
            "status": 500,
            "message": str(e)
        
    }


@frappe.whitelist(allow_guest=True)
def delete_college_notice(name):
    try:
        if not name:
            return {
                "status": 400,
                "message": "Document name is required"
            }

        frappe.delete_doc(
            "College Notice",
            name,
            ignore_permissions=True
        )

        return {
            "status": 200,
            "message": "College Notice deleted successfully"
        }

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Delete College Notice Error")
        return {
            "status": 500,
            "message": str(e)
        }