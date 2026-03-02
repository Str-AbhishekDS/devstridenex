import frappe
from stridenex_app.api_stridenex_app.app_utils import (
    gen_response, 
    generate_key, 
    exception_handel
    ) 


@frappe.whitelist(allow_guest=True)
def get_master_data(doctype=None, filters=None, fields=None):

    if not doctype:
        return gen_response(400, "DocType is required", {"success": False})

    try:
        if not filters:
            filters = {}

        if not fields:
            fields = ["name"]

        data = frappe.get_all(doctype, filters=filters, fields=fields)

        if data:
            return gen_response(200, f"{doctype} list retrieved successfully", data)
        else:
            return gen_response(404, "No data found", [])

    except Exception as e:
        return gen_response(500, str(e), {"success": False})