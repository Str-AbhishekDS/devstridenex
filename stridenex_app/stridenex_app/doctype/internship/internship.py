import frappe
from frappe.model.document import Document
from frappe.utils import today,getdate
from stridenex_app.api_stridenex_app.app_utils import (
    gen_response,
    exception_handel,
    append_child_rows
)


class Internship(Document):
    pass

    # def validate(self):

    #     if self.application_deadline:
    #         if getdate(self.application_deadline) < getdate(today()):
    #             frappe.throw("Deadline cannot be in the past")

    # def before_save(self):

    #     if self.application_deadline:

    #         if getdate(self.application_deadline) < getdate(today()):
    #             self.status = "Closed"

    #         elif not self.status:
    #             self.status = "Active"
                
@frappe.whitelist()
def get_match_score(student, internship):

    required_skills = frappe.get_all(
        "Internship skill table",
        filters={"parent": internship},
        pluck="skill"
    )

    student_skills = frappe.get_all(
        "Student Skill Table",
        filters={"student": student},   # ✅ FIXED HERE
        pluck="skill"
    )

    if not required_skills:
        return 100

    matched = list(set(required_skills) & set(student_skills))

    score = (len(matched) / len(required_skills)) * 100

    return round(score)
@frappe.whitelist(allow_guest=False)
def create_internship():
    try:
        # ----------------------------------------------------------
        # PERMISSION CHECK
        # Respects Role Permission Manager configuration
        # ----------------------------------------------------------
        session_user = frappe.session.user

        if not frappe.has_permission(
            "Internship",
            ptype="create",
            user=session_user
        ):
            frappe.throw(
                "You do not have permission to create Internship.",
                frappe.PermissionError
            )

        data = frappe.request.get_json()

        course_list = data.pop("course", [])
        department_list = data.pop("department", [])
        academic_year_list = data.pop("academic_year", [])

        internship = frappe.get_doc({
            "doctype": "Internship",
            **data
        })

        # Course
        for course in course_list:
            internship.append("course", {
                "course": (
                    course if isinstance(course, str)
                    else course.get("course")
                )
            })

        # Department
        for department in department_list:
            internship.append("department", {
                "department": (
                    department if isinstance(department, str)
                    else department.get("department")
                )
            })

        # Academic Year
        for year in academic_year_list:
            year_value = (
                year if isinstance(year, str)
                else year.get("academic_year")
            )

            row = frappe.new_doc("Academic Year Table")
            row.academic_year = year_value

            internship.append("academic_year", row)

        # Respects Role Permission Manager
        internship.insert()

        frappe.db.commit()

        return gen_response(
            status=200,
            message="Internship registered successfully",
            data={"name": internship.title}
        )

    except Exception as e:
        frappe.log_error(
            frappe.get_traceback(),
            "Create Internship Error"
        )

        return {
            "status": 500,
            "message": str(e)
        }
        
        
@frappe.whitelist(allow_guest=True)
def get_internship_list(
    industry=None,
    student=None,
    course=None,
    department=None,
    current_year=None,
    search=None
):
    try:
        # ----------------------------------------------------------
        # PERMISSION CHECK
        # Respects Role Permission Manager configuration
        # ----------------------------------------------------------
        # session_user = frappe.session.user

        # if not frappe.has_permission(
        #     "Internship",
        #     ptype="read",
        #     user=session_user
        # ):
        #     frappe.throw(
        #         "You do not have permission to access Internship.",
        #         frappe.PermissionError
        #     )

        filters = {}

        if industry:
            filters["industry"] = industry

        internship_names = None

        # Course filter
        if course:
            names = frappe.get_all(
                "Course Table",
                filters={"course": course},
                pluck="parent"
            )
            internship_names = set(names)

        # Department filter
        if department:
            names = frappe.get_all(
                "Department Table",
                filters={"department": department},
                pluck="parent"
            )

            if internship_names is None:
                internship_names = set(names)
            else:
                internship_names &= set(names)

        # Academic Year filter
        # if current_year:
        #     names = frappe.get_all(
        #         "Academic Year Table",
        #         filters={"academic_year": current_year},
        #         pluck="parent"
        #     )

        #     if internship_names is None:
        #         internship_names = set(names)
        #     else:
        #         internship_names &= set(names)
        or_filters = None
        if search:
            or_filters = [
                ["title", "like", f"%{search}%"],
                ["description", "like", f"%{search}%"],
                ["location", "like", f"%{search}%"],
            ]
        # Apply parent filter
        if internship_names is not None:
            if internship_names:
                filters["name"] = ["in", list(internship_names)]
            else:
                return gen_response(
                    status=200,
                    message="No internships found",
                    data=[]
                )

        internships = frappe.get_all(
            "Internship",
            filters=filters,
            or_filters=or_filters,
            fields=["name","creation","owner","title","duration","openings",
                    "required_skills","internship_type","location","required_skills",
                    "start_date","end_date","industry","type","work_mode","stipend","deadline",
                    "status","posted_by","description","eligibility","payment_mode"],
            order_by="creation desc"
        )
 
        
        internship_names = [i["name"] for i in internships]

        # ✅ Skills mapping
        all_skills = frappe.get_all(
            "Internship Required Skill",
            filters={"parent": ["in", internship_names]},
            fields=["parent", "skill"]
        )

        skill_map = {}

        for s in all_skills:
            skill_map.setdefault(
                s["parent"],
                []
            ).append({
                "skill": s["skill"]
            })

        # ✅ Application status mapping
        enrollment_map = {}

        if student:
            enrollments = frappe.get_all(
                "Internship Application",
                filters={"student": student},
                fields=["internship", "status"]
            )

            enrollment_map = {
                e["internship"]: e["status"]
                for e in enrollments
            }

        # ✅ Final response
        for internship in internships:

            internship["skills"] = skill_map.get(
                internship["name"],
                []
            )

            doc = frappe.get_doc(
                "Internship",
                internship["name"]
            )

            internship["course"] = [
                r.course for r in doc.course
            ]

            internship["department"] = [
                r.department for r in doc.department
            ]

            internship["academic_year"] = [
                r.academic_year for r in doc.academic_year
            ]

            if student:
                internship["applied_status"] = enrollment_map.get(
                    internship["name"],
                    "Not Applied"
                )
            else:
                internship["applied_status"] = "Not Applied"

        return gen_response(
            status=200,
            message="Internship list fetched successfully",
            data=internships
        )

    except Exception as e:
        return exception_handel(e)
    
    
