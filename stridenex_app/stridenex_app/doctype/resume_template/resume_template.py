# Copyright (c) 2026, QTPL and contributors
# For license information, please see license.txt

# import frappe
from frappe.model.document import Document
import frappe
from frappe.utils.pdf import get_pdf


class ResumeTemplate(Document):
	pass


@frappe.whitelist(allow_guest=True)
def generate_resume(student, template):
    student_doc = frappe.get_doc("Student", student)
    template_doc = frappe.get_doc("Resume Template", template)

    if not template_doc.is_active:
        frappe.throw("Selected resume template is inactive")

   
    html = frappe.render_template(
        template_doc.html_template,
        {"student": student_doc}
    )

    if template_doc.css_style:
        html = f"<style>{template_doc.css_style}</style>{html}"

    pdf_content = get_pdf(html)

    file_doc = frappe.get_doc({
        "doctype": "File",
        "file_name": f"{student_doc.first_name}_{student_doc.last_name}_resume.pdf",
        "attached_to_doctype": "Student",
        "attached_to_name": student_doc.name,
        "content": pdf_content,
        "is_private": 1
    })
    file_doc.save(ignore_permissions=True)

    return {
        "file_url": file_doc.file_url,
        "file_name": file_doc.file_name
    }


@frappe.whitelist(allow_guest=True)
def get_resume_template_previews(student=None):
    """
    Returns rendered HTML preview for every active Resume Template.
    If `student` is passed, renders using that student's real data.
    If not, renders using placeholder/dummy data.
    """
    templates = frappe.get_all(
        "Resume Template",
        filters={"is_active": 1},
        fields=["name", "template_name", "description"]
    )

    if student:
        context_doc = frappe.get_doc("Student", student)
    else:
        context_doc = _get_dummy_student()

    previews = []
    for t in templates:
        template_doc = frappe.get_doc("Resume Template", t.name)
        html = frappe.render_template(template_doc.html_template, {"student": context_doc})
        if template_doc.css_style:
            html = f"<style>{template_doc.css_style}</style>{html}"

        previews.append({
            "name": t.name,
            "template_name": t.template_name,
            "description": t.description,
            "preview_html": html
        })

    return previews


def _get_dummy_student():
    # Lightweight stand-in object so templates render without a real record
    return frappe._dict({
        "first_name": "Jordan",
        "last_name": "Sample",
        "email_id": "jordan.sample@email.com",
        "mobile_no": "+91 90000 00000",
        "linkedin": "linkedin.com/in/jordansample",
        "github": "github.com/jordansample",
        "college": "Sample Institute of Technology",
        "course": "B.Tech Computer Science",
        "department": "CSE",
        "academic_year": "Third Year",
        "semester": "6",
        "cgpa": 8,
        "education": [],
        "internship": [],
        "certificates": [],
        "skill": [],
        "career_interest": []
    })



@frappe.whitelist(allow_guest=True)
def preview_resume_template(template, student=None):
    """
    Always returns FULLY RENDERED html — never the raw {{ }} / {% %} source.
    """
    template_doc = frappe.get_doc("Resume Template", template)

    context_doc = frappe.get_doc("Student", student) if student else _get_dummy_student()

    # This line is the one that actually evaluates {{ }} and {% %} —
    # if this is skipped or bypassed anywhere in the call chain, you get
    # exactly what's in your screenshot.
    rendered_html = frappe.render_template(
        template_doc.html_template,
        {"student": context_doc}
    )

    if template_doc.css_style:
        rendered_html = f"<style>{template_doc.css_style}</style>{rendered_html}"

    return {"html": rendered_html}


def _get_dummy_student():
    return frappe._dict({
        "first_name": "Jordan", "last_name": "Sample",
        "email_id": "jordan.sample@email.com", "mobile_no": "+91 90000 00000",
        "linkedin": "linkedin.com/in/jordansample", "github": "github.com/jordansample",
        "college": "Sample Institute of Technology", "course": "B.Tech Computer Science",
        "department": "CSE", "academic_year": "Third Year", "semester": "6", "cgpa": 8,
        "education": [frappe._dict({
            "education_level": "B.Tech", "institution_name": "Sample Institute",
            "board_university": "Sample University", "specialization": "Computer Science",
            "passing_year": "2026", "percentage_cgpa": "8.0", "grade": "A"
        })],
        "internship": [], "certificates": [], "skill": [], "career_interest": []
    })