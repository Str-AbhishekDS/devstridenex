# Copyright (c) 2026, Your App
# License: MIT

import frappe
import requests
from frappe.model.document import Document
from stridenex_app.stridenex_app.doctype.mentor_session_booking.mentor_session_booking import create_notification

# create_notification(
#     user=student_doc.email_id,
#     subject="Industry Invitation",
#     message="...",
#     document_type="Recruitment Outreach Template",
#     # document_name=template.name
# )


class RecruitmentOutreachTemplate(Document):
    def validate(self):
        if self.template_type == "Professional Email" and not self.subject:
            frappe.throw("Subject is required for Professional Email templates")

        if not self.industry:
            frappe.throw("Industry is required")

    def before_save(self):
        self.verification_status = self.run_quality_check()

        if self.verification_status == "Verified":
            self.verified_by = frappe.session.user

    def run_quality_check(self):
        """Automated verification against Stridenex quality guidelines."""

        banned_phrases = [
            "guaranteed",
            "act now",
            "100% free",
            "click here now",
            "risk free",
        ]

        content = (self.body or "").lower()

        if any(phrase in content for phrase in banned_phrases):
            return "Rejected"

        if len(content.strip()) < 20:
            return "Rejected"

        return "Verified"


@frappe.whitelist()
def generate_email_template(industry, student=None):
    """Generate Professional Email Template"""

    frappe.has_permission(
        "Recruitment Outreach Template",
        "create",
        throw=True
    )

    industry_doc = frappe.get_doc("Industry list", industry)

    student_name = None
    if student:
        student_name = frappe.db.get_value(
            "Student",
            student,
            "Email_id"
        )

    subject, body = _build_professional_email(
        industry_doc,
        student_name
    )

    doc = frappe.get_doc({
        "doctype": "Recruitment Outreach Template",
        "industry": industry,
        "student": student,
        "template_type": "Professional Email",
        "subject": subject,
        "body": body,
        "is_ai_generated": 0,
    })

    doc.insert()

    return doc.as_dict()


@frappe.whitelist()
def get_invitation_template(
    industry,
    student=None,
    platform="Stridenex"
):
    """Generate Student Invitation Template"""

    frappe.has_permission(
        "Recruitment Outreach Template",
        "create",
        throw=True
    )

    industry_doc = frappe.get_doc("Industry list", industry)

    student_name = None
    if student:
        student_name = frappe.db.get_value(
            "Student",
            student,
            "Email_id"
        )

    body = _build_invitation(
        industry_doc,
        student_name,
        platform
    )

    doc = frappe.get_doc({
        "doctype": "Recruitment Outreach Template",
        "industry": industry,
        "student": student,
        "template_type": "Student Invitation",
        "platform": platform,
        "body": body,
        "is_ai_generated": 1,
    })

    doc.insert()

    return doc.as_dict()


# ---------------------------------------------------------------------
# Generation Helpers
# ---------------------------------------------------------------------

def _build_professional_email(industry_doc, student_name=None):

    greeting = (
        f"Dear {student_name},"
        if student_name
        else "Dear Student,"
    )

    industry_name = industry_doc.company_name

    subject = f"Opportunity: Internship with {industry_name}"

    body = f"""{greeting}

We've been impressed by your profile. Your skills and achievements align perfectly with our current initiatives.

We would love to discuss a potential partnership or internship opportunity with you.

Best regards,
Recruitment Team
{industry_name}
"""

    return subject, body


def _build_invitation(
    industry_doc,
    student_name=None,
    platform="Stridenex"
):

    greeting = (
        f"Hi {student_name},"
        if student_name
        else "Hi!"
    )

    industry_name = industry_doc.company_name

    return (
        f"{greeting} "
        f"{industry_name} would love to connect with you "
        f"on {platform}. Quick chat?"
    )



DOCTYPE = "Recruitment Outreach Template"


@frappe.whitelist()
def create_manual_template(
    industry,
    template_type,
    body,
    subject=None,
    student=None
):
    """Lets a user save a hand-written / edited template."""

    frappe.has_permission(
        DOCTYPE,
        ptype="create",
        throw=True
    )

    # Validate Industry exists
    frappe.get_doc("Industry list", industry)

    if template_type == "Professional Email" and not subject:
        frappe.throw(
            "Subject is required for Professional Email templates"
        )

    doc = frappe.get_doc({
        "doctype": DOCTYPE,
        "industry": industry,
        "student": student,
        "template_type": template_type,
        "subject": subject,
        "body": body,
        "is_ai_generated": 0,
    })

    doc.insert()

    return doc.as_dict()






