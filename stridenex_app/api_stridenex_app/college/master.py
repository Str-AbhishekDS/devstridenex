import frappe
from stridenex_app.api_stridenex_app.app_utils import (
    gen_response, 
    generate_key, 
    exception_handel
    ) 


# @frappe.whitelist(allow_guest=True)
# def get_master_data(doctype=None, filters=None, fields=None):

#     if not doctype:
#         return gen_response(400, "DocType is required", {"success": False})

#     try:
#         if not filters:
#             filters = {}

#         if not fields:
#             fields = ["name"]

#         data = frappe.get_all(doctype, filters=filters, fields=fields)

#         if data:
#             return gen_response(200, f"{doctype} list retrieved successfully", data)
#         else:
#             return gen_response(404, "No data found", [])

#     except Exception as e:
#         return gen_response(500, str(e), {"success": False})


@frappe.whitelist(allow_guest=True)
def get_master_data(doctype=None, filters=None, fields=None, page=1, page_size=20):
    if not doctype:
        return gen_response(400, "DocType is required", {"success": False})
    try:
        if not filters:
            filters = {}
        if not fields:
            fields = ["name"]

        # Parse filters if passed as JSON string (common when called via GET/query params)
        if isinstance(filters, str):
            filters = frappe.parse_json(filters)
        if isinstance(fields, str):
            fields = frappe.parse_json(fields)

        # Ensure page & page_size are valid integers
        try:
            page = int(page)
            page_size = int(page_size)
        except (ValueError, TypeError):
            page = 1
            page_size = 20

        if page < 1:
            page = 1
        if page_size < 1:
            page_size = 20

        limit_start = (page - 1) * page_size

        # Total count for pagination metadata (ignores limit/offset)
        total_count = frappe.db.count(doctype, filters=filters)

        data = frappe.get_all(
            doctype,
            filters=filters,
            fields=fields,
            limit_start=limit_start,
            limit_page_length=page_size,
        )

        if data:
            return gen_response(200, f"{doctype} list retrieved successfully", {
                "data": data,
                "pagination": {
                    "page": page,
                    "page_size": page_size,
                    "total_count": total_count,
                    "total_pages": (total_count + page_size - 1) // page_size,
                    "has_next": limit_start + page_size < total_count,
                    "has_prev": page > 1,
                }
            })
        else:
            return gen_response(404, "No data found", {
                "data": [],
                "pagination": {
                    "page": page,
                    "page_size": page_size,
                    "total_count": total_count,
                    "total_pages": (total_count + page_size - 1) // page_size,
                    "has_next": False,
                    "has_prev": page > 1,
                }
            })
    except Exception as e:
        return gen_response(500, str(e), {"success": False})