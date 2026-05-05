import frappe
from stridenex_app.api_stridenex_app.app_utils import (
    gen_response,
    exception_handel
)


@frappe.whitelist(allow_guest=True)
def create_student(email=None):
    try:

        data = dict(frappe.form_dict)
        email = data.get("email")

        # Remove file field
        data.pop("resume", None)

        # Remove child tables
        data.pop("skill", None)
        data.pop("career_interest", None)
        data.pop("courses_type", None)

        student = frappe.get_doc({
            "doctype": "Student",
            **data
        })

        # Skills
        skills = frappe.request.form.getlist("skill[0][skill]")
        for skill in skills:
            student.append("skill", {"skill": skill})

        # Career Interest
        careers = frappe.request.form.getlist("career_interest[0][career_interest]")
        for c in careers:
            student.append("career_interest", {"career_interest": c})

        # Course Type
        courses = frappe.request.form.getlist("courses_type[0][course_type]")
        for course in courses:
            student.append("courses_type", {"course_type": course})

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
        if email and frappe.db.exists("User", email):
            frappe.db.set_value("User", email, "is_onboarded", 2)
            frappe.db.commit()
        create_student_user(student)

        return gen_response(
            status=200,
            message="Student registered successfully",
            data={"name": student.name}
        )

    except Exception as e:
        return exception_handel(e)


def create_student_user(student):

    email = student.email_id
    if not email:
        return

    # If user already exists (signup user)
    if frappe.db.exists("User", email):

        user = frappe.get_doc("User", email)

        existing_roles = [r.role for r in user.roles]

        if "Student" not in existing_roles:
            user.append("roles", {"role": "Student"})
            user.save(ignore_permissions=True)

    else:
        # Create new user
        user = frappe.get_doc({
            "doctype": "User",
            "email": email,
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

    # Link Student with User
    student.user = email
    student.save(ignore_permissions=True)

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
    


@frappe.whitelist(allow_guest=True)
def get_student_by_email(email_id):
    try:
        if not email_id:
            return {
                "status": 400,
                "message": "Email is required",
                "data": {}
            }

        # Fetch record using email
        data = frappe.db.get_value(
            "Student",  
            {"email_id": email_id},
            ["*"],
            as_dict=True
        )

        if not data:
            return {
                "status": 404,
                "message": "No record found",
                "data": {}
            }

        return {
            "status": 200,
            "message": "Data fetched successfully",
            "data": data
        }

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Get Details By Email Error")
        return {
            "status": 500,
            "message": str(e),
            "data": {}
        }
@frappe.whitelist(allow_guest=True)
def update_student(name=None):
    try:
        data = frappe.request.get_json()

        if not name:
            return {"status": 400, "message": "Student name (ID) is required"}

        doc = frappe.get_doc("Student", name)

        # Update only fields that are provided
        fields = [
            "first_name", "middle_name", "last_name",
            "email_id", "mobile_no", "college",
            "department", "course", "semester",
            "academic_year", "date_of_birth",
            "stream", "linkedin", "github", "gender"
        ]

        for field in fields:
            if field in data:
                doc.set(field, data.get(field))

        doc.save(ignore_permissions=True)

        return {
            "status": 200,
            "message": "Student updated successfully",
            "data": doc.name
        }

    except Exception as e:
        return {"status": 500, "message": str(e)}