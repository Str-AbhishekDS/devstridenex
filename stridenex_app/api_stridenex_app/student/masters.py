import frappe 
from frappe.auth import LoginManager
from stridenex_app.api_stridenex_app.app_utils import (
    gen_response, 
    generate_key, 
    exception_handel
    ) 

@frappe.whitelist()
def get_course():
    result = frappe.get_all("Str Course",["*"])
    if result:
        gen_response(200,result)
    else:
        gen_response(400,"No data found")
    
        
@frappe.whitelist(allow_guest=True)
def get_college():
    try:
        colleges = frappe.db.sql("""
            SELECT 
                name,
                college_name
            FROM `tabCollege`
            WHERE is_active = 1
        """, as_dict=True)

        if not colleges:
            return gen_response(400, "No colleges found",{"success": False})

        return gen_response(200, "Colleges fetched successfully", colleges)

    except Exception as e:
        return exception_handel(e)
    
@frappe.whitelist(allow_guest=True)
def get_college_departments(college_name=None):
    try:
        if not college_name:
            return gen_response(400, "College is required",{"success": False})

        # Validate college exists
        college_exists = frappe.db.exists("College", college_name)
        if not college_exists:
            return gen_response(400, "Invalid college selected",{"success": False})

        departments = frappe.db.sql("""
            SELECT 
                department_name AS department,
                academic_years
            FROM `tabCollege Department`
            WHERE college = %s
        """, (college_name,), as_dict=True)

        if not departments:
            return gen_response(400, "No departments found for this college",{"success":False})

        return gen_response(200, "Departments fetched successfully", departments)

    except Exception as e:
        return exception_handel(e)
    

@frappe.whitelist(allow_guest=True)
def get_courses_type():
    result = frappe.get_all("Course Type",["*"])
    if result:
        gen_response(200,result)
    else:
        gen_response(400,"No data found")

@frappe.whitelist()
def get_semester():
    result = frappe.get_all("Semester",["*"])
    if result:
        gen_response(200,result)
    else:
        gen_response(400,"No data found")
