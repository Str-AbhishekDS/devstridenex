import frappe 
from stridenex_app.api_stridenex_app.app_utils import (
gen_response, 
generate_key, 
exception_handel
) 

import frappe


@frappe.whitelist(allow_guest=True)
def create_student():
    try:
        
        data = dict(frappe.form_dict)
        
        # Remove file field
        data.pop("resume", None)

        # Remove child table fields (we will process separately)
        data.pop("skill", None)
        data.pop("career_interest", None)
        data.pop("courses_type", None)

        student = frappe.get_doc({
        "doctype": "Student",
        **data
        })
        
        # Handle Skills
        skills = frappe.request.form.getlist("skill[0][skill]")
        for skill in skills:
            student.append("skill", {
                "skill": skill
            })
        

        # Handle Career Interest
        career = frappe.request.form.getlist("career_interest[0][career_interest]")
        for c in career:
            student.append("career_interest", {
                "career_interest": c
            })

        # Handle Course Type
        courses = frappe.request.form.getlist("courses_type[0][course_type]")
        for course in courses:
            student.append("courses_type", {
                "course_type": course
            })
        
        student.insert(ignore_permissions=True)

        # File Upload
        if "resume" in frappe.request.files:
            file = frappe.request.files["resume"]

            file_doc = frappe.get_doc({
                "doctype": "File",
                "file_name": file.filename,
                "attached_to_doctype": "Student",
                "attached_to_name": student.name,
                "content": file.read()
            })
            file_doc.save(ignore_permissions=True)
        
        create_student_user(student)
        frappe.db.commit()

        return gen_response(
            status=200,
            message="Student registered successfully",
            data={"name": student.name}
        )
    except Exception as e:
        return exception_handel(e)


def create_student_user(student):
    
    # Check if user already exists
    if not frappe.db.exists("User", student.email_id):
        user = frappe.get_doc({
            "doctype": "User",
            "email": student.email_id,
            "first_name": student.first_name,
            "last_name": student.last_name,
            "enabled": 1,
            "send_welcome_email": 0,
            "roles": [
                {
                    "role": "Student"
                }
            ]
        })

        user.insert(ignore_permissions=True)

    student.user = student.email_id

@frappe.whitelist()
def get_student(name=None, first_name=None, last_name=None, email_id=None, college=None):
    try:
        conditions = []
        values = {}

        if name:
            conditions.append("name = %(name)s")
            values["name"] = name

        if first_name:
            conditions.append("first_name = %(first_name)s")
            values["first_name"] = first_name

        if last_name:
            conditions.append("last_name = %(last_name)s")
            values["last_name"] = last_name

        if email_id:
            conditions.append("email_id = %(email_id)s")
            values["email_id"] = email_id

        if college:
            conditions.append("college = %(college)s")
            values["college"] = college

        where_clause = " AND ".join(conditions)

        sql = f"""
            SELECT name, first_name, last_name, email_id, college
            FROM `tabStudent`
            WHERE docstatus = 1
            {f'AND {where_clause}' if where_clause else ''}
        """

        result = frappe.db.sql(sql, values, as_dict=True)

        if not result:
            return gen_response(404, "No student found.")

        return gen_response(200, "Student fetched successfully.", result)

    except Exception as e:
        return exception_handel(e)