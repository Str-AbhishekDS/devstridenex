import frappe
from stridenex_app.api_stridenex_app.app_utils import (
    gen_response,
    exception_handel
)


@frappe.whitelist(allow_guest=True)
def create_college():
    try:
        data = frappe.request.get_json()
        email = data.get("email")

        

        college = frappe.get_doc({
            "doctype": "College",
            **data
        })

        college.insert(ignore_permissions=True)

        
        if email and frappe.db.exists("User", email):
            if data.get("college_name"):
                onboarding_status = 2
            else:
                onboarding_status = 1 
            frappe.db.set_value("User", email, "is_onboarded", onboarding_status)

        return gen_response(
            status=200,
            message="College registered successfully",
            data={"name": college.college_name}
        )

    except Exception as e:
        return exception_handel(e)


@frappe.whitelist(allow_guest=True)
def update_college(email):
    try:
        data = frappe.request.get_json()

        if not data:
            return gen_response(
                status=400,
                message="Invalid request data"
            )

        # Find College by email
        college_name = frappe.db.get_value(
            "College",
            {"email": email},
            "name"
        )

        if not college_name:
            return gen_response(
                status=404,
                message="College not found"
            )

        contact_details = data.pop("contact_details", [])

        college = frappe.get_doc("College", college_name)
        college.flags.ignore_permissions = True

        # Update parent fields
        for key, value in data.items():
            if frappe.get_meta("College").has_field(key):
                college.set(key, value)

        # Update child table
        if contact_details:
            college.set("contact_details", [])

            for row in contact_details:
                # Remap 'title' to 'salutation' if your child table field is named 'salutation'
                mapped_row = {
                    "salutation": row.get("title"),       # <-- key fix here
                    "first_name": row.get("first_name"),
                    "last_name": row.get("last_name"),
                    "designation": row.get("designation"),
                    "contact_no": row.get("contact_no"),
                    "email": row.get("email"),
                    "is_admin": row.get("is_admin", 0),
                }
                college.append("contact_details", mapped_row)

            create_college_users(contact_details)

        college.save(ignore_permissions=True)

        # Update onboarding status
        user_email = college.email

        if user_email and frappe.db.exists("User", user_email):
            onboarding_status = 0

            if college.country:
                onboarding_status = 3

            if contact_details:
                onboarding_status = 4

            frappe.db.set_value(
                "User",
                user_email,
                "is_onboarded",
                onboarding_status
            )

        frappe.db.commit()

        return gen_response(
            status=200,
            message="College updated successfully",
            data={
                "name": college.name,
                "college_name": college.college_name,
                "email": college.email
            }
        )

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Update College Error")
        return exception_handel(e)




def create_college_users(contact_details):

    for contact in contact_details:

        email = contact.get("email")
        if not email:
            continue

        is_admin = int(contact.get("is_admin", 0))
        role = "College Admin" if is_admin == 1 else "College Base"

        # User already exists
        if frappe.db.exists("User", email):
            user = frappe.get_doc("User", email)

            user.salutation = contact.get("title")
            user.first_name = contact.get("first_name")
            user.last_name = contact.get("last_name")
            user.mobile_no = contact.get("contact_no")

            existing_roles = [r.role for r in user.roles]

            if role not in existing_roles:
                user.append("roles", {"role": role})

            user.save(ignore_permissions=True)
            continue

        # Create new user
        user = frappe.get_doc({
            "doctype": "User",
            "email": email,
            "salutation":contact.get("title"),
            "first_name": contact.get("first_name"),
            "last_name": contact.get("last_name"),
            "mobile_no": contact.get("contact_no"),
            "send_welcome_email": 0,
            "roles": [
                {"role": "College Base"}
            ]
        })

        user.insert(ignore_permissions=True)

    return True


@frappe.whitelist(allow_guest=True)
def get_college(email):
    try:
        college_name = frappe.db.get_value(
            "College",
            {"email": email},
            "name"
        )

        if not college_name:
            return gen_response(
                status=404,
                message="College not found"
            )

        college = frappe.get_doc("College", college_name)

        # Get user details
        user_details = frappe.db.get_value(
            "User",
            email,
            ["first_name", "last_name", "mobile_no"],
            as_dict=True
        )

        data = college.as_dict()
        data["user_details"] = user_details or {}

        return gen_response(
            status=200,
            message="College fetched successfully",
            data=data
        )

    except Exception as e:
        return exception_handel(e)