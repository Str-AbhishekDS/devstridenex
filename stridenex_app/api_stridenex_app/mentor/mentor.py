import frappe 
from stridenex_app.api_stridenex_app.app_utils import (
    gen_response, 
    generate_key, 
    exception_handel
)

@frappe.whitelist(allow_guest=True)
def create_mentor():
    try:
        data = frappe.request.get_json()

        mentor = frappe.get_doc({
            "doctype": "Mentor",
            **data
        })

        mentor.insert(ignore_permissions=True)
        create_mentor_user(mentor)
        frappe.db.commit()

        return gen_response(
            status=200,
            message="Mentor registered successfully",
            data={"name": mentor.first_name}
        )

    except Exception as e:
        return exception_handel(e)

def create_mentor_user(mentor):
    
    # Check if user already exists
    if not frappe.db.exists("User", mentor.email_id):
        user = frappe.get_doc({
            "doctype": "User",
            "email": mentor.email_id,
            "first_name": mentor.first_name,
            "last_name": mentor.last_name,
            "enabled": 1,
            "send_welcome_email": 0,
            "roles": [
                {
                    "role": "Mentor"
                }
            ]
        })

        user.insert(ignore_permissions=True)

    mentor.user = mentor.email_id