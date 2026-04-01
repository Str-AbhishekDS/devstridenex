import frappe
from frappe.model.document import Document
from frappe.utils import today

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