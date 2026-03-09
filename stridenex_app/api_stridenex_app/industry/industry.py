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
        contact_details = data.pop("contact_details", [])
        create_industry_users(contact_details)

        industry.insert(ignore_permissions=True)
        frappe.db.commit()

        return gen_response(
            status=200,
            message="Industry registered successfully",
            data={"name": industry.name}
        )

    except Exception as e:
        return exception_handel(e)

def create_industry_users(contact_details):
    for contact in contact_details:

        email = contact.get("")

        if not email:
            continue

        # Check if user already exists
        if not frappe.db.exists("User", email):

            user = frappe.get_doc({
                "doctype": "User",
                "email": email,
                "first_name": contact.get("first_name"),
                "last_name": contact.get("last_name"),
                "mobile_no": contact.get("contact_no"),
                "send_welcome_email": 0
            })

            user.insert(ignore_permissions=True)

            # Assign Role
            role = "Company Admin" if contact.get("is_admin") == 1 else "Company User"

            user.append("roles", {
                "role": role
            })

            user.save(ignore_permissions=True)