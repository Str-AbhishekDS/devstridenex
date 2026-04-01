# Copyright (c) 2026, QTPL and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import now

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