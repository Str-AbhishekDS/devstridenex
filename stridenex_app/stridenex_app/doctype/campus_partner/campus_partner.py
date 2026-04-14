# Copyright (c) 2026, QTPL and contributors
# For license information, please see license.txt

# import frappe
from frappe.model.document import Document
import frappe

from stridenex_app.api_stridenex_app.app_utils import (
    gen_response,
    exception_handel
)

class CampusPartner(Document):
    pass

@frappe.whitelist(allow_guest=True)
def create_campus_partener():
    try:
        data = frappe.request.get_json()

        project = frappe.get_doc({
            "doctype": "Campus Partner",
            **data
        })

        project.insert(ignore_permissions=True)
        frappe.db.commit()
        return gen_response(
            status=200,
            message="Campus Partner registered successfully",
            data={"name": project.name}
        )

    except Exception as e:
        return exception_handel(e)
    

@frappe.whitelist(allow_guest=True)
def get_campus_partener_list(industry=None):
    try:
        filters = {}

        # Apply filter only if industry is provided
        if industry:
            filters["industry"] = industry
        

        projects = frappe.get_all(
            "Campus Partner",
            filters=filters,
            fields=["college"],
            order_by="creation desc"
        )
        return gen_response(
            status=200,
            message="Campus Partener fetched successfully",
            data=projects
        )
    except Exception as e:
        return exception_handel(e)


@frappe.whitelist(allow_guest=True)
def delete_campus_partener(name):
    try:
        if not name:
            return gen_response(
                status=400,
                message="Name is required",
                data=[]
            )

        # Check if document exists
        if not frappe.db.exists("Campus Partner", name):
            return gen_response(
                status=404,
                message="Campus Partner not found",
                data=[]
            )

        # Delete document
        frappe.delete_doc("Campus Partner", name, ignore_permissions=True)
        frappe.db.commit()

        return gen_response(
            status=200,
            message="Campus Partner deleted successfully",
            data={"name": name}
        )

    except Exception as e:
        return exception_handel(e)