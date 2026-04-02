import frappe
from stridenex_app.api_stridenex_app.app_utils import (
    gen_response,
    exception_handel
)


@frappe.whitelist(allow_guest=True)
def create_industry():
    try:
        data = frappe.request.get_json()

        contact_details = data.pop("contact_details", [])

        industry = frappe.get_doc({
            "doctype": "Industry",
            **data
        })

        industry.insert(ignore_permissions=True)

        create_industry_users(contact_details)

        return gen_response(
            status=200,
            message="Industry registered successfully",
            data={"name": industry.name}
        )

    except Exception as e:
        return exception_handel(e)


def create_industry_users(contact_details):

    for contact in contact_details:

        email = contact.get("email")
        if not email:
            continue

        # Detect admin checkbox safely
        is_admin = int(contact.get("is_admin", 0))

        role = "Industry Admin" if is_admin == 1 else "Industry User"

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

@frappe.whitelist(allow_guest=True)
def update_industry(name):
    try:
        data = frappe.request.get_json()

        # Get existing Industry document
        industry = frappe.get_doc("Industry", name)

        # Update fields dynamically
        for key, value in data.items():
            industry.set(key, value)

        # Save updated document
        industry.save(ignore_permissions=True)

        return gen_response(
            status=200,
            message="Industry updated successfully",
            data={"name": industry.name}
        )

    except Exception as e:
        return exception_handel(e)