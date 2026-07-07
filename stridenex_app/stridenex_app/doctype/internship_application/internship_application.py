# Copyright (c) 2026, QTPL and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import now
from stridenex_app.api_stridenex_app.app_utils import (
    gen_response,
    exception_handel
)

class InternshipApplication(Document):

    def before_insert(self):
        self.set_applied_on()
        self.validate_duplicate()
        self.calculate_match_score()

    def set_applied_on(self):
        if not self.applied_on:
            self.applied_on = now()

    def validate_duplicate(self):
        exists = frappe.db.exists(
            "Internship Application",
            {
                "student": self.student,
                "internship": self.internship
            }
        )

        if exists:
            frappe.throw("You have already applied for this internship")

    def calculate_match_score(self):
        required_skills = frappe.get_all(
            "Internship Required Skill",
            filters={"parent": self.internship},
            pluck="skill"
        )

        student_skills = frappe.get_all(
            "Student Skill Table",
            filters={"parent": self.student},
            pluck="skill"
        )

        if not required_skills:
            self.match_score = 100
            return

        matched = list(set(required_skills) & set(student_skills))

        score = (len(matched) / len(required_skills)) * 100
        self.match_score = round(score)
        
@frappe.whitelist()
def get_match_score(student, internship):

    required_skills = frappe.get_all(
        "Internship Required Skill",
        filters={"parent": internship},
        pluck="skill"
    )

    student_skills = frappe.get_all(
        "Student Skill Table",
        filters={"parent": student},
        pluck="skill"
    )

    if not required_skills:
        return 100

    matched = list(set(required_skills) & set(student_skills))

    score = (len(matched) / len(required_skills)) * 100

    return round(score)

@frappe.whitelist(allow_guest=False)
def get_student_application_list(industry=None):
    try:
        session_user = frappe.session.user

        # if not frappe.has_permission(
        #     "Internship Application",
        #     ptype="read",
        #     user=session_user
        # ):
        #     frappe.throw(
        #         "You do not have permission to access Internship Applications.",
        #         frappe.PermissionError
        #     )

        filters = {}

        if industry:
            filters["industry"] = industry

        internship = frappe.get_list(
            "Internship Application",
            filters=filters,
            fields=["*"],
            order_by="creation desc"
        )

        return gen_response(
            status=200,
            message="Internship Applications list fetched successfully",
            data=internship
        )

    except Exception as e:
        return exception_handel(e)
    

@frappe.whitelist(allow_guest=False)
def get_application_status_count(industry=None):
    try:
        session_user = frappe.session.user

        if not frappe.has_permission(
            "Internship Application",
            ptype="read",
            user=session_user
        ):
            frappe.throw(
                "You do not have permission to access Internship Applications.",
                frappe.PermissionError
            )

        conditions = ""
        values = {}

        if industry:
            conditions = "WHERE industry = %(industry)s"
            values["industry"] = industry

        query = f"""
            SELECT status, COUNT(*) as count
            FROM `tabInternship Application`
            {conditions}
            GROUP BY status
        """

        result = frappe.db.sql(query, values, as_dict=True)

        all_status = [
            "Applied",
            "Shortlisted",
            "Tech Interview",
            "Final",
            "HR",
            "Rejected",
            "Selected"
        ]

        count_map = {
            row["status"]: row["count"]
            for row in result
        }

        final_result = {
            status: count_map.get(status, 0)
            for status in all_status
        }

        return gen_response(
            status=200,
            message="Application status count fetched successfully",
            data=final_result
        )

    except Exception as e:
        return exception_handel(e)
    
    
@frappe.whitelist(allow_guest=False)
def create_student_application():
    try:
        session_user = frappe.session.user

        if not frappe.has_permission(
            "Internship Application",
            ptype="create",
            user=session_user
        ):
            frappe.throw(
                "You do not have permission to create Internship Application.",
                frappe.PermissionError
            )

        data = frappe.request.get_json()
        student = data.get("student")

        application_count = frappe.db.count(
            "Internship Application",
            {"student": student}
        )

        if application_count >= 5:
            return gen_response(
                status=417,
                message="You have already applied for 5 internships. Cannot apply for more.",
                data=None
            )

        doc = frappe.get_doc({
            "doctype": "Internship Application",
            "student": data.get("student"),
            "internship": data.get("internship"),
            "status": data.get("status") or "Applied",
            "applied_on": data.get("applied_on"),
            "resume": data.get("resume"),
            "match_score": data.get("match_score") or 0.0,
            "notes": data.get("notes"),
            "industry": data.get("industry"),
        })

        doc.insert()

        frappe.db.commit()

        return gen_response(
            status=200,
            message="Internship Application created successfully",
            data=doc
        )

    except Exception as e:
        return exception_handel(e)


@frappe.whitelist(allow_guest=False)
def update_application_status(name, status):
    try:
        session_user = frappe.session.user

        if not frappe.has_permission(
            "Internship Application",
            ptype="write",
            user=session_user
        ):
            frappe.throw(
                "You do not have permission to update Internship Application.",
                frappe.PermissionError
            )

        if not name:
            return {
                "status": 400,
                "message": "Application name is required"
            }

        if not status:
            return {
                "status": 400,
                "message": "Status is required"
            }

        if not frappe.db.exists(
            "Internship Application",
            name
        ):
            return gen_response(
                status=404,
                message="Internship Application not found",
                data={"success": False}
            )

        doc = frappe.get_doc(
            "Internship Application",
            name
        )

        doc.status = status

        doc.save()

        frappe.db.commit()

        return gen_response(
            status=200,
            message="Application status updated successfully",
            data={
                "name": doc.name,
                "status": doc.status
            }
        )

    except Exception as e:
        frappe.log_error(
            frappe.get_traceback(),
            "update_application_status"
        )
        return exception_handel(e)