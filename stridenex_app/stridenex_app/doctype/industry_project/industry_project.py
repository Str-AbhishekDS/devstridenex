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

        project = frappe.get_doc({
            "doctype": "Industry Project",
            **data
        })

        project.insert(ignore_permissions=True)
        frappe.db.commit()
        return gen_response(
            status=200,
            message="Project registered successfully",
            data={"name": project.name}
        )

    except Exception as e:
        return exception_handel(e)
    

@frappe.whitelist(allow_guest=True)
def get_project_list(industry=None, student=None,status=None):
    try:
        filters = {}

        if industry:
            filters["industry"] = industry
        if status:
            filters["status"] = status

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
                "industry"
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

        # ✅ Attach skills + applied status
        for project in projects:

            # Skills
            skills = frappe.get_all(
                "Student Skill Table",
                filters={"parent": project["name"]},
                fields=["skill"]
            )
            project["skills"] = skills

            # ✅ Match project key
            project_key = f"{project['project_name']}-{project['project_code']}"

            if student:
                project["applied_status"] = enrollment_map.get(
                    project_key, "Not Applied"
                )
            else:
                project["applied_status"] = None

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
        for key, value in data.items():
            if key != "required_skills":
                setattr(project, key, value)

        if "required_skills" in data:
            project.set("required_skills", [])  # clear old rows

            for skill in data["required_skills"]:
                project.append("required_skills", {
                    "skill": skill.get("skill")
                })


        project.save(ignore_permissions=True)
        frappe.db.commit()

        return gen_response(
            status=200,
            message="Project updated successfully",
            data={"name": project.name}
        )

    except Exception as e:
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