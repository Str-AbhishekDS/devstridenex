import frappe 
from stridenex_app.api_stridenex_app.app_utils import (
    gen_response, 
    generate_key, 
    exception_handel
)

@frappe.whitelist(allow_guest=True)
def create_industry():
    try:
        data = frappe.request.get_json()

        industry = frappe.get_doc({
            "doctype": "Industry",
            **data
        })

        industry.insert(ignore_permissions=True)
        frappe.db.commit()

        return gen_response(
            status=200,
            message="Industry registered successfully",
            data={"name": industry.name}
        )

    except Exception as e:
        return exception_handel(e)