@frappe.whitelist()
def list_templates(
    industry=None,
    template_type=None,
    verification_status=None,
    limit_start=0,
    limit_page_length=20
):
    """List templates with optional filters."""

    filters = {}

    if industry:
        filters["industry"] = industry

    if template_type:
        filters["template_type"] = template_type

    if verification_status:
        filters["verification_status"] = verification_status

    return frappe.get_list(
        DOCTYPE,
        filters=filters,
        fields=[
            "name",
            "industry",
            "template_type",
            "subject",
            "body",
            "verification_status",
            "is_ai_generated",
            "platform",
            "creation",
            "modified",
        ],
        order_by="creation desc",
        limit_start=int(limit_start),
        limit_page_length=int(limit_page_length),
    )
    
    
    
@frappe.whitelist()
def send_industry_invitation(student, industry):
    """
    Send the latest Recruitment Outreach Template for the given
    Industry to the specified Student.
    """

    frappe.has_permission(
        "Recruitment Outreach Template",
        ptype="read",
        throw=True
    )

    # Get student email
    student_doc = frappe.get_doc("Student", student)

    if not student_doc.email_id:
        frappe.throw(
            f"Student {student} does not have an email address."
        )

    # Get latest template for this industry
    template = frappe.get_all(
        "Recruitment Outreach Template",
        filters={
            "industry": industry,
            "verification_status": "Verified"
        },
        fields=[
            "name",
            "subject",
            "body",
            "industry"
        ],
        order_by="creation desc",
        limit=1
    )

    if not template:
        frappe.throw(
            f"No verified template found for Industry: {industry}"
        )

    template = template[0]

    # Get industry company name
    company_name = frappe.db.get_value(
        "Industry list",
        industry,
        "company_name"
    )

    subject = (
        template.subject
        or f"Invitation from {company_name}"
    )

    try:
        frappe.sendmail(
            recipients=[student_doc.email_id],
            subject=subject,
            message=template.body,
            reference_doctype="Recruitment Outreach Template",
            reference_name=template.name,
        )
        
        

        # Update template record
        doc = frappe.get_doc(
            "Recruitment Outreach Template",
            template.name
        )

        doc.sent_status = "Sent"
        doc.sent_on = frappe.utils.now_datetime()
        doc.recipient_email = student_doc.email_id
        doc.send_error = None

        doc.save(ignore_permissions=True)
        
        create_notification(
            user=student_doc.email_id,
            subject="Industry Invitation",
            message=f"""
                You have received an invitation from {company_name}.

                Please check your email for complete details.
            """,
            document_type="Recruitment Outreach Template",
            document_name=template.name
        )

        if frappe.db.exists("User", student_doc.email_id):

            notification = frappe.get_doc({
                "doctype": "Notification Log",
                "subject": "Industry Invitation",
                "for_user": student_doc.email_id,
                "type": "Alert",
                "document_type": "Recruitment Outreach Template",
                "document_name": template.name,
                "email_content": f"""
                    You have received an invitation from {company_name}.

                    Please check your email for complete details.
                """
            })

            notification.insert(ignore_permissions=True)

            frappe.publish_realtime(
                event="msgprint",
                message={
                    "title": "Industry Invitation",
                    "message": f"You have received an invitation from {company_name}",
                    "indicator": "green"
                },
                user=student_doc.email_id
            )

        frappe.db.commit()
        

        return {
            "status": "success",
            "message": "Invitation sent successfully",
            "student": student,
            "industry": industry,
            # "recipient_email": student_doc.email_id,
            "template": template.name
        }

    except Exception as e:

        doc = frappe.get_doc(
            "Recruitment Outreach Template",
            template.name
        )

        doc.sent_status = "Failed"
        doc.send_error = str(e)
        doc.save(ignore_permissions=True)

        frappe.log_error(
            title="Industry Invitation Send Failed",
            message=frappe.get_traceback()
        )

        frappe.throw(
            f"Failed to send invitation: {str(e)}"
        )