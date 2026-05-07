# Copyright (c) 2026, QTPL and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from stridenex_app.api_stridenex_app.app_utils import (
    gen_response,
    exception_handel,
)


class Specialization(Document):
	pass


@frappe.whitelist(allow_guest=True)
def create_specialization():
    try:
        data = frappe.request.get_json()

        # Check for duplicate
        if frappe.db.exists("Specialization", data.get("specialization_name")):
            return gen_response(
                status=409,
                message="Specialization already exists",
                data=[]
            )

        specialization = frappe.get_doc({
            "doctype": "Specialization",
            "specialization_name": data.get("specialization_name")
        })

        specialization.insert(ignore_permissions=True)
        frappe.db.commit()

        return gen_response(
            status=200,
            message="Specialization created successfully",
            data={"name": specialization.name}
        )

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Create Specialization Error")
        return exception_handel(e)