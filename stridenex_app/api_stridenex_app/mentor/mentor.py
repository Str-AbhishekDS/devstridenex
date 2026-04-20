import json

import frappe
from stridenex_app.api_stridenex_app.app_utils import (
    gen_response,
    exception_handel
)


@frappe.whitelist(allow_guest=True)
def create_mentor():
    try:
        data = frappe.request.get_json()
        email = data.get("email")

        mentor = frappe.get_doc({
            "doctype": "Mentor",
            **data
        })

        mentor.insert(ignore_permissions=True)

        create_mentor_user(mentor)
        if email and frappe.db.exists("User", email):
            frappe.db.set_value("User", email, "is_onboarded", 1)
            frappe.db.commit()

        return gen_response(
            status=200,
            message="Mentor registered successfully",
            data={"name": mentor.first_name}
        )

    except Exception as e:
        return exception_handel(e)


@frappe.whitelist()
def create_mentor_user(mentor=None):
    if not mentor:
        frappe.throw("Mentor data is required")

    if isinstance(mentor, str):
        mentor = frappe.parse_json(mentor)

    email = mentor.get("email_id")
    mobile = mentor.get("mobile_no")

    if not email:
        frappe.throw("Email is required")

    if not mobile:
        frappe.throw("Mobile number is required")

    if frappe.db.exists("Mentor", email):
        mentor_doc = frappe.get_doc("Mentor", email)
    else:
        mentor_doc = frappe.get_doc({
            "doctype": "Mentor",
            "email_id": email,
            "first_name": mentor.get("first_name"),
            "last_name": mentor.get("last_name"),
            "mobile_no": mobile
        })
        mentor_doc.insert(ignore_permissions=True)

    if frappe.db.exists("User", email):
        user = frappe.get_doc("User", email)
        roles = [r.role for r in user.roles]

        if "Mentor" not in roles:
            user.append("roles", {"role": "Mentor"})

        if "Instructor" not in roles:
            user.append("roles", {"role": "Instructor"})

        user.save(ignore_permissions=True)

    else:
        user = frappe.get_doc({
            "doctype": "User",
            "email": email,
            "first_name": mentor.get("first_name"),
            "last_name": mentor.get("last_name"),
            "enabled": 1,
            "send_welcome_email": 0,
            "roles": [
                {"role": "Mentor"},
                {"role": "Instructor"}
            ]
        })
        user.insert(ignore_permissions=True)

    mentor_doc.user = email
    mentor_doc.save(ignore_permissions=True)

    return {
        "status": "success",
        "mentor": mentor_doc.name,
        "user": email
    }
