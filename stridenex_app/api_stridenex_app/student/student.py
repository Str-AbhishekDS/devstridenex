import frappe 
from stridenex_app.api_stridenex_app.app_utils import (
    gen_response, 
    generate_key, 
    exception_handel
    ) 

@frappe.whitelist()
def create_student(*args, **kwargs):
    try:
        data = kwargs
        
        if not data.get("first_name"):
            return gen_response(500, "first_name is required.")
        if not data.get("last_name"):
            return gen_response(500, "last_name is required.")
        if not data.get("email_id"):
            return gen_response(500, "email_id is required.")
        if not data.get("college"):
            return gen_response(500, "college is required.")

        if data.get("name"):
            if not frappe.db.exists("Student", data.get("name"), cache=True):
                return gen_response(500, "Invalid Student Id.")
            student = frappe.get_doc("Student", data.get("name"))
            student.update(data)
            student.save()
            frappe.db.commit()
            gen_response(200, "Student registration updated successfully.", student.name)
        else:
            duplicate_filters = {
                "first_name": data.get("first_name"),
                "last_name": data.get("last_name"),
                "email_id": data.get("email_id"),
                "college": data.get("college")
            }

            duplicate = frappe.db.exists("Student", duplicate_filters)
            if duplicate:
                return gen_response(401, f"Student <b>{duplicate}</b> is already present.")

            else:
                student = frappe.get_doc(dict(doctype="Student"))
                student.update(data)
                student.insert()
                frappe.db.commit()
                gen_response(200, "Student registered successfully.", student.name)
    except frappe.PermissionError:
        return gen_response(500, "Not permitted for Student")
    except Exception as e:
        return exception_handel(e)



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