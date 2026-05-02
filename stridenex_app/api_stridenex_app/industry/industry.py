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
        email = data.get("email")

        industry = frappe.get_doc({
            "doctype": "Industry list",
            **data
        })
        
        industry.insert(ignore_permissions=True)
        if email and frappe.db.exists("User", email):
            if data.get("company_name"):  # Step 1
                onboarding_status = 1
            else:
                onboarding_status = 0  # optional (not started)
            frappe.db.set_value("User", email, "is_onboarded", onboarding_status)
        
                
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

        if not data:
            return gen_response(400, "Invalid request data")

        # ✅ Get doc with permission bypass
        industry = frappe.get_doc("Industry list", company_name)
        industry.flags.ignore_permissions = True

        # ✅ Extract fields
        contact_details = data.pop("contact_details", [])
        job_functions = data.pop("job_functions", [])
        email = data.get("email")

        ignore_fields = ["name", "doctype", "owner", "creation", "modified"]

        for key, value in data.items():
            if key not in ignore_fields:
                industry.set(key, value)

        # =========================
        # ✅ Job Function (replace)
        # =========================
        if isinstance(job_functions, list):
            industry.job_functions = ", ".join(
                [j.get("job_function") for j in job_functions if isinstance(j, dict)]
            )
            
        # =========================
        # ✅ Contact Details (replace)
        # =========================
        industry.set("contact_details", [])

        if isinstance(contact_details, list):
            for contact in contact_details:
                if isinstance(contact, dict):
                    industry.append("contact_details", {
                        "title": contact.get("title"),
                        "first_name": contact.get("first_name"),
                        "last_name": contact.get("last_name"),
                        "designation": contact.get("designation"),
                        "contact_no": contact.get("contact_no"),
                        "email": contact.get("email")
                    })

        # ✅ Save ONLY ONCE
        industry.save(ignore_permissions=True)

        # =========================
        # ✅ Create users
        # =========================
        create_industry_users(contact_details)

        # =========================
        # ✅ Onboarding logic
        # =========================
        if email and frappe.db.exists("User", email):
            onboarding_status = 0
            if data.get("country"):
                onboarding_status = 2
            if contact_details:
                onboarding_status = 3

            frappe.db.set_value("User", email, "is_onboarded", onboarding_status)

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

        # ✅ Get single industry name
        name = frappe.db.get_value("Industry list", {"email": email}, "name")

        if not name:
            return {"status": 404, "message": "No industry found"}

        # ✅ Fetch full document
        result = []
        doc = frappe.get_doc("Industry list", name)

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
                        "duration": row.duration,
                        "sequence":row.sequence
                    }
                    for row in doc.hiring_process
                ]
            }
        result.append(data)
 

        return {
            "status": 200,
            "message": "Industry fetched successfully",
            "data": data   # ✅ NOT a list
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

        doc.append("hiring_process", {
            "round": round,
            "based_on": based_on,
            "duration": int(duration) if duration else None
        })

        doc.save(ignore_permissions=True)
        frappe.db.commit()

        return {
            "status": 200,
            "message": "Hiring round added successfully",
            "data": doc.hiring_process   # ✅ FIXED
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