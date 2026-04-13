
import frappe
from frappe.model.document import Document
from frappe.utils import today
from stridenex_app.api_stridenex_app.app_utils import (
    gen_response,
    exception_handel
)


class IndustryRole(Document):
	pass


@frappe.whitelist(allow_guest=True)
def create_industry_role():
    try:
        data = frappe.request.get_json()

        industry = frappe.get_doc({
            "doctype": "Industry Role",
            **data
        })

        industry.insert(ignore_permissions=True)
        frappe.db.commit()

        return gen_response(
            status=200,
            message="Internship registered successfully",
            data={"name":industry.role }
        )

    except Exception as e:
        return exception_handel(e)
    
@frappe.whitelist(allow_guest=True)
def get_industry_role_list(industry=None):
    try:
        filters = {}

        # Apply filters only if provided
        if industry:
            filters["industry"] = industry


        roles = frappe.get_all(
            "Industry Role",
            filters=filters,
            fields=[
                "*"
            ],
            order_by="creation desc"
        )

        return gen_response(
            status=200,
            message="Industry role list fetched successfully",
            data=roles
        )

    except Exception as e:
        return exception_handel(e)
    

@frappe.whitelist(allow_guest=True)
def update_industry_role(name):
    try:
        
        data = frappe.request.get_json()
        if not name:
            return {"status": 400, "message": "name is required"}

        # Fetch existing document
        industry_role = frappe.get_doc("Industry Role", name)

        # Update all fields from request
        for key, value in data.items():
            setattr(industry_role, key, value)

        industry_role.save(ignore_permissions=True)
        frappe.db.commit()

        return gen_response(
            status=200,
            message="Industry Role updated successfully",
            data={"name": industry_role.name}
        )

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "update_industry_role")
        return exception_handel(e)