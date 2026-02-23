import frappe 
from stridenex_app.api_stridenex_app.app_utils import (
    gen_response, 
    generate_key, 
    exception_handel
    ) 

@frappe.whitelist(allow_guest=True)
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
            gen_response(200, "Student registration updated successfully.", student.name)
        else:
            duplicate_filters = {
                "fist_name": data.get("first_name"),
                "last_name": data.get("last_name"),
                "email_id": data.get("email_id"),
                "college": data.get("college")
            }

            duplicate = frappe.db.exists("Student", duplicate_filters)
            if duplicate:
                return gen_response(401, "Student <b>{duplicate}</b> is already present.")

            else:
                student = frappe.get_doc(dict(doctype="Student"))
                student.update(data)
                student.insert()
                gen_response(200, "Student registered successfully.", student.name)
    except frappe.PermissionError:
        return gen_response(500, "Not permitted for Student")
    except Exception as e:
        return exception_handel(e)
    
    


@frappe.whitelist(allow_guest=True)
def get_student(**kwargs):
    try:
        student_id = kwargs.get("name")
        email_id = kwargs.get("email_id")

        # -------------------------------
        # Case 1: Get Single Student by ID
        # -------------------------------
        if student_id:
            if not frappe.db.exists("Student", student_id):
                return gen_response(404, "Student not found.")

            student = frappe.get_doc("Student", student_id)

            return gen_response(200, "Student fetched successfully.", student)

        # -------------------------------
        # Case 2: Get Student by Email
        # -------------------------------
        if email_id:
            student = frappe.db.get_value(
                "Student",
                {"email_id": email_id},
                "*",
                as_dict=True
            )

            if not student:
                return gen_response(404, "Student not found.")

            return gen_response(200, "Student fetched successfully.", student)

        # -------------------------------
        # Case 3: Get All Students
        # -------------------------------
        students = frappe.get_all(
            "Student",
            fields=["name", "first_name", "last_name", "email_id", "college"]
        )

        return gen_response(200, "Student list fetched successfully.", students)

    except Exception as e:
        return exception_handel(e)
