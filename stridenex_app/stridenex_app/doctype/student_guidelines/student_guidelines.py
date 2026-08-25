# Copyright (c) 2026, QTPL and contributors
# For license information, please see license.txt

# import frappe
from frappe.model.document import Document


class StudentGuidelines(Document):
	pass


import frappe
from frappe.utils import now


@frappe.whitelist(allow_guest=True)
def get_guidelines(module="Student", tab=None):

    filters = {
        "module": module,
        "is_active": 1
    }

    if tab:
        filters["tab"] = tab

    guidelines = frappe.get_all(
        "Student Guidelines",
        filters=filters,
        fields=[
            "name",
            "title",
            "module",
            "tab",
            "step_no",
            "description",
            "video_url",
            "image",
            "is_mandatory"
        ],
        order_by="step_no asc"
    )

    student = frappe.db.get_value(
        "Student",
        {"email_id": frappe.session.user},
        "name"
    )

    completed = 0

    for guideline in guidelines:

        status = "Pending"

        if student:
            progress = frappe.db.get_value(
                "Student Onboarding Progress",
                {
                    "student": student,
                    "guideline": guideline.name
                },
                "status"
            )

            if progress:
                status = progress

        guideline["status"] = status

        if status == "Completed":
            completed += 1

    total = len(guidelines)

    progress_percentage = (
        round((completed / total) * 100)
        if total
        else 0
    )

    return {
        "module": module,
        "tab": tab,
        "completed": completed,
        "total": total,
        "progress": progress_percentage,
        "steps": guidelines
    }

@frappe.whitelist()
def complete_onboarding(guideline):

    student = frappe.db.get_value(
        "Student",
        {"email_id": frappe.session.user},
        "name"
    )

    if not student:
        frappe.throw("Student not found")

    existing = frappe.db.exists(
        "Student Onboarding Progress",
        {
            "student": student,
            "guideline": guideline
        }
    )

    if existing:

        frappe.db.set_value(
            "Student Onboarding Progress",
            existing,
            {
                "status": "Completed",
                "completed_on": now()
            }
        )

    else:

        doc = frappe.get_doc({
            "doctype": "Student Onboarding Progress",
            "student": student,
            "guideline": guideline,
            "status": "Completed",
            "completed_on": now()
        })

        doc.insert(ignore_permissions=True)

    frappe.db.commit()

    return {
        "success": True,
        "message": "Onboarding step completed"
    }