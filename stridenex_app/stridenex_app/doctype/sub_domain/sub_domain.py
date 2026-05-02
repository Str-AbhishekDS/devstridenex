# Copyright (c) 2026, QTPL and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from stridenex_app.api_stridenex_app.app_utils import (
    gen_response,
    exception_handel
)


class SubDomain(Document):
	pass


@frappe.whitelist(allow_guest=True)
def create_domain():
    try:
        data = frappe.request.get_json() or {}

        # ✅ Create new Domain document
        doc = frappe.get_doc({
            "doctype": "Domain",
            "domain": data.get("domain")   
        })
        if frappe.db.exists("Domain", {"domain": data.get("domain")}):
            return gen_response(409, "Domain already exists")

        doc.insert(ignore_permissions=True)
        frappe.db.commit()

        return gen_response(
            status=200,
            message="Domain created successfully",
            data=doc
        )

    except Exception as e:
        return exception_handel(e)

@frappe.whitelist(allow_guest=True)
def create_sub_domain():
    try:
        data = frappe.request.get_json() or {}

        # ✅ Create new Domain document
        doc = frappe.get_doc({
            "doctype": "Sub Domain",
            "domain": data.get("domain"),
            "sub_domain": data.get("sub_domain")  # field from your form
        })

        doc.insert(ignore_permissions=True)
        frappe.db.commit()

        return gen_response(
            status=200,
            message="Domain created successfully",
            data=doc
        )

    except Exception as e:
        return exception_handel(e)