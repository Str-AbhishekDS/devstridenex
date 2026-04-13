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

@frappe.whitelist(allow_guest=True)
def get_student_application_list(industry=None):
    try:
        filters = {}

        # Apply filter only if industry is provided
        if industry:
            filters["industry"] = industry

        internship = frappe.get_all(
            "Internship Application",
            filters=filters,
            fields=["*"
            ],
            order_by="creation desc"
        )

        return gen_response(
            status=200,
            message="Internship Applications list fetched successfully",
            data=internship
        )

    except Exception as e:
        return exception_handel(e)
    
    
@frappe.whitelist(allow_guest=True)
def get_application_status_count(industry=None):
    try:

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

        count_map = {}
        for row in result:
            count_map[row["status"]] = row["count"]

        final_result = {status: count_map.get(status, 0) for status in all_status}

        return gen_response(
            status=200,
            message="Application status count fetched successfully",
            data=final_result
        )

    except Exception as e:
        return exception_handel(e)