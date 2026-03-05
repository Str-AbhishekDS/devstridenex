import frappe 
from stridenex_app.api_stridenex_app.app_utils import (
    gen_response, 
    generate_key, 
    exception_handel
)

@frappe.whitelist(allow_guest=True)
def create_college():
    try:
        data = frappe.request.get_json()

        college = frappe.get_doc({
            "doctype": "College",
            **data
        })

        college.insert(ignore_permissions=True)
        frappe.db.commit()

        return gen_response(
            status=200,
            message="College registered successfully",
            data={"name": college.college_name}
        )

    except Exception as e:
        return exception_handel(e)