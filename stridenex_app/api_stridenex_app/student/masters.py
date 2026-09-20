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
def get_semester(semester=None, page=1, page_size=20, search=""):
    try:
        # Build ordered list of all semesters
        all_semesters = frappe.get_all(
            "Semester",
            fields=["name"],
            order_by="name asc"
        )

        if not all_semesters:
            return gen_response(400, "No semesters found", {"success": False})

        # If a specific semester is passed (e.g. "Semester 1", "Sem 1"),
        # filter to return only semesters from that semester onward
        if semester:
            sem_str = str(semester).strip().lower()

            # Find the matching record by flexible name comparison
            start_index = None
            for idx, s in enumerate(all_semesters):
                s_name = s["name"].strip().lower()
                # Match e.g. "sem 1" == "sem 1", or "semester 1" ~ "sem 1"
                s_digits = "".join(filter(str.isdigit, s_name))
                q_digits = "".join(filter(str.isdigit, sem_str))
                if s_name == sem_str or (s_digits and s_digits == q_digits):
                    start_index = idx
                    break

            if start_index is not None:
                result = all_semesters[start_index:]
            else:
                result = all_semesters
        else:
            result = all_semesters

        # Apply search filter if provided
        if search:
            result = [s for s in result if search.lower() in s["name"].lower()]

        return gen_response(200, "All Semester fetched successfully", {"data": result})

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Get Semester Error")
        return gen_response(500, str(e), {"success": False})


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



@frappe.whitelist(allow_guest=True)
def get_student_certificate_info(sr_no=None):

    if frappe.request.method != "GET":
        frappe.throw("Method not allowed")

    if not sr_no:
        gen_response(
            400,
            "Serial No is required",
            {"success": False}
        )
        return

    # ---------------------------------------------------------
    # 1. Get Certificate using Serial No
    # ---------------------------------------------------------
    certificate = frappe.db.get_value(
        "Certificate",
        {"sr_no": sr_no},
        [
            "name",
            "sr_no",
            "student_name",
            "assessment_name",
            "issued_date",
            "student_email"
        ],
        as_dict=True
    )

    if not certificate:
        gen_response(
            404,
            "Certificate not found",
            {
                "success": False,
                "sr_no": sr_no
            }
        )
        return

    student_email = certificate.get("student_email")

    if not student_email:
        gen_response(
            404,
            "Student email is not available in certificate",
            {
                "success": False,
                "sr_no": sr_no
            }
        )
        return

    # ---------------------------------------------------------
    # 2. Get Student/User information
    # ---------------------------------------------------------
    student = frappe.db.get_value(
        "User",
        {"email": student_email},
        [
            "name",
            "full_name",
   
        ],
        as_dict=True
    )

    if not student:
        gen_response(
            404,
            "Student not found",
            {
                "success": False,
                "email": student_email
            }
        )
        return

    # ---------------------------------------------------------
    # 3. Get Student Skill Ledger records
    # ---------------------------------------------------------
    skills = frappe.get_all(
        "Student Skill Ledger",
        filters={
            "student": student_email
        },
        fields=[
            "name",
            "student",
            
            "skill",
            "skill_level",
            "event_type",
            
        ],
        order_by="event_time desc"
    )

    # ---------------------------------------------------------
    # 4. Prepare response
    # ---------------------------------------------------------
    response_data = {
        "certificate": {
            "name": certificate.get("name"),
            "sr_no": certificate.get("sr_no"),
            "student_name": certificate.get("student_name"),
            "assessment_name": certificate.get("assessment_name"),
            "issued_date": certificate.get("issued_date")
        },

        "student": {
            "name": student.get("name"),
            "full_name": student.get("full_name"),
            "email": student.get("email"),
            "mobile_no": student.get("mobile_no"),
            "enabled": student.get("enabled")
        },

        "skills": skills,

        "skill_count": len(skills)
    }

    gen_response(
        200,
        "Certificate, student and skill information fetched successfully",
        {
            "success": True,
            "data": response_data
        }
    )
