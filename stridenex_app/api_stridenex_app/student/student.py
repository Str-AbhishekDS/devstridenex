import frappe 
from stridenex_app.api_stridenex_app.app_utils import (
    gen_response, 
    generate_key, 
    exception_handel
    ) 

@frappe.whitelist(allow_guest=True)
def create_student():
    try:
        data = frappe.request.get_json()

        student = frappe.get_doc({
        "doctype": "Student",
        **data
        })

        student.insert(ignore_permissions=True)
        frappe.db.commit()

        return {"message": "Student registered successfully", "name": student.name}

    except Exception:
        frappe.log_error(frappe.get_traceback(), "Student API Error")
        return {"error": "Something went wrong"}

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