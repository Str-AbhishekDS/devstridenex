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
        gen_response(400,"No data found",{"success":False})
    
        
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
    


@frappe.whitelist()
def get_semester():
    result = frappe.get_all("Semester",["*"])
    if result:
        gen_response(200,result)
    else:
        gen_response(400,"No data found", {"success": False})
        
@frappe.whitelist()
def get_stream():
    result = frappe.get_all("Stream",["stream_name"])
    if result:
        gen_response(200,"Stream found successfully",result)
    else:
        gen_response(400,"No data found", {"success": False})
        
        
        
        
        
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
def get_college_streams(college_name=None):
    try:
        # 1️⃣ Validate input
        if not college_name:
            return gen_response(400, "College is required", {"success": False})

        # 2️⃣ Check if college exists
        college_exists = frappe.db.exists("College", college_name)
        if not college_exists:
            return gen_response(400, "Invalid college selected", {"success": False})

        # 3️⃣ Fetch unique streams for that college
        streams = frappe.db.sql("""
            SELECT DISTINCT
                stream
            FROM `tabCourses`
            WHERE college = %s
        """, (college_name,), as_dict=True)

        # 4️⃣ If no streams found
        if not streams:
            return gen_response(400, "No streams found for this college", {"success": False})

        # 5️⃣ Success response
        return gen_response(200, "Streams fetched successfully", streams)

    except Exception as e:
        return exception_handel(e)
    
@frappe.whitelist(allow_guest=True)
def get_courses_type(college_name=None):
    try:
        # 1️⃣ Validate input
        if not college_name:
            return gen_response(400, "College is required", {"success": False})

        # 2️⃣ Check college exists
        college_exists = frappe.db.exists("College", college_name)
        if not college_exists:
            return gen_response(400, "Invalid college selected", {"success": False})

        # 3️⃣ Fetch unique course types
        course_types = frappe.db.sql("""
            SELECT DISTINCT
                course_type
            FROM `tabCourses`
            WHERE college = %s
            AND course_type IS NOT NULL
        """, (college_name,), as_dict=True)

        # 4️⃣ If empty
        if not course_types:
            return gen_response(400, "No course types found for this college", {"success": False})

        # 5️⃣ Success
        return gen_response(200, "Course types fetched successfully", course_types)

    except Exception as e:
        return exception_handel(e)
    
    
@frappe.whitelist(allow_guest=True)
def get_courses(college_name=None, stream=None):
    try:
        # 1️⃣ Validate inputs
        if not college_name:
            return gen_response(400, "College is required", {"success": False})

        if not stream:
            return gen_response(400, "Stream is required", {"success": False})

        # 2️⃣ Validate college exists
        college_exists = frappe.db.exists("College", college_name)
        if not college_exists:
            return gen_response(400, "Invalid college selected", {"success": False})

        # 3️⃣ Fetch unique courses
        courses = frappe.db.sql("""
            SELECT DISTINCT
                course_name
            FROM `tabCourses`
            WHERE college = %s
            AND stream = %s
            AND course_name IS NOT NULL
        """, (college_name, stream), as_dict=True)

        # 4️⃣ If no courses found
        if not courses:
            return gen_response(400, "No courses found", {"success": False})

        return gen_response(200, "Courses fetched successfully", courses)

    except Exception as e:
        return exception_handel(e)
    
    
# @frappe.whitelist(allow_guest=True)
# def get_college_departments(college_name=None, course=None):
#     try:
#         # 1️⃣ Validate inputs
#         if not college_name:
#             return gen_response(400, "College is required", {"success": False})

#         if not course:
#             return gen_response(400, "Course is required", {"success": False})

#         # 2️⃣ Validate college exists
#         college_exists = frappe.db.exists("College", college_name)
#         if not college_exists:
#             return gen_response(400, "Invalid college selected", {"success": False})

#         # 3️⃣ Fetch departments based on college + course
#         departments = frappe.db.sql("""
#             SELECT 
#                 department_name AS department,
#                 academic_years
#             FROM `tabCollege Department`
#             WHERE college = %s
#             AND courses = %s
#         """, (college_name, course), as_dict=True)

#         if not departments:
#             return gen_response(400, "No departments found", {"success": False})

#         return gen_response(200, "Departments fetched successfully", departments)

#     except Exception as e:
#         return exception_handel(e)
    
    
    
@frappe.whitelist(allow_guest=True)
def get_college_departments(college_name=None, course=None):
    try:
        # 1️⃣ Validate inputs
        if not college_name:
            return gen_response(400, "College is required", {"success": False})

        if not course:
            return gen_response(400, "Course is required", {"success": False})

        # 2️⃣ Validate college exists
        college_exists = frappe.db.exists("College", college_name)
        if not college_exists:
            return gen_response(400, "Invalid college selected", {"success": False})

        # 3️⃣ Fetch department data
        departments = frappe.db.sql("""
            SELECT 
                department_name AS department,
                academic_years
            FROM `tabCollege Department`
            WHERE college = %s
            AND courses = %s
        """, (college_name, course), as_dict=True)

        if not departments:
            return gen_response(400, "No departments found", {"success": False})

        # 4️⃣ Generate semesters dynamically
        final_data = []

        for dept in departments:
            academic_years = int(dept.get("academic_years", 0))
            total_semesters = academic_years * 2

            semesters = []
            for i in range(1, total_semesters + 1):
                semesters.append(f"Semester {i}")

            final_data.append({
                "department": dept["department"],
                "academic_years": academic_years,
                "semesters": semesters
            })

        return gen_response(200, "Departments fetched successfully", final_data)

    except Exception as e:
        return exception_handel(e)