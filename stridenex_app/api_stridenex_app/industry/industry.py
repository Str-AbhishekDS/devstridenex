import frappe
from stridenex_app.api_stridenex_app.app_utils import (
    gen_response,
    exception_handel
)

# industry apis
@frappe.whitelist(allow_guest=True)
def create_industry():
    try:
        data = frappe.request.get_json()

        contact_details = data.pop("contact_details", [])
        job_functions = data.pop("job_functions", [])
        email = data.get("email")

        industry = frappe.get_doc({
            "doctype": "Industry list",
            **data
        })
        # return contact_details

        # ✅ Fix job_functions
        if isinstance(job_functions, list):
            industry.job_functions = ", ".join(
                [j.get("job_function") for j in job_functions if isinstance(j, dict)]
            )

        # ✅ Contact Details
        for contact in contact_details:
            industry.append("contact_details", {
                "title": contact.get("title"),
                "first_name": contact.get("first_name"),
                "last_name": contact.get("last_name"),
                "designation": contact.get("designation"),
                "contact_no": contact.get("contact_no"),
                "email": contact.get("email")
            })
        # create_industry_users(contact_details)
        industry.insert(ignore_permissions=True)
        frappe.db.commit() 
        if email and frappe.db.exists("User", email):
            frappe.db.set_value("User", email, "is_onboarded", 1)
            frappe.db.commit()
                
        return gen_response(
            status=200,
            message="Industry registered successfully",
            data={"name": industry.name}
        )

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "CREATE INDUSTRY ERROR")
        frappe.throw(str(e))
    
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
def update_industry(company_name):
    try:
        data = frappe.request.get_json()
        industry = frappe.get_doc("Industry list", company_name)

        # ✅ Normal fields
        for key, value in data.items():
            industry.set(key, value)

        industry.save(ignore_permissions=True)
        frappe.db.commit()

        return gen_response(
            status=200,
            message="Industry updated successfully",
            data={"name": industry.name}
        )

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "UPDATE INDUSTRY ERROR")
        return exception_handel(e)
    
@frappe.whitelist(allow_guest=True)
def get_industry_by_name(email):
    try:
        if not email:
            return {"status": 400, "message": "User mail is required"}

        # ✅ Step 1: Get Industry directly using email field
        industries = frappe.get_all(
            "Industry list",
            filters={"email": email},
            fields=["name"]
        )

        if not industries:
            return {"status": 404, "message": "No industry found"}

        result = []

        # ✅ Step 2: Fetch full details
        for item in industries:
            doc = frappe.get_doc("Industry list", item.name)

            data = {
                "company_name": doc.company_name,
                "about": doc.about,
                "business_type": doc.business_type,
                "gst_number": doc.gst_number,
                "industry_sector": doc.industry_sector,
                "headquarters": doc.headquarters,
                "employee_head_count": doc.employee_head_count,
                "turn_over_in_cr": doc.turn_over_in_cr,
                "company_website": doc.company_website,
                "status": doc.status,
                "cin": doc.cin,

                "hiring_process": [
                    {
                        "name":row.name,
                        "round": row.round,
                        "based_on": row.based_on,
                        "duration": row.duration
                    }
                    for row in doc.table_nuet
                ]
            }

            result.append(data)

        return {
            "status": 200,
            "message": "Industries fetched successfully",
            "data": result
        }

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Get Industry Error")
        return {"status": 500, "message": str(e)}
# =====================child table apis=============================
@frappe.whitelist()
def add_required_role(industry_name, role, duration=None, semester=None, description=None, available_positions=None):
    try:
        doc = frappe.get_doc("Industry list", industry_name)

        doc.append("table_tehd", {
            "role": role,
            "duration": duration,
            "semester": semester,
            "description": description,
            "available_positions": available_positions
        })

        doc.save(ignore_permissions=True)
        frappe.db.commit()

        return {
            "status": 200,
            "message": "Required Role added successfully",
            "data": doc.table_tehd
        }

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Add Required Role Error")
        return {
            "status": 500,
            "message": str(e)
        }
    
@frappe.whitelist()
def add_hiring_round(industry_name, round, based_on=None, duration=None):
    try:
        doc = frappe.get_doc("Industry list", industry_name)

        doc.append("table_nuet", {
            "round": round,
            "based_on": based_on,
            "duration": int(duration) if duration else None
        })

        doc.save(ignore_permissions=True)
        frappe.db.commit()

        return {
            "status": 200,
            "message": "Hiring round added successfully",
            "data": doc.table_nuet   # ✅ FIXED
        }

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Add Hiring Round Error")
        return exception_handel(e)

@frappe.whitelist(allow_guest=True)
def delete_hiring_round(name, row_name):
    try:
        doc = frappe.get_doc("Industry list", name)
        

        row_to_delete = None

        for row in doc.table_nuet:
            if row.name == row_name:
                row_to_delete = row
                break
            
        if not row_to_delete:
            return {
                "status": 404,
                "message": "Row not found"
            }

        doc.remove(row_to_delete)

        doc.save(ignore_permissions=True)
        frappe.db.commit()

        return {
            "status": 200,
            "message": "Hiring round deleted successfully",
            "data": doc.table_nuet
        }

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Delete Hiring Round Error")
        return exception_handel(e)

@frappe.whitelist(allow_guest=True)
def update_hiring_round(industry_name, row_name, round=None, based_on=None, duration=None):
    try:
        doc = frappe.get_doc("Industry list", industry_name)

        updated = False

        for row in doc.table_nuet:
            if row.name == row_name:
                if round is not None:
                    row.round = round
                if based_on is not None:
                    row.based_on = based_on
                if duration is not None:
                    row.duration = int(duration)

                updated = True
                break

        if not updated:
            return {
                "status": 404,
                "message": "Row not found"
            }

        doc.save(ignore_permissions=True)
        frappe.db.commit()

        return {
            "status": 200,
            "message": "Hiring round updated successfully",
            "data": doc.table_nuet
        }

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Update Hiring Round Error")
        return exception_handel(e)