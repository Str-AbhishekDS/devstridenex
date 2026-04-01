import frappe
from stridenex_app.api_stridenex_app.app_utils import (
    gen_response,
    exception_handel
)


@frappe.whitelist(allow_guest=True)
def create_college():
    try:
        data = frappe.request.get_json()

        contact_details = data.pop("contact_details", [])

        college = frappe.get_doc({
            "doctype": "College",
            **data
        })

        college.insert(ignore_permissions=True)

        create_college_users(contact_details)

        return gen_response(
            status=200,
            message="College registered successfully",
            data={"name": college.college_name}
        )

    except Exception as e:
        return exception_handel(e)


def create_college_users(contact_details):

    for contact in contact_details:

        email = contact.get("email")
        if not email:
            continue

        # Detect role
        is_admin = int(contact.get("is_admin", 0))

        role = "College Admin" if is_admin == 1 else "College User"

        # If user already exists (signup user)
        if frappe.db.exists("User", email):

            user = frappe.get_doc("User", email)

            existing_roles = [r.role for r in user.roles]

            if role not in existing_roles:
                user.append("roles", {"role": role})
                user.save(ignore_permissions=True)

        else:
            # Create new user
            user = frappe.get_doc({
                "doctype": "User",
                "email": email,
                "first_name": contact.get("first_name"),
                "last_name": contact.get("last_name"),
                "mobile_no": contact.get("contact_no"),
                "send_welcome_email": 0,
                "roles": [
                    {
                        "role": role
                    }
                ]
            })

            user.insert(ignore_permissions=True)

    return True