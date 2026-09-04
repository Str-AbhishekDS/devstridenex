# Copyright (c) 2026, QTPL and contributors
# For license information, please see license.txt

# import frappe
from frappe.model.document import Document


class StudentGuidelines(Document):
	pass


import frappe
from frappe.utils import now


@frappe.whitelist(allow_guest=True)
def get_guidelines(module,tab,student):

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

    # student = frappe.db.get_value(
    #     "Student",
    #     {"email_id": frappe.session.user},
    #     "name"
    # )

    completed = 0

    for guideline in guidelines:

        status = "Pending"

        if student:
            progress = frappe.db.get_value(
                "Student Guideline Progress",
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



@frappe.whitelist(allow_guest=True)
def complete_onboarding(guideline, student):

    if not guideline:
        frappe.throw("Guideline is required")

    if not student:
        frappe.throw("Student is required")

    # Check existing progress directly in DB
    existing = frappe.db.sql("""
        SELECT name
        FROM `tabStudent Guideline Progress`
        WHERE student = %s
        AND guideline = %s
        LIMIT 1
    """, (student, guideline), as_dict=True)

    if existing:
        frappe.db.sql("""
            UPDATE `tabStudent Guideline Progress`
            SET status = %s,
                completed_on = %s
            WHERE name = %s
        """, ("Completed", now(), existing[0].name))

    else:
        name = frappe.generate_hash(length=10)

        frappe.db.sql("""
            INSERT INTO `tabStudent Guideline Progress`
            (
                name,
                creation,
                modified,
                modified_by,
                owner,
                docstatus,
                student,
                guideline,
                status,
                completed_on
            )
            VALUES
            (
                %s,
                %s,
                %s,
                %s,
                %s,
                0,
                %s,
                %s,
                %s,
                %s
            )
        """, (
            name,
            now(),
            now(),
            "Guest",
            "Guest",
            student,
            guideline,
            "Completed",
            now()
        ))

    frappe.db.commit()

    return {
        "success": True,
        "message": "Onboarding step completed",
        "student": student,
        "guideline": guideline,
        "status": "Completed"
    }