import frappe 
from frappe.auth import LoginManager
from stridenex_app.api_stridenex_app.app_utils import (
    gen_response, 
    generate_key, 
    exception_handel
    ) 

@frappe.whitelist()
def get_course():
    result = frappe.get_all("Course",["name", "docstatus", "course_name", "department", "description"])
    if result:
        gen_response(200,result)
    else:
        gen_response(400,"No data found")

@frappe.whitelist()
def get_college():
    result = frappe.get_all("College",["name","college_name","status","registration_number","approved_status","college_code","university","college_type","website","is_active","country","state","district","city","taluka","approved_status_workflow","tahsil"])
    if result:
        gen_response(200,result)
    else:
        gen_response(400,"No data found")

@frappe.whitelist()
def get_department():
    result = frappe.get_all("Department",["*"])
    if result:
        gen_response(200,result)
    else:
        gen_response(400,"No data found")

@frappe.whitelist()
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