@frappe.whitelist(allow_guest=True)
def update_internship():
    try:
        # ----------------------------------------------------------
        # PERMISSION CHECK
        # Respects Role Permission Manager configuration
        # ----------------------------------------------------------
        # session_user = frappe.session.user

        # if not frappe.has_permission(
        #     "Internship",
        #     ptype="write",
        #     user=session_user
        # ):
        #     frappe.throw(
        #         "You do not have permission to update Internship.",
        #         frappe.PermissionError
        #     )

        data = frappe.request.get_json()
        name = data.pop("name", None)

        if not name:
            return gen_response(
                status=400,
                message="Name is required",
                data=[]
            )

        # Pop Table MultiSelect and Child Table fields before setattr loop
        course_list = data.pop("course", None)
        department_list = data.pop("department", None)
        academic_year_list = data.pop("academic_year", None)
        required_skills = data.pop("required_skills", None)

        # Pop unknown/non-schema fields to avoid setattr noise
        data.pop("internship_name", None)

        internship = frappe.get_doc(
            "Internship",
            name
        )

        # Set all remaining simple fields
        for key, value in data.items():
            setattr(internship, key, value)

        # Course
        if course_list is not None:
            internship.set("course", [])

            for item in course_list:
                course_value = (
                    item if isinstance(item, str)
                    else item.get("course")
                )

                internship.append(
                    "course",
                    {"course": course_value}
                )

        # Department
        if department_list is not None:
            internship.set("department", [])

            for item in department_list:
                dept_value = (
                    item if isinstance(item, str)
                    else item.get("department")
                )

                internship.append(
                    "department",
                    {"department": dept_value}
                )

        # Academic Year
        if academic_year_list is not None:
            internship.set("academic_year", [])

            for item in academic_year_list:
                year_value = (
                    item if isinstance(item, str)
                    else item.get("academic_year")
                )

                internship.append(
                    "academic_year",
                    {"academic_year": year_value}
                )

        # Required Skills
        if required_skills is not None:
            internship.set("required_skills", [])

            for item in required_skills:
                skill_value = (
                    item if isinstance(item, str)
                    else item.get("skill")
                )

                internship.append(
                    "required_skills",
                    {"skill": skill_value}
                )

        # Respects Role Permission Manager
        internship.save()

        frappe.db.commit()

        return gen_response(
            status=200,
            message="Internship updated successfully",
            data={"name": internship.name}
        )

    except Exception as e:
        frappe.log_error(
            frappe.get_traceback(),
            "Update Internship Error"
        )

        return exception_handel(e)
    
    
@frappe.whitelist(allow_guest=False)
def inactive_internship(name):
    try:
        # ----------------------------------------------------------
        # PERMISSION CHECK
        # Respects Role Permission Manager configuration
        # ----------------------------------------------------------
        session_user = frappe.session.user

        if not frappe.has_permission(
            "Internship",
            ptype="write",
            user=session_user
        ):
            frappe.throw(
                "You do not have permission to update Internship.",
                frappe.PermissionError
            )

        if not frappe.db.exists(
            "Internship",
            name
        ):
            return gen_response(
                status=404,
                message="Internship not found",
                data=[]
            )

        project = frappe.get_doc(
            "Internship",
            name
        )

        project.status = "Closed"  # or "Inactive"

        # Respects Role Permission Manager
        project.save()

        frappe.db.commit()

        return gen_response(
            status=200,
            message="Internship marked as deleted",
            data={"name": name}
        )

    except Exception as e:
        return exception_handel(e)