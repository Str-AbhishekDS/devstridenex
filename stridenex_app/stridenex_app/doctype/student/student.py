# Copyright (c) 2026, QTPL and contributors
# For license information, please see license.txt


import frappe
from frappe.model.document import Document

class Student(Document):
    def validate(self):
    
        self.validate_resume()
        self.validate_social_links()
        # existing_student = frappe.db.exists(
        #     "Student",
        #     {
        #         "email_id": self.email_id,
        #         "name": ["!=", self.name]
        #     }
        # )

        # if existing_student:
        #     frappe.throw(f"Student already exists with email {self.email_id}")

    def validate_resume(self):
        if self.resume:
            file_doc = frappe.get_doc("File", {"file_url": self.resume})
            
            if not file_doc.file_name.lower().endswith(".pdf"):
                frappe.throw("Only PDF files are allowed for Resume upload.")


    def validate_social_links(self):
        if self.linkedin and "linkedin.com" not in self.linkedin.lower():
            frappe.throw("Please enter a valid LinkedIn URL.")

        if self.github and "github.com" not in self.github.lower():
            frappe.throw("Please enter a valid GitHub URL.")