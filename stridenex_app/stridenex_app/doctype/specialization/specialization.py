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

@frappe.whitelist(allow_guest=False)
def create_specialization():
    try:
        # ----------------------------------------------------------
        # PERMISSION CHECK
        # Respects Role Permission Manager configuration
        # ----------------------------------------------------------
        session_user = frappe.session.user

        if not frappe.has_permission(
            "Specialization",
            ptype="create",
            user=session_user
        ):
            frappe.throw(
                "You do not have permission to create Specialization.",
                frappe.PermissionError
            )

        data = frappe.request.get_json()

        # Check for duplicate
        if frappe.db.exists(
            "Specialization",
            data.get("specialization_name")
        ):
            return gen_response(
                status=409,
                message="Specialization already exists",
                data=[]
            )

        specialization = frappe.get_doc({
            "doctype": "Specialization",
            "specialization_name": data.get("specialization_name")
        })

        # Respects permissions
        specialization.insert()

        frappe.db.commit()

        return gen_response(
            status=200,
            message="Specialization created successfully",
            data={"name": specialization.name}
        )

    except Exception as e:
        frappe.log_error(
            frappe.get_traceback(),
            "Create Specialization Error"
        )
        return exception_handel(e)