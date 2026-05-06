import frappe
from frappe.model.document import Document
from frappe.utils import today
from stridenex_app.api_stridenex_app.app_utils import (
    gen_response,
    exception_handel,
    append_child_rows
)
class Internship(Document):
    def validate(self):
        # Deadline validation
        if self.deadline and self.deadline < today():
            frappe.throw("Deadline cannot be in the past")

    def before_save(self):
        # Auto status handling
        if self.deadline:
            if self.deadline < today():
                self.status = "Closed"
            elif not self.status:
                self.status = "Active"
                
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

@frappe.whitelist(allow_guest=True)
def create_internship():
    try:
        data = frappe.request.get_json()

        course_list = data.pop("course", [])
        department_list = data.pop("department", [])
        academic_year_list = data.pop("acdemic_year", [])
        # return academic_year_list

        internship = frappe.get_doc({
            "doctype": "Internship",
            **data
        })

        # ✅ Adjust keys based on child tables
        append_child_rows(internship, "course", course_list, "course")         # 🔁 change if needed
        append_child_rows(internship, "department", department_list, "department")  # 🔁 change if needed
        append_child_rows(internship, "academic_year", academic_year_list, "acdemic_year")  # ✅ confirmed

        internship.insert(ignore_permissions=True)
        frappe.db.commit()

        return gen_response(
            status=200,
            message="Internship registered successfully",
            data={"name": internship.title}
        )

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Create Internship Error")
        return {
            "status": 500,
            "message": str(e)
        }
        
@frappe.whitelist(allow_guest=True)
def get_internship_list(industry=None, student=None,course=None,department=None,academic_year=None):
    try:
        filters = {}

        if industry:
            filters["industry"] = industry
        if course:
            filters["course"]=course
        if department:
            filters["department"]=department
        if academic_year:
            filters["academic_year"]=academic_year

        internships = frappe.get_all(
            "Internship",
            filters=filters,
            fields=["*"],
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
            skill_map.setdefault(s["parent"], []).append({
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
                e["internship"]: e["status"] for e in enrollments
            }

        # ✅ Final response
        for internship in internships:
            internship["skills"] = skill_map.get(internship["name"], [])

            if student:
                internship["applied_status"] = enrollment_map.get(
                    internship["name"], "Not Applied"
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
        data = frappe.request.get_json()
        name = data.pop("name", None)

        if not name:
            return gen_response(
                status=400,
                message="Name is required",
                data=[]
            )

        # Extract Table MultiSelect and Child Table fields
        course_list = data.pop("course", None)
        department_list = data.pop("department", None)
        academic_year_list = data.pop("acdemic_year", None)
        required_skills = data.pop("required_skills", None)

        internship = frappe.get_doc("Internship", name)

        # Set simple fields
        for key, value in data.items():
            setattr(internship, key, value)

        # Course (Table MultiSelect)
        if course_list is not None:
            internship.set("course", [])
            for course in course_list:
                course_value = course if isinstance(course, str) else course.get("course")
                row = frappe.new_doc("Course Table")
                row.course = course_value
                internship.append("course", row)

        # Department (Table MultiSelect)
        if department_list is not None:
            internship.set("department", [])
            for department in department_list:
                department_value = department if isinstance(department, str) else department.get("department")
                row = frappe.new_doc("Department Table")
                row.department = department_value
                internship.append("department", row)

        # Academic Year (Table MultiSelect)
        if academic_year_list is not None:
            internship.set("acdemic_year", [])
            for year in academic_year_list:
                year_value = year if isinstance(year, str) else year.get("acdemic_year")
                row = frappe.new_doc("Academic Year Table")
                row.academic_year = year_value
                internship.append("acdemic_year", row)

        # Required Skills (Child Table)
        if required_skills is not None:
            internship.set("required_skills", [])
            for skill in required_skills:
                internship.append("required_skills", {
                    "skill": skill if isinstance(skill, str) else skill.get("skill")
                })

        internship.save(ignore_permissions=True)
        frappe.db.commit()

        return gen_response(
            status=200,
            message="Internship updated successfully",
            data={"name": internship.name}
        )

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Update Internship Error")
        return exception_handel(e)
    
@frappe.whitelist(allow_guest=True)
def inactive_internship(name):
    try:
        if not frappe.db.exists("Internship", name):
            return gen_response(
                status=404,
                message="Internship not found",
                data=[]
            )

        project = frappe.get_doc("Internship", name)
        project.status = "Closed"   # or "Inactive"
        project.save(ignore_permissions=True)
        frappe.db.commit()

        return gen_response(
            status=200,
            message="Internship marked as deleted",
            data={"name": name}
        )

    except Exception as e:
        return exception_handel(e)