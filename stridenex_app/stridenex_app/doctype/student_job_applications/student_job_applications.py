# Copyright (c) 2026, QTPL and contributors
# For license information, please see license.txt

# import frappe
from frappe.model.document import Document
import frappe
from frappe import _
from frappe.utils import now_datetime



class StudentJobApplications(Document):
	pass




@frappe.whitelist(allow_guest=False)
def apply_for_job():
    try:
        data = frappe.form_dict

        student = data.get("student")
        job_profile = data.get("job_profile")

        if not student:
            frappe.throw(_("Student is required"))

        if not job_profile:
            frappe.throw(_("Job Profile is required"))


        # Duplicate application check
        if frappe.db.exists(
            "Student Job Applications",
            {
                "student": student,
                "job_profile": job_profile
            }
        ):
            frappe.throw(
                _("You have already applied for this job.")
            )


        # Get Job Profile
        job = frappe.get_doc(
            "Industry Job Profile",
            job_profile
        )


        if not job.is_active:
            frappe.throw(
                _("This job profile is currently inactive.")
            )


        if job.status != "Open":
            frappe.throw(
                _("Applications are closed for this job.")
            )


        application = frappe.new_doc("Student Job Applications")

        application.student = student
        application.job_profile = job_profile
        application.industry = job.industry
        application.application_date = now_datetime()
        application.status = "Applied"


        # Student Details
        # student_doc = frappe.get_doc(
        #     "Student",
        #     student
        # )

        # application.first_name = student_doc.student_name
        # application.student_email = student_doc.email
        # application.student_phone = student_doc.phone


        application.cover_letter = data.get("cover_letter")
        application.expected_salary = data.get("expected_salary")
        application.available_from = data.get("available_from")


        # Resume Upload
        if frappe.request.files.get("resume"):
            file = frappe.request.files.get("resume")
            frappe.errprint(f"Application Name: {application.name}")
            frappe.errprint(f"Type: {type(application.name)}")

            attachment = frappe.get_doc({
                "doctype": "File",
                "file_name": file.filename,
                "attached_to_doctype": "Student Job Applications",
                "attached_to_name": application.name,
                "content": file.read(),
                "is_private": 1
            })

            attachment.insert(ignore_permissions=True)

            application.resume = attachment.file_url


        application.insert(
            ignore_permissions=True
        )

        frappe.db.commit()


        return {
            "status": "success",
            "message": "Application submitted successfully",
            "application_id": application.name,
            "resume": application.resume
        }


    except Exception:
        frappe.db.rollback()
        frappe.log_error(
            frappe.get_traceback(),
            "Apply Job API Error"
        )
        raise


import frappe
from frappe import _

@frappe.whitelist(allow_guest=False)
def get_job_profile_list():
    student = frappe.form_dict.get("student")
    course = frappe.form_dict.get("course")
    department = frappe.form_dict.get("department")
    skill = frappe.form_dict.get("skill")

    filters = {
        "status": "Open",
        "is_active": 1
    }

    jobs = frappe.get_all(
        "Industry Job Profile",
        filters=filters,
        fields=[
            "name",
            "job_title",
            "industry",
            "experience",
            "employment_type",
            "location",
            "salary_from",
            "salary_to",
            "openings",
            "last_date",
            "published_on"
        ],
        order_by="creation desc"
    )

    result = []

    for job in jobs:

        # ---------- Course ----------
        courses = frappe.get_all(
            "Course Table",
            filters={"parent": job.name},
            pluck="course"
        )

        if course and course not in courses:
            continue

        # ---------- Department ----------
        departments = frappe.get_all(
            "Department Table",
            filters={"parent": job.name},
            pluck="department"
        )

        if department and department not in departments:
            continue

        # ---------- Skills ----------
        skills = frappe.get_all(
            "Student Skill Table",
            filters={"parent": job.name},
            pluck="skill"
        )

        if skill and skill not in skills:
            continue

        # ---------- Applied Status ----------
        applied = 0
        application_status = None

        if student:
            application = frappe.db.get_value(
                "Student Applications",
                {
                    "student": student,
                    "job_profile": job.name
                },
                "status"
            )

            if application:
                applied = 1
                application_status = application

        job["course"] = courses
        job["department"] = departments
        job["skills"] = skills
        job["applied"] = applied
        job["status"] = application_status


        result.append(job)

    return {
        "status": "success",
        "count": len(result),
        "data": result
    }