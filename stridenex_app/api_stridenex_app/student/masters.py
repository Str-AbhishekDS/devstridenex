import frappe 
from frappe.auth import LoginManager
from stridenex_app.api_stridenex_app.app_utils import (
    gen_response, 
    generate_key, 
    exception_handel
    ) 

  
@frappe.whitelist(allow_guest=True)
def get_colleges_by_stream(stream=None, state=None, district=None):
    try:
        if not stream:
            return gen_response(400, "Stream is required")

        conditions = " WHERE cc.stream = %(stream)s AND c.is_active = 1 "
        values = {"stream": stream}

        if state:
            conditions += " AND c.state = %(state)s "
            values["state"] = state

        if district:
            conditions += " AND c.district = %(district)s "
            values["district"] = district

        query = f"""
            SELECT DISTINCT c.name, c.college_name, c.state, c.district
            FROM `tabCollege` c
            INNER JOIN `tabCollege Courses Table` cc 
                ON cc.parent = c.name
            {conditions}
        """

        colleges = frappe.db.sql(query, values, as_dict=True)

        if not colleges:
            return gen_response(404, "No colleges found with given filters")

        return gen_response(200, "Colleges fetched successfully", colleges)

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Get Colleges By Stream Error")
        return gen_response(500, "Something went wrong", str(e))
    
        
@frappe.whitelist(allow_guest=True)
def get_semester(semester=None):

    if frappe.request.method not in ["GET"]:
        frappe.throw("Method not allowed")

    if semester:
        result = frappe.get_all(
            "Semester",
            fields=["name"],
            limit=int(semester)
        )
    else:
        result = frappe.get_all(
            "Semester",
            fields=["name"]
        )

    if result:
        gen_response(200,"All Semester fetched successfully", result)
    else:
        gen_response(400, "No data found", {"success": False})

@frappe.whitelist(allow_guest=True)
def get_user_by_mail(semester=None):

    if frappe.request.method not in ["GET"]:
        frappe.throw("Method not allowed")

    if semester:
        result = frappe.get_all(
            "Semester",
            fields=["name"],
            limit=int(semester)
        )
    else:
        result = frappe.get_all(
            "Semester",
            fields=["name"]
        )

    if result:
        gen_response(200,"All Semester fetched successfully", result)
    else:
        gen_response(400, "No data found", {"success": False})


@frappe.whitelist(allow_guest=True)
def get_user_by_mail(email=None):

    if frappe.request.method not in ["GET"]:
        frappe.throw("Method not allowed")

    if not email:
        gen_response(400, "Email is required", {"success": False})
        return

    user = frappe.get_all(
        "User",
        filters={"email": email},
        fields=["name", "full_name", "email", "mobile_no"]
    )

    if user:
        gen_response(200, "User fetched successfully", user)
    else:
        gen_response(404, "User not found", {"success": False})