# Copyright (c) 2026, QTPL and contributors
# For license information, please see license.txt

# import frappe
from frappe.model.document import Document
import frappe
from frappe import _
from frappe.utils import now_datetime
from frappe.exceptions import ValidationError


class IndustryJobProfile(Document):
	pass





@frappe.whitelist(allow_guest=False)
def create_job_profile():
    try:
        data = frappe.request.get_json()
        job_title = data.get("job_title")
        industry = data.get("industry")

        # Duplicate check
        if frappe.db.exists(
            "Industry Job Profile",
            {
                "job_title": job_title,
                "industry": industry
            }
        ):
            frappe.throw(
                _("Job Profile '{0}' already exists for Industry '{1}'.").format(
                    job_title, industry
                )
            )

        doc = frappe.new_doc("Industry Job Profile")
        

        doc.job_title = data.get("job_title")
        doc.industry = data.get("industry")
        doc.job_description = data.get("job_description")
        doc.experience = data.get("experience")
        doc.employment_type = data.get("employment_type")
        doc.location = data.get("location")
        doc.salary_from = data.get("salary_from")
        doc.salary_to = data.get("salary_to")
        doc.openings = data.get("openings")
        doc.last_date = data.get("last_date")
        doc.contact_person = data.get("contact_person")
        doc.contact_email = data.get("contact_email")
        doc.contact_phone = data.get("contact_phone")
        doc.status = data.get("status") or "Open"
        doc.is_active = data.get("is_active", 1)
        doc.published_on = now_datetime()

        # Department (Table MultiSelect)
        for department in data.get("department", []):
            doc.append("department", {
                "department": department
            })

        # Course (Table MultiSelect)
        for course in data.get("course", []):
            doc.append("course", {
                "course": course
            })

        # Skills Required (Table)
        for skill in data.get("skills_required", []):
            doc.append("skills_required", {
                "skill": skill.get("skill")
            })

        doc.insert(ignore_permissions=True)
        frappe.db.commit()

        return {
            "status": "success",
            "message": "Job Profile Created Successfully",
            "name": doc.name
        }
    except ValidationError:
         raise
    
    except Exception:
        frappe.db.rollback()
        frappe.log_error(frappe.get_traceback(), "Create Job Profile API")
        



@frappe.whitelist(allow_guest=True)
def get_job_profiles(industry=None):

    filters = {}

    if industry:
        filters["industry"] = industry

    jobs = frappe.get_all(
        "Industry Job Profile",
        filters=filters,
        fields=[
            "name",
            "job_title",
            "industry",
            "experience",
            "job_description",
            "employment_type",
            "location",
            "salary_from",
            "salary_to",
            "openings",
            "last_date",
            "contact_person",
            "contact_email",
            "contact_phone",
           
            "status",
            "is_active",
            "published_on"
        ]
    )

    result = []

    for job in jobs:

        departments = frappe.get_all(
            "Department Table",
            filters={"parent": job.name},
            fields=["department"]
        )

        courses = frappe.get_all(
            "Course Table",
            filters={"parent": job.name},
            fields=["course"]
        )

        skills = frappe.get_all(
            "Student Skill Table",
            filters={"parent": job.name},
            fields=["skill"]
        )

        job["department"] = departments
        job["education"] = courses
        job["skills_required"] = skills

        result.append(job)

    return {
        "status": "success",
        "data": result
    }



@frappe.whitelist(allow_guest=False)
def delete_job_profile(name):
    try:
        if not name:
            frappe.throw(_("Job Profile name is required"))

        doc = frappe.get_doc("Industry Job Profile", name)

        if doc.docstatus != 0:
            frappe.throw(_("Only Draft Job Profiles can be deleted."))

        frappe.delete_doc(
            "Industry Job Profile",
            name,
            ignore_permissions=True
        )

        frappe.db.commit()

        return {
            "status": "success",
            "message": "Job Profile Deleted Successfully"
        }

    except Exception:
        frappe.db.rollback()
        frappe.log_error(frappe.get_traceback(), "Delete Job Profile")
        frappe.throw(_("Something went wrong"))


import frappe
from frappe import _

@frappe.whitelist(allow_guest=False)
def update_job_profile():
    try:
        data = frappe.request.get_json()

        if not data.get("name"):
            frappe.throw(_("Job Profile name is required"))

        doc = frappe.get_doc("Industry Job Profile", data.get("name"))

        if doc.docstatus != 0:
            frappe.throw(_("Only Draft Job Profiles can be updated."))

        doc.job_title = data.get("job_title", doc.job_title)
        doc.industry = data.get("industry", doc.industry)
        doc.experience = data.get("experience", doc.experience)
        doc.job_description = data.get("job_description", doc.job_description)
        doc.employment_type = data.get("employment_type", doc.employment_type)
        doc.location = data.get("location", doc.location)
        doc.salary_from = data.get("salary_from", doc.salary_from)
        doc.salary_to = data.get("salary_to", doc.salary_to)
        doc.openings = data.get("openings", doc.openings)
        doc.last_date = data.get("last_date", doc.last_date)
        doc.contact_person = data.get("contact_person", doc.contact_person)
        doc.contact_email = data.get("contact_email", doc.contact_email)
        doc.contact_phone = data.get("contact_phone", doc.contact_phone)
        doc.attachment = data.get("attachment", doc.attachment)
        doc.status = data.get("status", doc.status)
        doc.is_active = data.get("is_active", doc.is_active)

        # Clear child tables
        doc.set("department", [])
        doc.set("education", [])
        doc.set("skills_required", [])

        # Department
        for department in data.get("department", []):
            doc.append("department", {
                "department": department
            })

        # Education
        for course in data.get("education", []):
            doc.append("education", {
                "course": course
            })

        # Skills
        for skill in data.get("skills_required", []):
            doc.append("skills_required", {
                "skill": skill.get("skill")
            })

        doc.save(ignore_permissions=True)
        frappe.db.commit()

        return {
            "status": "success",
            "message": "Job Profile Updated Successfully",
            "name": doc.name
        }

    except Exception:
        frappe.db.rollback()
        frappe.log_error(frappe.get_traceback(), "Update Job Profile")
        frappe.throw(_("Something went wrong"))