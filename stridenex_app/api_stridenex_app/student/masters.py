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
        # 1️⃣ Get all active colleges
        colleges = frappe.get_all(
            "College",
            filters={"is_active": 1},
            fields=["name", "college_name"]
        )

        if not colleges:
            return gen_response(400, "No colleges found")

        final_data = []

        for college in colleges:

            # 2️⃣ Get departments of this college
            departments = frappe.get_all(
                "College Department",
                filters={
                    "college": college["name"],
                    
                },
                fields=[
                    "department_name as department",
                    "academic_years"   # This field stores 2, 4 etc.
                ]
            )

            dept_list = []

            for dept in departments:
                dept_list.append({
                    "department": dept.get("department"),
                    "academic_years": dept.get("academic_years")
                })

            final_data.append({
                "college_name": college.get("college_name"),
                "departments": dept_list
            })

        return gen_response(200, "College data fetched successfully", final_data)

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
