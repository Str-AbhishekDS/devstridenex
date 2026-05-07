# Copyright (c) 2026, QTPL and contributors
# For license information, please see license.txt

# import frappe
from frappe.model.document import Document
import frappe

from frappe.utils import today
from stridenex_app.api_stridenex_app.app_utils import (
    gen_response,
    exception_handel
)

class IndustryProject(Document):
	pass

@frappe.whitelist(allow_guest=True)
def create_project():
    try:
        data = frappe.request.get_json()

        course_list = data.pop("course", [])
        department_list = data.pop("department", [])
        academic_year_list = data.pop("academic_year", [])

        project = frappe.get_doc({
            "doctype": "Industry Project",
            **data
        })

        # Course
        for course in course_list:
            project.append("course", {
                "course": course if isinstance(course, str) else course.get("course")
            })

        # Department
        for department in department_list:
            project.append("department", {
                "department": department if isinstance(department, str) else department.get("department")
            })

        # Academic Year — field inside child DocType is "academic_year" (Link to "Academic Year")
        for year in academic_year_list:
            year_value = year if isinstance(year, str) else year.get("academic_year")
            row = frappe.new_doc("Academic Year Table")
            row.academic_year = year_value
            project.append("academic_year", row)

        project.insert(ignore_permissions=True)
        frappe.db.commit()

        return gen_response(
            status=200,
            message="Project registered successfully",
            data={"name": project.project_name}
        )

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Create Project Error")
        return exception_handel(e)
    

@frappe.whitelist(allow_guest=True)
def get_project_list(industry=None, student=None, status=None, course=None, department=None, academic_year=None):
    try:
        filters = {}
        if industry:
            filters["industry"] = industry
        if status:
            filters["status"] = status
        if course:
            filters["course"] = course
        if department:
            filters["department"] = department
        if academic_year:
            filters["academic_year"] = academic_year

        # ✅ Get all projects
        projects = frappe.get_all(
            "Industry Project",
            filters=filters,
            fields=[
                "name",
                "project_name",
                "description",
                "project_code",
                "duration",
                "start_date",
                "end_date",
                "status",
                "eligibility",
                "industry",
                "course",
                "department",
                "academic_year",
                "application_deadline"
            ],
            order_by="creation desc"
        )

        # ✅ Get enrollments (only once)
        enrollment_map = {}
        if student:
            enrollments = frappe.get_all(
                "Student Project Enrollment",
                filters={"student": student},
                fields=["project", "status"]
            )
            # Map: "project" → status
            enrollment_map = {
                e["project"]: e["status"] for e in enrollments
            }

        # ✅ Get all enrollments for count (only when student is None)
        all_enrollments = []
        if not student:
            all_enrollments = frappe.get_all(
                "Student Project Enrollment",
                fields=["project", "status"]
            )
        

        # ✅ Attach skills + applied status
        for project in projects:
            skills = frappe.get_all(
                "Student Skill Table",
                filters={"parent": project["name"]},
                fields=["skill"]
            )
            project["skills"] = skills

            # ✅ Fetch Table MultiSelect fields
            doc = frappe.get_doc("Industry Project", project["name"])
            project["course"] = [r.course for r in doc.course]
            project["department"] = [r.department for r in doc.department]
            project["academic_year"] = [r.academic_year for r in doc.academic_year]

            project_key = f"{project['project_name']}-{project['project_code']}"
            if student:
                project["applied_status"] = enrollment_map.get(project_key, "Not Applied")
            else:
                project["applied_status"] = None

            project_enrollments = [e for e in all_enrollments if e["project"] == project_key]
            project["applied_count"] = len(project_enrollments)
            project["shortlisted_count"] = len([e for e in project_enrollments if e["status"] == "Shortlisted"])

        return gen_response(
            status=200,
            message="Project list fetched successfully",
            data=projects
        )
    except Exception as e:
        return exception_handel(e)


@frappe.whitelist(allow_guest=True)
def get_project_by_id(project_name):
    try:
        project = frappe.get_doc("Industry Project", project_name)

        return gen_response(
            status=200,
            message="Project fetched successfully",
            data=project
        )

    except Exception as e:
        return exception_handel(e)
    
@frappe.whitelist(allow_guest=True)
def update_project(name):
    try:
        data = frappe.request.get_json()
        project = frappe.get_doc("Industry Project", name)

        course_list = data.pop("course", None)
        department_list = data.pop("department", None)
        academic_year_list = data.pop("academic_year", None)
        required_skills = data.pop("required_skills", None)

        for key, value in data.items():
            setattr(project, key, value)

        # Course
        if course_list is not None:
            project.set("course", [])
            for course in course_list:
                project.append("course", {
                    "course": course if isinstance(course, str) else course.get("course")
                })

        # Department
        if department_list is not None:
            project.set("department", [])
            for department in department_list:
                project.append("department", {
                    "department": department if isinstance(department, str) else department.get("department")
                })

        # Academic Year
        if academic_year_list is not None:
            project.set("academic_year", [])
            for year in academic_year_list:
                year_value = year if isinstance(year, str) else year.get("academic_year")
                row = frappe.new_doc("Academic Year Table")
                row.academic_year = year_value
                project.append("academic_year", row)

        # Required Skills
        if required_skills is not None:
            project.set("required_skills", [])
            for skill in required_skills:
                project.append("required_skills", {
                    "skill": skill if isinstance(skill, str) else skill.get("skill")
                })

        project.save(ignore_permissions=True)
        frappe.db.commit()

        return gen_response(
            status=200,
            message="Project updated successfully",
            data={"name": project.project_name}
        )

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Update Project Error")
        return exception_handel(e)
    
    
@frappe.whitelist(allow_guest=True)
def inactive_project(project_name):
    try:
        if not frappe.db.exists("Industry Project", project_name):
            return gen_response(
                status=404,
                message="Project not found",
                data=[]
            )

        project = frappe.get_doc("Industry Project", project_name)
        project.status = "Disable"   # or "Inactive"
        project.save(ignore_permissions=True)
        frappe.db.commit()

        return gen_response(
            status=200,
            message="Project marked as deleted",
            data={"name": project.name}
        )

    except Exception as e:
        return exception_handel(e)