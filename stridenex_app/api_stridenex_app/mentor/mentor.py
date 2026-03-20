import frappe
from stridenex_app.api_stridenex_app.app_utils import (
    gen_response,
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

        return gen_response(
            status=200,
            message="Mentor registered successfully",
            data={"name": mentor.first_name}
        )

    except Exception as e:
        return exception_handel(e)


def create_mentor_user(mentor):

    email = mentor.email_id

    if not email:
        return

    # If user already exists (signup user)
    if frappe.db.exists("User", email):

        user = frappe.get_doc("User", email)

        existing_roles = [r.role for r in user.roles]

        if "Mentor" not in existing_roles:
            user.append("roles", {"role": "Mentor"})
            user.save(ignore_permissions=True)

    else:
        # Create new user
        user = frappe.get_doc({
            "doctype": "User",
            "email": email,
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

    # Link mentor with user
    mentor.user = email
    mentor.save(ignore_permissions=True)