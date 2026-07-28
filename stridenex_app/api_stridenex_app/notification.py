# File: stridenex_app/api/admin_notification.py

from email.utils import formatdate

import frappe
from frappe import _
from frappe.utils import now_datetime

# @frappe.whitelist(allow_guest=True)
# def get_notifications(module=None):
#     """
#     GET /api/method/stridenex_app.api.admin_notification.get_notifications
#     Query Params:
#         - module (optional): Student | College | Industry | Mentor
    
#     Returns notifications where:
#         - schedule_a_notification <= current datetime (i.e., time to show)
#         - Optionally filtered by select_module
#         - Only submitted (docstatus=1) documents
#     """

#     filters = {
#         "schedule_a_notification": ("<=", now_datetime()),
#     }

#     if module:
#         valid_modules = ["Student", "College", "Industry", "Mentor"]
#         if module not in valid_modules:
#             frappe.throw(_("Invalid module. Must be one of: {0}").format(", ".join(valid_modules)))
#         filters["select_module"] = module

#     notifications = frappe.get_all(
#         "Admin Notification",
#         filters=filters,
#         fields=[
#             "name",
#             "title",
#             "select_module",
#             "schedule_a_notification",
#             "message",
#             "status",
#             "creation",
#         ],
#         order_by="schedule_a_notification desc",
#     )

#     return {
#         "status": "success",
#         "count": len(notifications),
#         "data": notifications,
#     }

# @frappe.whitelist(allow_guest=False)
# def mark_as_seen(notification_name):
#     """
#     POST /api/method/stridenex_app.api.admin_notification.mark_as_seen
#     Body:
#         - notification_name: name/ID of the Admin Notification doc (e.g., "Admin Notification-00001")
    
#     Transitions status from 'Unseen' to 'Seen'.
#     Note: Since the doctype is submittable, we use db_set to bypass submit lock.
#     """

#     if not notification_name:
#         frappe.throw(_("notification_name is required"))

#     # Check if document exists
#     if not frappe.db.exists("Admin Notification", notification_name):
#         frappe.throw(_("Notification '{0}' not found").format(notification_name), frappe.DoesNotExistError)

#     doc = frappe.get_doc("Admin Notification", notification_name)

#     if doc.docstatus != 1:
#         frappe.throw(_("Only submitted notifications can be updated"))

#     if doc.status == "Seen":
#         return {
#             "status": "info",
#             "message": "Notification is already marked as Seen",
#             "name": notification_name,
#         }

#     # db_set bypasses the submit lock on docstatus=1 docs
#     doc.db_set("status", "Seen", update_modified=True)
#     frappe.db.commit()

#     return {
#         "status": "success",
#         "message": "Notification marked as Seen",
#         "name": notification_name,
#     }


# @frappe.whitelist(allow_guest=False)
# def mark_all_as_seen(module=None):
#     """
#     POST /api/method/stridenex_app.api.admin_notification.mark_all_as_seen
#     Body:
#         - module (optional): Mark all unseen for a specific module
#     """

#     filters = {
#         "docstatus": 1,
#         "status": "Unseen",
#         "schedule_a_notification": ("<=", now_datetime()),
#     }

#     if module:
#         filters["select_module"] = module

#     unseen_docs = frappe.get_all("Admin Notification", filters=filters, pluck="name")

#     if not unseen_docs:
#         return {"status": "info", "message": "No unseen notifications found", "updated": 0}

#     frappe.db.set_value(
#         "Admin Notification",
#         {"name": ("in", unseen_docs)},
#         "status",
#         "Seen",
#     )
#     frappe.db.commit()

#     return {
#         "status": "success",
#         "message": f"{len(unseen_docs)} notification(s) marked as Seen",
#         "updated": len(unseen_docs),
#         "names": unseen_docs,
#     }
    


@frappe.whitelist(allow_guest=True)
def get_notifications(owner_email, limit=20):

    # Resolve actual user
    user = frappe.db.get_value(
        "User",
        {"email": owner_email},
        "name"
    )

    if not user:
        return {
            "status": "error",
            "message": "User not found"
        }

    notifications = frappe.get_all(
        "Notification Log",
        filters={
            "for_user": user
        },
        fields=[
            "name",
            "subject",
            "type",
            "email_content",
            "document_type",
            "document_name",
            "from_user",
            "creation",
            "read"
        ],
        order_by="creation desc",
        limit_page_length=int(limit)
    )

    unread_count = frappe.db.count(
        "Notification Log",
        filters={
            "for_user": user,
            "read": 0
        }
    )

    return {
        "status": "success",
        "user": user,
        "unread_count": unread_count,
        "count": len(notifications),
        "data": notifications
    }
    
    

@frappe.whitelist(allow_guest=True)
def mark_as_seen(notification_name, owner_email):
    """
    Mark single Notification Log record as Seen/Read

    API:
    /api/method/stridenex_app.api.notification.mark_as_seen

    Params:
        notification_name (required)
        owner_email (required)

    Method:
        POST
    """

    # -----------------------------
    # Validate Inputs
    # -----------------------------
    if not notification_name:
        return {
            "status": "error",
            "message": "notification_name is required"
        }

    if not owner_email:
        return {
            "status": "error",
            "message": "owner_email is required"
        }

    # -----------------------------
    # Resolve User
    # -----------------------------
    user = frappe.db.get_value(
        "User",
        {"email": owner_email},
        "name"
    )

    if not user:
        return {
            "status": "error",
            "message": "User not found"
        }

    # -----------------------------
    # Check Notification Exists
    # -----------------------------
    if not frappe.db.exists("Notification Log", notification_name):
        return {
            "status": "error",
            "message": f"Notification '{notification_name}' not found"
        }

    # -----------------------------
    # Get Notification
    # -----------------------------
    doc = frappe.get_doc("Notification Log", notification_name)

    # -----------------------------
    # Validate Ownership
    # -----------------------------
    if doc.for_user != user:
        return {
            "status": "error",
            "message": "You are not authorized to update this notification"
        }

    # -----------------------------
    # Already Read
    # -----------------------------
    if doc.read:
        return {
            "status": "info",
            "message": "Notification already marked as seen",
            "name": notification_name
        }

    # -----------------------------
    # Mark as Read
    # -----------------------------
    doc.db_set("read", 1, update_modified=True)

    frappe.db.commit()

    return {
        "status": "success",
        "message": "Notification marked as seen",
        "name": notification_name
    }
    
@frappe.whitelist(allow_guest=True)
def mark_all_as_seen(owner_email):
    """
    Mark all Notification Log records as Seen/Read

    API:
    /api/method/stridenex_app.api.notification.mark_all_as_seen

    Params:
        owner_email (required)

    Method:
        POST
    """

    # -----------------------------
    # Validate Input
    # -----------------------------
    if not owner_email:
        return {
            "status": "error",
            "message": "owner_email is required"
        }

    # -----------------------------
    # Resolve User
    # -----------------------------
    user = frappe.db.get_value(
        "User",
        {"email": owner_email},
        "name"
    )

    if not user:
        return {
            "status": "error",
            "message": "User not found"
        }

    # -----------------------------
    # Get Unread Notifications
    # -----------------------------
    unread_notifications = frappe.get_all(
        "Notification Log",
        filters={
            "for_user": user,
            "read": 0
        },
        pluck="name"
    )

    # -----------------------------
    # No Unread Notifications
    # -----------------------------
    if not unread_notifications:
        return {
            "status": "info",
            "message": "No unread notifications found",
            "updated": 0
        }

    # -----------------------------
    # Mark All as Read
    # -----------------------------
    frappe.db.sql("""
        UPDATE `tabNotification Log`
        SET `read` = 1
        WHERE name IN %(names)s
    """, {
        "names": tuple(unread_notifications)
    })

    frappe.db.commit()

    # -----------------------------
    # Success Response
    # -----------------------------
    return {
        "status": "success",
        "message": f"{len(unread_notifications)} notification(s) marked as seen",
        "updated": len(unread_notifications),
        "notifications": unread_notifications
    }
    
    
    
import frappe
from frappe.utils import today


def update_last_activity(login_manager):
    """
    Update last activity date whenever a user logs in.
    """

    user = frappe.session.user

    if not user or user == "Guest":
        return

    frappe.db.set_value(
        "Student",
        user,
        "last_activity_date",
        today(),
        update_modified=False
    )

    frappe.db.commit()
    
    
    
import frappe
from frappe.utils import get_url

# Config per status: accent color, label color, subject line, and body message
PROJECT_STATUS_CONFIG = {
    "Shortlisted": {
        "accent": "#0f0fbd",
        "badge_color": "#0f0fbd",
        "badge_bg": "#eef2ff",
        "subject": "You've Been Shortlisted!",
        "heading": "You're Shortlisted 🎉",
        "message": "Great news! You have been shortlisted for the project. Please keep an eye on your dashboard for the next steps.",
        "note": "Stay tuned — the next update could be an interview invite.",
    },
    "Interview Scheduled": {
        "accent": "#7c3aed",
        "badge_color": "#7c3aed",
        "badge_bg": "#f3e8ff",
        "subject": "Your Interview Has Been Scheduled",
        "heading": "Interview Scheduled 📅",
        "message": "Your interview for the project has been scheduled. Please check your dashboard for the date, time, and further details.",
        "note": "Make sure to prepare well and join on time.",
    },
    "Rejected": {
        "accent": "#dc2626",
        "badge_color": "#dc2626",
        "badge_bg": "#fee2e2",
        "subject": "Update on Your Project Application",
        "heading": "Application Update",
        "message": "Thank you for applying. After careful review, we regret to inform you that your application was not selected for this project this time.",
        "note": "Don't be discouraged — new opportunities are added regularly. Keep applying!",
    },
    "Selected": {
        "accent": "#10b981",
        "badge_color": "#10b981",
        "badge_bg": "#d1fae5",
        "subject": "Congratulations! You've Been Selected",
        "heading": "You're Selected ✅",
        "message": "Congratulations! You have been selected for the project. Please check your dashboard for onboarding details and next steps.",
        "note": "Welcome aboard — we're excited to have you on this project.",
    },
    "Completed": {
        "accent": "#0891b2",
        "badge_color": "#0891b2",
        "badge_bg": "#cffafe",
        "subject": "Project Marked as Completed",
        "heading": "Project Completed 🏁",
        "message": "Your project has been marked as completed. Great work! Your performance and output are being reviewed by the team.",
        "note": "Check your dashboard for feedback and any certificates or awards.",
    },
    "Awarded": {
        "accent": "#ff6b00",
        "badge_color": "#ff6b00",
        "badge_bg": "#ffedd5",
        "subject": "You've Been Awarded!",
        "heading": "Congratulations, You're Awarded 🏆",
        "message": "Outstanding work! You have been awarded for your performance on this project. This achievement has been added to your profile.",
        "note": "Check your dashboard to view your award details.",
    },
}


def project_status_change(doc, method=None):
    """Triggered on Student Project Enrollment save. Sends email + notification
    only when status has actually changed to one of the tracked stages."""

    if not doc.has_value_changed("status"):
        return

    status = doc.status
    config = PROJECT_STATUS_CONFIG.get(status)

    if not config:
        return  # not one of our 6 tracked stages

    student_user = get_student_user(doc)
    if not student_user:
        return

    full_name = frappe.db.get_value("User", student_user, "full_name") or student_user

    send_status_mail(student_user, full_name, status, config, doc)
    send_status_notification(student_user, status, config, doc)


def get_student_user(doc):
    """Adjust this based on your actual field name linking to the student's user account.
    Assuming Student Project Enrollment has a 'student' field (Link -> Student)
    and Student doctype has a 'user' or 'user_id' field linking to User."""

    if hasattr(doc, "student_email") and doc.student_email:
        return doc.student_email

    if hasattr(doc, "student") and doc.student:
        # adjust fieldname 'user_id' if your Student doctype uses a different one
        return frappe.db.get_value("Student", doc.student, "email_id") or frappe.db.get_value(
            "Student", doc.student, "user"
        )

    return None


def send_status_notification(student_user, status, config, doc):
    """Creates an in-app Notification Log entry (bell icon notification)."""

    
    frappe.get_doc({
        "doctype": "Notification Log",
        "subject": config["subject"],
        "email_content": config["message"],
        "for_user": student_user,
        "type": "Alert",
        "document_type": doc.doctype,
        "document_name": doc.name,
    }).insert(ignore_permissions=True)


def send_status_mail(student_user, full_name, status, config, doc):
    project_name = getattr(doc, "project_name", None) or getattr(doc, "project", None) or "your project"
    
    message = f"""
<div style="margin:0;padding:0;background:#f6f6f8;font-family:'Inter',-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;">
    <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background:#f6f6f8;padding:30px 15px;">
        <tr>
            <td align="center">

                <table role="presentation" width="100%" cellspacing="0" cellpadding="0"
                    style="max-width:600px;background:#ffffff;border:1px solid #e2e8f0;border-radius:16px;overflow:hidden;">

                    <!-- Header -->
                    <tr>
                        <td style="background:{config['accent']};padding:30px;text-align:center;">
                            <h1 style="margin:0;color:#ffffff;font-size:24px;font-weight:700;">
                                {config['heading']}
                            </h1>
                            <p style="margin:8px 0 0;color:#dbeafe;font-size:14px;">
                                Update on: {project_name}
                            </p>
                        </td>
                    </tr>

                    <!-- Body -->
                    <tr>
                        <td style="padding:32px;">

                            <p style="margin:0 0 20px;color:#1E293B;font-size:16px;line-height:1.8;">
                                Hi <strong>{full_name}</strong>,
                            </p>

                            <p style="margin:0 0 24px;color:#1E293B;font-size:15px;line-height:1.8;">
                                {config['message']}
                            </p>

                            <!-- Status Badge Card -->
                            <div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:12px;padding:20px;margin-bottom:24px;">
                                <table width="100%" style="border-collapse:collapse;">
                                    <tr>
                                        <td style="padding:8px 0;color:#64748B;font-size:14px;">
                                            <strong>Project</strong>
                                        </td>
                                        <td style="padding:8px 0;color:#1E293B;font-size:14px;text-align:right;">
                                            {project_name}
                                        </td>
                                    </tr>
                                    <tr>
                                        <td style="padding:8px 0;color:#64748B;font-size:14px;">
                                            <strong>Current Status</strong>
                                        </td>
                                        <td style="padding:8px 0;text-align:right;">
                                            <span style="background:{config['badge_bg']};color:{config['badge_color']};
                                                padding:4px 12px;border-radius:20px;font-size:13px;font-weight:600;">
                                                {status}
                                            </span>
                                        </td>
                                    </tr>
                                </table>
                            </div>

                            <!-- Note -->
                            <div style="background:#eef2ff;border-left:4px solid {config['accent']};padding:16px 18px;border-radius:8px;">
                                <p style="margin:0;color:#1E293B;font-size:14px;line-height:1.8;">
                                    {config['note']}
                                </p>
                            </div>

                        </td>
                    </tr>

                    <!-- Footer -->
                    <tr>
                        <td style="background:#0F172A;padding:24px;text-align:center;">
                            <p style="margin:0;color:#ffffff;font-size:15px;font-weight:600;">
                                StrideNex Team
                            </p>
                            <p style="margin:10px 0 0;color:#94a3b8;font-size:13px;">
                                Empowering Skills • Building Careers • Creating Opportunities
                            </p>
                            <div style="margin-top:16px;padding-top:16px;border-top:1px solid #334155;">
                                <p style="margin:0;color:#94a3b8;font-size:12px;">
                                    Log in to your dashboard to view full details of this update.
                                </p>
                            </div>
                        </td>
                    </tr>

                </table>

            </td>
        </tr>
    </table>
</div>
"""

    frappe.sendmail(
        recipients=[student_user],
        subject=config["subject"],
        message=message,
        reference_doctype=doc.doctype,
        reference_name=doc.name,
    )
    
    
    
    
    

STATUS_CONFIG = {
    "Shortlisted": {
        "accent": "#0f0fbd",
        "badge_color": "#0f0fbd",
        "badge_bg": "#eef2ff",
        "subject": "You've Been Shortlisted!",
        "heading": "You're Shortlisted 🎉",
        "message": "Great news! You have been shortlisted for this internship. Keep an eye on your dashboard for the next steps.",
        "note": "Stay tuned — the next update could be an interview invite.",
    },
    "Tech Interview": {
        "accent": "#7c3aed",
        "badge_color": "#7c3aed",
        "badge_bg": "#f3e8ff",
        "subject": "Technical Interview Scheduled",
        "heading": "Tech Interview Scheduled 💻",
        "message": "Your technical interview round has been scheduled for this internship. Please check your dashboard for the date, time, and details.",
        "note": "Brush up on your technical fundamentals and be ready ahead of time.",
    },
    "HR": {
        "accent": "#9333ea",
        "badge_color": "#9333ea",
        "badge_bg": "#f3e8ff",
        "subject": "HR Round Scheduled",
        "heading": "HR Interview Scheduled 🗣️",
        "message": "You've moved to the HR interview round for this internship. Please check your dashboard for the schedule and details.",
        "note": "This is often the final step before a decision — good luck!",
    },
    "Final": {
        "accent": "#2563eb",
        "badge_color": "#2563eb",
        "badge_bg": "#dbeafe",
        "subject": "Final Round Scheduled",
        "heading": "Final Round Scheduled 🎯",
        "message": "You've reached the final round for this internship. Please check your dashboard for the schedule and details.",
        "note": "You're almost there — this is the last step before a final decision.",
    },
    "Rejected": {
        "accent": "#dc2626",
        "badge_color": "#dc2626",
        "badge_bg": "#fee2e2",
        "subject": "Update on Your Internship Application",
        "heading": "Application Update",
        "message": "Thank you for applying. After careful review, we regret to inform you that your application was not selected for this internship this time.",
        "note": "Don't be discouraged — new opportunities are added regularly. Keep applying!",
    },
    "Selected": {
        "accent": "#10b981",
        "badge_color": "#10b981",
        "badge_bg": "#d1fae5",
        "subject": "Congratulations! You've Been Selected",
        "heading": "You're Selected ✅",
        "message": "Congratulations! You have been selected for this internship. Please check your dashboard for onboarding details and next steps.",
        "note": "Welcome aboard — we're excited to have you get started.",
    },
}


def internship_status_change(doc, method=None):
    """Triggered on Internship Application save. Sends email + notification
    only when status changes to one of the tracked stages (excludes 'Applied')."""

    if not doc.has_value_changed("status"):
        return

    status = doc.status
    config = STATUS_CONFIG.get(status)

    if not config:
        return  # 'Applied' or any untracked status - skip

    student_user = get_internship_student_user(doc.student)
    if not student_user:
        frappe.log_error(
            f"No user linked for Student {doc.student}",
            "Internship Application Notification"
        )
        return

    full_name = frappe.db.get_value("User", student_user, "full_name") or student_user
    internship_title = frappe.db.get_value("Internship", doc.internship, "title") \
        or doc.internship

    send_internship_status_mail(student_user, full_name, status, config, doc, internship_title)
    send_internship_status_notification(student_user, status, config, doc)


def get_internship_student_user(student):
    """Student doctype is assumed to have a field linking to User -
    adjust fieldname below if it's different (e.g. 'user', 'user_id', 'email')."""

    if not student:
        return None

    for fieldname in ("email_id", "user", "email"):
        if frappe.db.has_column("Student", fieldname):
            value = frappe.db.get_value("Student", student, fieldname)
            if value:
                return value

    return None


def send_internship_status_notification(student_user, status, config, doc):
    frappe.get_doc({
        "doctype": "Notification Log",
        "subject": config["subject"],
        "email_content": config["message"],
        "for_user": student_user,
        "type": "Alert",
        "document_type": doc.doctype,
        "document_name": doc.name,
    }).insert(ignore_permissions=True)


def send_internship_status_mail(student_user, full_name, status, config, doc, internship_title):
    message = f"""
<div style="margin:0;padding:0;background:#f6f6f8;font-family:'Inter',-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;">
    <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background:#f6f6f8;padding:30px 15px;">
        <tr>
            <td align="center">

                <table role="presentation" width="100%" cellspacing="0" cellpadding="0"
                    style="max-width:600px;background:#ffffff;border:1px solid #e2e8f0;border-radius:16px;overflow:hidden;">

                    <!-- Header -->
                    <tr>
                        <td style="background:{config['accent']};padding:30px;text-align:center;">
                            <h1 style="margin:0;color:#ffffff;font-size:24px;font-weight:700;">
                                {config['heading']}
                            </h1>
                            <p style="margin:8px 0 0;color:#dbeafe;font-size:14px;">
                                Update on: {internship_title}
                            </p>
                        </td>
                    </tr>

                    <!-- Body -->
                    <tr>
                        <td style="padding:32px;">

                            <p style="margin:0 0 20px;color:#1E293B;font-size:16px;line-height:1.8;">
                                Hi <strong>{full_name}</strong>,
                            </p>

                            <p style="margin:0 0 24px;color:#1E293B;font-size:15px;line-height:1.8;">
                                {config['message']}
                            </p>

                            <!-- Status Badge Card -->
                            <div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:12px;padding:20px;margin-bottom:24px;">
                                <table width="100%" style="border-collapse:collapse;">
                                    <tr>
                                        <td style="padding:8px 0;color:#64748B;font-size:14px;">
                                            <strong>Internship</strong>
                                        </td>
                                        <td style="padding:8px 0;color:#1E293B;font-size:14px;text-align:right;">
                                            {internship_title}
                                        </td>
                                    </tr>
                                    <tr>
                                        <td style="padding:8px 0;color:#64748B;font-size:14px;">
                                            <strong>Current Status</strong>
                                        </td>
                                        <td style="padding:8px 0;text-align:right;">
                                            <span style="background:{config['badge_bg']};color:{config['badge_color']};
                                                padding:4px 12px;border-radius:20px;font-size:13px;font-weight:600;">
                                                {status}
                                            </span>
                                        </td>
                                    </tr>
                                </table>
                            </div>

                            <!-- Note -->
                            <div style="background:#eef2ff;border-left:4px solid {config['accent']};padding:16px 18px;border-radius:8px;">
                                <p style="margin:0;color:#1E293B;font-size:14px;line-height:1.8;">
                                    {config['note']}
                                </p>
                            </div>

                        </td>
                    </tr>

                    <!-- Footer -->
                    <tr>
                        <td style="background:#0F172A;padding:24px;text-align:center;">
                            <p style="margin:0;color:#ffffff;font-size:15px;font-weight:600;">
                                StrideNex Team
                            </p>
                            <p style="margin:10px 0 0;color:#94a3b8;font-size:13px;">
                                Empowering Skills • Building Careers • Creating Opportunities
                            </p>
                            <div style="margin-top:16px;padding-top:16px;border-top:1px solid #334155;">
                                <p style="margin:0;color:#94a3b8;font-size:12px;">
                                    Log in to your dashboard to view full details of this update.
                                </p>
                            </div>
                        </td>
                    </tr>

                </table>

            </td>
        </tr>
    </table>
</div>
"""

    frappe.sendmail(
        recipients=[student_user],
        subject=config["subject"],
        message=message,
        reference_doctype=doc.doctype,
        reference_name=doc.name,
    )
    
    
    
    
# -----------------------------------------------------------------------------
# hooks.py
# -----------------------------------------------------------------------------
# doc_events = {
#     "User": {
#         "on_update": [
#             "your_app.your_module.onboarding_email.send_onboarding_email",
#             "your_app.your_module.onboarding_email.send_mentor_onboarding_email",
#             "your_app.your_module.onboarding_email.send_college_onboarding_email",
#             "your_app.your_module.onboarding_email.send_industry_onboarding_email",
#         ]
#     }
# }
# -----------------------------------------------------------------------------
# Place this file at: your_app/your_module/onboarding_email.py
# Student, Mentor, College, and Industry logic all live here, with NO shared
# function/variable names, so none of them can silently overwrite another.
# -----------------------------------------------------------------------------

import frappe

STUDENT_ROLE = "Student Base"
MENTOR_ROLE = "Mentor"  # <-- CONFIRM this exact name on your site
COLLEGE_ROLE = "College Base"
INDUSTRY_ROLE = "Industry Base"


# ============================== STUDENT FLOW ================================

def _has_student_role(doc):
    role_list = doc.get("roles") or []
    return any(getattr(r, "role", None) == STUDENT_ROLE for r in role_list)


def send_onboarding_email(doc, method=None):
    """
    Fires once, only at the exact moment is_onboarded transitions INTO 2
    for a user who has the "Student Base" role.
    """
    if not _has_student_role(doc):
        return

    if doc.get("is_onboarded") != 2:
        return

    # if doc.get("onboarding_email_sent"):
    #     return

    doc_before = doc.get_doc_before_save()
    if doc_before is not None:
        if doc_before.get("is_onboarded") == 2:
            return

    _send_student_email(doc)

    # frappe.db.set_value("User", doc.name, "onboarding_email_sent", 1, update_modified=False)


def _send_student_email(doc):
    student_name = doc.get("full_name") or doc.get("first_name") or doc.name
    subject = "🎉 You're All Set! Your Onboarding is Complete"
    message = frappe.render_template(STUDENT_EMAIL_TEMPLATE, {"student_name": student_name})
    frappe.sendmail(recipients=[doc.email], subject=subject, message=message, now=True)


STUDENT_EMAIL_TEMPLATE = """
<div style="margin:0;padding:0;background:#f6f6f8;font-family:'Inter',-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;">
  <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background:#f6f6f8;padding:30px 15px;">
    <tr>
      <td align="center">

        <table role="presentation" width="100%" cellspacing="0" cellpadding="0"
          style="max-width:650px;background:#ffffff;border:1px solid #e2e8f0;border-radius:16px;overflow:hidden;">

          <!-- Header -->
          <tr>
            <td style="background:#0f0fbd;padding:32px;text-align:center;">
              <h1 style="margin:0;color:#ffffff;font-size:28px;font-weight:700;">
                🎉 Welcome to StrideNex
              </h1>
              <p style="margin:10px 0 0;color:#dbeafe;font-size:15px;">
                Your onboarding is complete and your account is now active
              </p>
            </td>
          </tr>

          <!-- Body -->
          <tr>
            <td style="padding:32px;">

              <p style="margin:0 0 20px;color:#1E293B;font-size:16px;line-height:1.8;">
                Hi <strong>{{ student_name }}</strong>,
              </p>

              <div style="background:#f0fdf4;border-left:4px solid #10b981;padding:18px;border-radius:8px;margin-bottom:24px;">
                <p style="margin:0;color:#065f46;font-size:15px;line-height:1.8;">
                  🎉 Congratulations! Your onboarding is now <strong>complete</strong> and your account has been successfully verified.
                </p>
              </div>

              <!-- Plan Activation -->
              <div style="background:#eef2ff;border-left:4px solid #0f0fbd;padding:18px;border-radius:8px;margin-bottom:24px;">
                <h3 style="margin:0 0 10px;color:#0f0fbd;font-size:16px;">
                  Student Base Pack Activated
                </h3>

                <p style="margin:0;color:#1E293B;font-size:14px;line-height:1.8;">
                  Your <strong>Student Base Pack</strong> starts today and will remain active for the next
                  <strong>60 days</strong>.
                </p>

                <p style="margin:10px 0 0;color:#64748B;font-size:14px;line-height:1.8;">
                  During this period, you can access learning resources, AI-powered tools,
                  career guidance, mentoring opportunities, events, and much more.
                </p>
              </div>

              <h3 style="margin:0 0 16px;color:#0f0fbd;font-size:18px;">
                🚀 What You Can Do Now
              </h3>

              <table width="100%" cellspacing="0" cellpadding="0" style="margin-bottom:24px;">
                <tr>
                  <td style="padding:10px 0;color:#1E293B;">
                    ✅ <strong>Add & Verify Skills using AI</strong><br>
                    <span style="color:#64748B;">Validate your skills and strengthen your profile.</span>
                  </td>
                </tr>

                <tr>
                  <td style="padding:10px 0;color:#1E293B;">
                    🎯 <strong>Choose Your Career Path</strong><br>
                    <span style="color:#64748B;">Follow a structured roadmap toward your dream career.</span>
                  </td>
                </tr>

                <tr>
                  <td style="padding:10px 0;color:#1E293B;">
                    📚 <strong>Watch Study Shorts</strong><br>
                    <span style="color:#64748B;">Learn quickly through bite-sized educational content.</span>
                  </td>
                </tr>

                <tr>
                  <td style="padding:10px 0;color:#1E293B;">
                    📈 <strong>Track Daily Habits</strong><br>
                    <span style="color:#64748B;">Build consistency with habit tracking and progress monitoring.</span>
                  </td>
                </tr>

                <tr>
                  <td style="padding:10px 0;color:#1E293B;">
                    👨‍🏫 <strong>Connect with Mentors</strong><br>
                    <span style="color:#64748B;">Get guidance from experienced professionals.</span>
                  </td>
                </tr>

                <tr>
                  <td style="padding:10px 0;color:#1E293B;">
                    🎪 <strong>Discover College Events</strong><br>
                    <span style="color:#64748B;">Stay informed about opportunities around your campus.</span>
                  </td>
                </tr>

                <tr>
                  <td style="padding:10px 0;color:#1E293B;">
                    🌟 <strong>Read & Share Success Stories</strong><br>
                    <span style="color:#64748B;">Get inspired by achievements from the StrideNex community.</span>
                  </td>
                </tr>
              </table>

              <div style="background:#fff7ed;border-left:4px solid #ff6b00;padding:18px;border-radius:8px;">
                <p style="margin:0;color:#9a3412;font-size:14px;line-height:1.8;">
                  Start exploring today and make the most of your Student Base Pack benefits.
                  Your journey toward career success begins now.
                </p>
              </div>

            </td>
          </tr>

          <!-- Footer -->
          <tr>
            <td style="background:#0F172A;padding:24px;text-align:center;">
              <p style="margin:0;color:#ffffff;font-size:16px;font-weight:600;">
                Welcome to the StrideNex Community
              </p>

              <p style="margin:10px 0 0;color:#94a3b8;font-size:13px;">
                Empowering Skills • Building Careers • Creating Opportunities
              </p>

              <div style="margin-top:16px;padding-top:16px;border-top:1px solid #334155;">
                <p style="margin:0;color:#94a3b8;font-size:12px;">
                  Best Regards,<br>
                  <span style="color:#ffffff;font-weight:600;">StrideNex Team</span>
                </p>
              </div>
            </td>
          </tr>

        </table>

      </td>
    </tr>
  </table>
</div>
"""


# ============================== MENTOR FLOW ==================================

def _has_mentor_role(doc):
    role_list = doc.get("roles") or []
    return any(getattr(r, "role", None) == MENTOR_ROLE for r in role_list)


def send_mentor_onboarding_email(doc, method=None):
    """
    Fires once, only at the exact moment is_onboarded transitions INTO 3
    for a user who has the "Mentor" role.
    """
    if not _has_mentor_role(doc):
        return

    if doc.get("is_onboarded") != 3:
        return

    # if doc.get("mentor_onboarding_email_sent"):
    #     return

    doc_before = doc.get_doc_before_save()
    if doc_before is not None:
        if doc_before.get("is_onboarded") == 3:
            return

    _send_mentor_email(doc)

    # frappe.db.set_value("User", doc.name, "mentor_onboarding_email_sent", 1, update_modified=False)


def _send_mentor_email(doc):
    mentor_name = doc.get("full_name") or doc.get("first_name") or doc.name
    subject = "🎉 You're All Set! Your Mentor Onboarding is Complete"
    message = frappe.render_template(MENTOR_EMAIL_TEMPLATE, {"mentor_name": mentor_name})
    frappe.sendmail(recipients=[doc.email], subject=subject, message=message, now=True)


MENTOR_EMAIL_TEMPLATE = """
<div style="margin:0;padding:0;background:#f6f6f8;font-family:'Inter',-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;">
  <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background:#f6f6f8;padding:30px 15px;">
    <tr>
      <td align="center">

        <table role="presentation" width="100%" cellspacing="0" cellpadding="0"
          style="max-width:650px;background:#ffffff;border:1px solid #e2e8f0;border-radius:16px;overflow:hidden;">

          <!-- Header -->
          <tr>
            <td style="background:#0f0fbd;padding:32px;text-align:center;">
              <h1 style="margin:0;color:#ffffff;font-size:28px;font-weight:700;">
                🎉 Welcome to StrideNex Mentorship
              </h1>
              <p style="margin:10px 0 0;color:#dbeafe;font-size:15px;">
                Your mentor account is now active and ready to inspire learners
              </p>
            </td>
          </tr>

          <!-- Body -->
          <tr>
            <td style="padding:32px;">

              <p style="margin:0 0 20px;color:#1E293B;font-size:16px;line-height:1.8;">
                Hi <strong>{{ mentor_name }}</strong>,
              </p>

              <div style="background:#f0fdf4;border-left:4px solid #10b981;padding:18px;border-radius:8px;margin-bottom:24px;">
                <p style="margin:0;color:#065f46;font-size:15px;line-height:1.8;">
                  🎉 Congratulations! Your mentor onboarding is now <strong>complete</strong>.
                  You're ready to start guiding students, sharing your expertise,
                  and making a meaningful impact through StrideNex.
                </p>
              </div>

              <!-- Pack Activation -->
              <div style="background:#eef2ff;border-left:4px solid #0f0fbd;padding:18px;border-radius:8px;margin-bottom:24px;">
                <h3 style="margin:0 0 10px;color:#0f0fbd;font-size:16px;">
                  Mentor Base Pack Activated
                </h3>

                <p style="margin:0;color:#1E293B;font-size:14px;line-height:1.8;">
                  Your <strong>Mentor Base Pack</strong> starts today and will remain active for the next
                  <strong>60 days</strong>.
                </p>

                <p style="margin:10px 0 0;color:#64748B;font-size:14px;line-height:1.8;">
                  During this period, you can create mentoring sessions, interact with students,
                  validate skills, manage bookings, and build your mentoring presence on StrideNex.
                </p>
              </div>

              <h3 style="margin:0 0 16px;color:#0f0fbd;font-size:18px;">
                🚀 What You Can Do Now
              </h3>

              <table width="100%" cellspacing="0" cellpadding="0" style="margin-bottom:24px;">

                <tr>
                  <td style="padding:10px 0;color:#1E293B;">
                    🎓 <strong>Add Session Offers</strong><br>
                    <span style="color:#64748B;">
                      Create Group Sessions or 1:1 Mentorship offerings for students to book.
                    </span>
                  </td>
                </tr>

                <tr>
                  <td style="padding:10px 0;color:#1E293B;">
                    ✅ <strong>Verify Student Skills</strong><br>
                    <span style="color:#64748B;">
                      Review and validate skills added by students to strengthen their profiles.
                    </span>
                  </td>
                </tr>

                <tr>
                  <td style="padding:10px 0;color:#1E293B;">
                    📥 <strong>Manage Session Requests</strong><br>
                    <span style="color:#64748B;">
                      Accept, schedule, and conduct mentoring sessions with learners.
                    </span>
                  </td>
                </tr>

                <tr>
                  <td style="padding:10px 0;color:#1E293B;">
                    📅 <strong>Set Your Availability</strong><br>
                    <span style="color:#64748B;">
                      Publish your availability so students can easily book sessions.
                    </span>
                  </td>
                </tr>

                <tr>
                  <td style="padding:10px 0;color:#1E293B;">
                    📊 <strong>Track Session History</strong><br>
                    <span style="color:#64748B;">
                      Review previous mentoring sessions, students guided, and outcomes achieved.
                    </span>
                  </td>
                </tr>

              </table>

              <div style="background:#fff7ed;border-left:4px solid #ff6b00;padding:18px;border-radius:8px;">
                <p style="margin:0;color:#9a3412;font-size:14px;line-height:1.8;">
                  Students are waiting to learn from your experience.
                  Start creating session offers and begin your mentoring journey today.
                </p>
              </div>

            </td>
          </tr>

          <!-- Footer -->
          <tr>
            <td style="background:#0F172A;padding:24px;text-align:center;">
              <p style="margin:0;color:#ffffff;font-size:16px;font-weight:600;">
                Thank You for Joining StrideNex
              </p>

              <p style="margin:10px 0 0;color:#94a3b8;font-size:13px;">
                Empowering Skills • Building Careers • Creating Opportunities
              </p>

              <div style="margin-top:16px;padding-top:16px;border-top:1px solid #334155;">
                <p style="margin:0;color:#94a3b8;font-size:12px;">
                  Best Regards,<br>
                  <span style="color:#ffffff;font-weight:600;">StrideNex Team</span>
                </p>
              </div>
            </td>
          </tr>

        </table>

      </td>
    </tr>
  </table>
</div>
"""

# ============================== COLLEGE FLOW =================================

def _has_college_role(doc):
    role_list = doc.get("roles") or []
    return any(getattr(r, "role", None) == COLLEGE_ROLE for r in role_list)


def send_college_onboarding_email(doc, method=None):
    """
    Fires once, only at the exact moment is_onboarded transitions INTO 4
    for a user who has the "College Base" role.
    """
    if not _has_college_role(doc):
        return

    if doc.get("is_onboarded") != 4:
        return

    # if doc.get("college_onboarding_email_sent"):
    #     return

    doc_before = doc.get_doc_before_save()
    if doc_before is not None:
        if doc_before.get("is_onboarded") == 4:
            return

    _send_college_email(doc)

    # frappe.db.set_value("User", doc.name, "college_onboarding_email_sent", 1, update_modified=False)


def _send_college_email(doc):
    college_name = doc.get("full_name") or doc.get("first_name") or doc.name
    subject = "🎉 You're All Set! Your College Onboarding is Complete"
    message = frappe.render_template(COLLEGE_EMAIL_TEMPLATE, {"college_name": college_name})
    frappe.sendmail(recipients=[doc.email], subject=subject, message=message, now=True)


COLLEGE_EMAIL_TEMPLATE = """
<div style="margin:0;padding:0;background:#f6f6f8;font-family:'Inter',-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;">
  <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background:#f6f6f8;padding:30px 15px;">
    <tr>
      <td align="center">

        <table role="presentation" width="100%" cellspacing="0" cellpadding="0"
          style="max-width:650px;background:#ffffff;border:1px solid #e2e8f0;border-radius:16px;overflow:hidden;">

          <!-- Header -->
          <tr>
            <td style="background:#0f0fbd;padding:32px;text-align:center;">
              <h1 style="margin:0;color:#ffffff;font-size:28px;font-weight:700;">
                🎉 Welcome to StrideNex
              </h1>
              <p style="margin:10px 0 0;color:#dbeafe;font-size:15px;">
                Your college account is now active and fully onboarded
              </p>
            </td>
          </tr>

          <!-- Body -->
          <tr>
            <td style="padding:32px;">

              <p style="margin:0 0 20px;color:#1E293B;font-size:16px;line-height:1.8;">
                Hi <strong>{{ college_name }}</strong>,
              </p>

              <div style="background:#f0fdf4;border-left:4px solid #10b981;padding:18px;border-radius:8px;margin-bottom:24px;">
                <p style="margin:0;color:#065f46;font-size:15px;line-height:1.8;">
                  🎉 Congratulations! Your college onboarding is now
                  <strong>complete</strong>. Your institution is ready to leverage
                  the full power of StrideNex to support students, placements,
                  mentoring, and career development.
                </p>
              </div>

              <!-- Pack Activation -->
              <div style="background:#eef2ff;border-left:4px solid #0f0fbd;padding:18px;border-radius:8px;margin-bottom:24px;">
                <h3 style="margin:0 0 10px;color:#0f0fbd;font-size:16px;">
                  College Base Pack Activated
                </h3>

                <p style="margin:0;color:#1E293B;font-size:14px;line-height:1.8;">
                  Your <strong>College Base Pack</strong> starts today and will remain active for
                  <strong>60 days</strong>.
                </p>

                <p style="margin:10px 0 0;color:#64748B;font-size:14px;line-height:1.8;">
                  During this period, your institution can manage students,
                  connect with industry partners, organize placement drives,
                  monitor student development, and enhance employability outcomes.
                </p>
              </div>

              <h3 style="margin:0 0 16px;color:#0f0fbd;font-size:18px;">
                🚀 What You Can Do Now
              </h3>

              <table width="100%" cellspacing="0" cellpadding="0" style="margin-bottom:24px;">

                <tr>
                  <td style="padding:10px 0;color:#1E293B;">
                    👨‍🎓 <strong>Manage Students</strong><br>
                    <span style="color:#64748B;">
                      Add, monitor, and support student profiles and progress.
                    </span>
                  </td>
                </tr>

                <tr>
                  <td style="padding:10px 0;color:#1E293B;">
                    📊 <strong>Track Employability & Skills</strong><br>
                    <span style="color:#64748B;">
                      Monitor student skill development and employability metrics.
                    </span>
                  </td>
                </tr>

                <tr>
                  <td style="padding:10px 0;color:#1E293B;">
                    💼 <strong>Publish Placement Opportunities</strong><br>
                    <span style="color:#64748B;">
                      Connect students with internships, projects, and job opportunities.
                    </span>
                  </td>
                </tr>

                <tr>
                  <td style="padding:10px 0;color:#1E293B;">
                    🤝 <strong>Connect with Industry Partners</strong><br>
                    <span style="color:#64748B;">
                      Build stronger relationships with companies and recruiters.
                    </span>
                  </td>
                </tr>

                <tr>
                  <td style="padding:10px 0;color:#1E293B;">
                    🎯 <strong>Organize Placement Drives</strong><br>
                    <span style="color:#64748B;">
                      Conduct campus recruitment drives and streamline hiring processes.
                    </span>
                  </td>
                </tr>

                <tr>
                  <td style="padding:10px 0;color:#1E293B;">
                    📈 <strong>View Analytics & Reports</strong><br>
                    <span style="color:#64748B;">
                      Gain insights into student engagement, placements, and outcomes.
                    </span>
                  </td>
                </tr>

              </table>

              <div style="background:#fff7ed;border-left:4px solid #ff6b00;padding:18px;border-radius:8px;">
                <p style="margin:0;color:#9a3412;font-size:14px;line-height:1.8;">
                  Start exploring StrideNex today and empower your students with
                  better career opportunities, mentorship, and industry connections.
                </p>
              </div>

            </td>
          </tr>

          <!-- Footer -->
          <tr>
            <td style="background:#0F172A;padding:24px;text-align:center;">
              <p style="margin:0;color:#ffffff;font-size:16px;font-weight:600;">
                Welcome to the StrideNex Partner Network
              </p>

              <p style="margin:10px 0 0;color:#94a3b8;font-size:13px;">
                Empowering Skills • Building Careers • Creating Opportunities
              </p>

              <div style="margin-top:16px;padding-top:16px;border-top:1px solid #334155;">
                <p style="margin:0;color:#94a3b8;font-size:12px;">
                  Best Regards,<br>
                  <span style="color:#ffffff;font-weight:600;">StrideNex Team</span>
                </p>
              </div>
            </td>
          </tr>

        </table>

      </td>
    </tr>
  </table>
</div>
"""


# ============================== INDUSTRY FLOW ================================

def _has_industry_role(doc):
    role_list = doc.get("roles") or []
    return any(getattr(r, "role", None) == INDUSTRY_ROLE for r in role_list)


def send_industry_onboarding_email(doc, method=None):
    """
    Fires once, only at the exact moment is_onboarded transitions INTO 3
    for a user who has the "Industry Base" role.

    Note: is_onboarded == 3 is shared with the Mentor flow above, but since
    the role check (_has_industry_role vs _has_mentor_role) is different,
    the two will never both fire for the same user unless that user somehow
    has both roles assigned.
    """
    if not _has_industry_role(doc):
        return

    if doc.get("is_onboarded") != 3:
        return

    # if doc.get("industry_onboarding_email_sent"):
    #     return

    doc_before = doc.get_doc_before_save()
    if doc_before is not None:
        if doc_before.get("is_onboarded") == 3:
            return

    _send_industry_email(doc)

    # frappe.db.set_value("User", doc.name, "industry_onboarding_email_sent", 1, update_modified=False)


def _send_industry_email(doc):
    industry_name = doc.get("full_name") or doc.get("first_name") or doc.name
    subject = "🎉 You're All Set! Your Industry Onboarding is Complete"
    message = frappe.render_template(INDUSTRY_EMAIL_TEMPLATE, {"industry_name": industry_name})
    frappe.sendmail(recipients=[doc.email], subject=subject, message=message, now=True)


INDUSTRY_EMAIL_TEMPLATE = """
<div style="margin:0;padding:0;background:#f6f6f8;font-family:'Inter',-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;">
  <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background:#f6f6f8;padding:30px 15px;">
    <tr>
      <td align="center">

        <table role="presentation" width="100%" cellspacing="0" cellpadding="0"
          style="max-width:650px;background:#ffffff;border:1px solid #e2e8f0;border-radius:16px;overflow:hidden;">

          <!-- Header -->
          <tr>
            <td style="background:#0f0fbd;padding:32px;text-align:center;">
              <h1 style="margin:0;color:#ffffff;font-size:28px;font-weight:700;">
                🎉 Welcome to StrideNex
              </h1>
              <p style="margin:10px 0 0;color:#dbeafe;font-size:15px;">
                Your industry account is now active and fully verified
              </p>
            </td>
          </tr>

          <!-- Body -->
          <tr>
            <td style="padding:32px;">

              <p style="margin:0 0 20px;color:#1E293B;font-size:16px;line-height:1.8;">
                Hi <strong>{{ industry_name }}</strong>,
              </p>

              <div style="background:#f0fdf4;border-left:4px solid #10b981;padding:18px;border-radius:8px;margin-bottom:24px;">
                <p style="margin:0;color:#065f46;font-size:15px;line-height:1.8;">
                  🎉 Congratulations! Your industry onboarding is now
                  <strong>complete</strong> and your account has been successfully verified.
                  You're ready to connect with talented students, mentors, and educational institutions through StrideNex.
                </p>
              </div>

              <!-- Pack Activation -->
              <div style="background:#eef2ff;border-left:4px solid #0f0fbd;padding:18px;border-radius:8px;margin-bottom:24px;">
                <h3 style="margin:0 0 10px;color:#0f0fbd;font-size:16px;">
                  Industry Base Pack Activated
                </h3>

                <p style="margin:0;color:#1E293B;font-size:14px;line-height:1.8;">
                  Your <strong>Industry Base Pack</strong> starts today and will remain active for
                  <strong>60 days</strong>.
                </p>

                <p style="margin:10px 0 0;color:#64748B;font-size:14px;line-height:1.8;">
                  During this period, you can discover talent, publish internships,
                  manage industry projects, engage with colleges, and streamline your recruitment efforts.
                </p>
              </div>

              <h3 style="margin:0 0 16px;color:#0f0fbd;font-size:18px;">
                🚀 What You Can Do Now
              </h3>

              <table width="100%" cellspacing="0" cellpadding="0" style="margin-bottom:24px;">

                <tr>
                  <td style="padding:10px 0;color:#1E293B;">
                    🔍 <strong>Find Talent</strong><br>
                    <span style="color:#64748B;">
                      Search and discover students with the skills and qualifications your organization needs.
                    </span>
                  </td>
                </tr>

                <tr>
                  <td style="padding:10px 0;color:#1E293B;">
                    💼 <strong>Post Internships & Track Applications</strong><br>
                    <span style="color:#64748B;">
                      Create internship opportunities and monitor applicant progress throughout the hiring process.
                    </span>
                  </td>
                </tr>

                <tr>
                  <td style="padding:10px 0;color:#1E293B;">
                    🚀 <strong>Post Industry Projects</strong><br>
                    <span style="color:#64748B;">
                      Engage students through real-world projects and track project participation and outcomes.
                    </span>
                  </td>
                </tr>

                <tr>
                  <td style="padding:10px 0;color:#1E293B;">
                    📧 <strong>Generate Email Templates</strong><br>
                    <span style="color:#64748B;">
                      Create professional communication templates for outreach, hiring, and engagement.
                    </span>
                  </td>
                </tr>

                <tr>
                  <td style="padding:10px 0;color:#1E293B;">
                    🤝 <strong>Collaborate with Colleges</strong><br>
                    <span style="color:#64748B;">
                      Build relationships with educational institutions and participate in campus initiatives.
                    </span>
                  </td>
                </tr>

                <tr>
                  <td style="padding:10px 0;color:#1E293B;">
                    📊 <strong>Track Recruitment Activity</strong><br>
                    <span style="color:#64748B;">
                      Monitor applications, project participation, internships, and hiring metrics in one place.
                    </span>
                  </td>
                </tr>

              </table>

              <div style="background:#fff7ed;border-left:4px solid #ff6b00;padding:18px;border-radius:8px;">
                <p style="margin:0;color:#9a3412;font-size:14px;line-height:1.8;">
                  Start building your future workforce today by connecting with skilled students,
                  mentors, and institutions through the StrideNex ecosystem.
                </p>
              </div>

            </td>
          </tr>

          <!-- Footer -->
          <tr>
            <td style="background:#0F172A;padding:24px;text-align:center;">
              <p style="margin:0;color:#ffffff;font-size:16px;font-weight:600;">
                Welcome to the StrideNex Industry Network
              </p>

              <p style="margin:10px 0 0;color:#94a3b8;font-size:13px;">
                Empowering Skills • Building Careers • Creating Opportunities
              </p>

              <div style="margin-top:16px;padding-top:16px;border-top:1px solid #334155;">
                <p style="margin:0;color:#94a3b8;font-size:12px;">
                  Best Regards,<br>
                  <span style="color:#ffffff;font-weight:600;">StrideNex Team</span>
                </p>
              </div>
            </td>
          </tr>

        </table>

      </td>
    </tr>
  </table>
</div>
"""

import frappe
from frappe.utils import today, getdate, formatdate


def send_daily_application_summaries():
    """Daily scheduled job — runs every morning."""
    send_project_application_summary()
    send_internship_application_summary()


# ---------------------------------------------------------------------
# PROJECT SIDE
# ---------------------------------------------------------------------
def send_project_application_summary():
    current_date = getdate(today())

    # Only projects whose deadline hasn't passed yet
    open_projects = frappe.get_all(
        "Industry Project",  # ADJUST doctype name if different
        filters={"application_deadline": [">=", current_date]},
        fields=["name", "industry", "project_name", "application_deadline"],  # ADJUST fields
    )

    for project in open_projects:
        total_enrollments = frappe.db.count(
            "Student Project Enrollment",  # ADJUST doctype name
            filters={"project": project["name"]},  # ADJUST link fieldname
        )

        notify_industry(
            industry=project.get("industry"),
            title=project.get("project_name") or project["name"],
            deadline=project.get("application_deadline"),
            total_applications=total_enrollments,
            doc_type="Industry Project",
            doc_name=project["name"],
            kind="Project",
        )


# ---------------------------------------------------------------------
# INTERNSHIP SIDE
# ---------------------------------------------------------------------
def send_internship_application_summary():
    current_date = getdate(today())

    open_internships = frappe.get_all(
        "Internship",  # ADJUST doctype name if different
        filters={"application_deadline": [">=", current_date]},
        fields=["name", "industry", "title", "application_deadline"],  # ADJUST fields
    )

    for internship in open_internships:
        total_applications = frappe.db.count(
            "Internship Application",  # ADJUST doctype name
            filters={"internship": internship["name"]},  # ADJUST link fieldname
        )

        notify_industry(
            industry=internship.get("industry"),
            title=internship.get("title") or internship["name"],
            deadline=internship.get("application_deadline"),
            total_applications=total_applications,
            doc_type="Internship",
            doc_name=internship["name"],
            kind="Internship",
        )

def notify_industry(industry, title, deadline, total_applications, doc_type, doc_name, kind):
    if not industry:
        return

    industry_doc = frappe.db.get_value(
        "Industry list", industry,
        ["email", "company_name"],  # ADJUST "industry_name" if field is named differently
        as_dict=True
    )

    if not industry_doc or not industry_doc.get("email"):
        frappe.log_error(f"No email found for Industry {industry}", "Application Summary Notify")
        return

    user_email = industry_doc["email"]
    notification_user = industry_doc.get("email")

    subject = f"Daily Update: {total_applications} application(s) received for {title}"

    message = f"""
    <div style="margin:0;padding:0;background:#f6f6f8;font-family:'Inter',-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;">
        <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background:#f6f6f8;padding:30px 15px;">
            <tr>
                <td align="center">

                    <table role="presentation" width="100%" cellspacing="0" cellpadding="0"
                        style="max-width:650px;background:#ffffff;border:1px solid #e2e8f0;border-radius:16px;overflow:hidden;">

                        <!-- Header -->
                        <tr>
                            <td style="background:#0f0fbd;padding:30px;text-align:center;">
                                <h1 style="margin:0;color:#ffffff;font-size:26px;font-weight:700;">
                                    📊 Daily Application Update
                                </h1>
                                <p style="margin:8px 0 0;color:#dbeafe;font-size:14px;">
                                    Latest status for your {kind.lower()}
                                </p>
                            </td>
                        </tr>

                        <!-- Body -->
                        <tr>
                            <td style="padding:32px;">

                                <p style="margin:0 0 20px;color:#1E293B;font-size:16px;line-height:1.8;">
                                    Dear <strong>{industry_doc.get('company_name') or 'Team'}</strong>,
                                </p>

                                <p style="margin:0 0 24px;color:#1E293B;font-size:15px;line-height:1.8;">
                                    Here is your latest update for:
                                </p>

                                <!-- Opportunity Card -->
                                <div style="background:#eef2ff;border-left:4px solid #0f0fbd;padding:18px;border-radius:8px;margin-bottom:24px;">
                                    <p style="margin:0;color:#1E293B;font-size:16px;font-weight:600;">
                                        {kind}: {title}
                                    </p>
                                </div>

                                <!-- Statistics -->
                                <div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:12px;padding:20px;margin-bottom:24px;">

                                    <table width="100%" style="border-collapse:collapse;">

                                        <tr>
                                            <td style="padding:10px 0;color:#64748B;font-size:14px;">
                                                <strong>Total Applications</strong>
                                            </td>
                                            <td style="padding:10px 0;text-align:right;color:#10b981;font-size:18px;font-weight:700;">
                                                {total_applications}
                                            </td>
                                        </tr>

                                        <tr>
                                            <td style="padding:10px 0;color:#64748B;font-size:14px;">
                                                <strong>Application Deadline</strong>
                                            </td>
                                            <td style="padding:10px 0;text-align:right;color:#ff6b00;font-size:14px;font-weight:600;">
                                                {formatdate(deadline)}
                                            </td>
                                        </tr>

                                    </table>

                                </div>

                                <!-- CTA -->
                                <div style="text-align:center;margin:30px 0;">
                                    <a href="{frappe.utils.get_url()}/app/{doc_type.lower().replace(' ', '-')}/{doc_name}"
                                    style="background:#0f0fbd;color:#ffffff;text-decoration:none;
                                            padding:14px 28px;border-radius:8px;
                                            font-size:15px;font-weight:600;display:inline-block;">
                                        View {kind} Details →
                                    </a>
                                </div>

                                <!-- Note -->
                                <div style="background:#fff7ed;border-left:4px solid #ff6b00;padding:16px 18px;border-radius:8px;">
                                    <p style="margin:0;color:#9a3412;font-size:14px;line-height:1.8;">
                                        We recommend reviewing applications regularly to identify top candidates and respond promptly before the deadline.
                                    </p>
                                </div>

                            </td>
                        </tr>

                        <!-- Footer -->
                        <tr>
                            <td style="background:#0F172A;padding:24px;text-align:center;">
                                <p style="margin:0;color:#ffffff;font-size:15px;font-weight:600;">
                                    StrideNex Industry Dashboard
                                </p>

                                <p style="margin:10px 0 0;color:#94a3b8;font-size:13px;">
                                    Empowering Skills • Building Careers • Creating Opportunities
                                </p>

                                <div style="margin-top:16px;padding-top:16px;border-top:1px solid #334155;">
                                    <p style="margin:0;color:#94a3b8;font-size:12px;">
                                        This is an automated daily summary from StrideNex.
                                    </p>
                                </div>
                            </td>
                        </tr>

                    </table>

                </td>
            </tr>
        </table>
    </div>
    """

    # ---- Email ----
    try:
        frappe.sendmail(
            recipients=[user_email],
            subject=subject,
            message=message,
            reference_doctype=doc_type,
            reference_name=doc_name,
        )
    except Exception:
        frappe.log_error(frappe.get_traceback(), f"Failed to email {kind} summary for {doc_name}")

    notification_message = (
        f"📊 {kind} Update\n"
        f"{title} received {total_applications} application(s).\n"
        f"Deadline: {formatdate(deadline)}"
    )
    
    if notification_user:
        try:
            notification = frappe.new_doc("Notification Log")
            notification.subject = subject
            notification.for_user = notification_user
            notification.type = "Alert"
            notification.document_type = doc_type
            notification.document_name = doc_name
            notification.from_user = "Administrator"
            notification.email_content = notification_message
            notification.insert(ignore_permissions=True)
            frappe.db.commit()
        except Exception:
            frappe.log_error(frappe.get_traceback(), f"Failed to create notification for {doc_name}")
            
            

import calendar
from datetime import datetime
 
import frappe
from frappe.utils import getdate, get_first_day, get_last_day, add_months
 
 
def get_month_range(reference_date=None, use_previous_month=True):
	"""Return (start_date, end_date, month_name, year) for the reporting window."""
	ref = getdate(reference_date or frappe.utils.nowdate())
	if use_previous_month:
		ref = add_months(ref, -1)
	start_date = get_first_day(ref)
	end_date = get_last_day(ref)
	month_name = calendar.month_name[start_date.month]
	return start_date, end_date, month_name, start_date.year
 
 
def send_monthly_summary():
	"""Main entry point — called by the scheduler."""
	start_date, end_date, month_name, year = get_month_range()
 
	students = frappe.get_all(
      "Student",
      fields=["name", "student_name", "email_id"]
  )
	# NOTE: adjust "student_email" / "student_name" above to match your actual
	# Student doctype fieldnames if they differ.
 
	for student in students:
		if not student.get("email_id"):
			frappe.log_error(
				title="Monthly Summary Skipped",
				message=f"No email found for student {student.name}",
			)
			continue
 
		context = build_student_summary(student, start_date, end_date, month_name, year)
 
		# Skip emailing students with zero activity for the month (optional)
		total_items = (
			len(context["projects"])
			+ len(context["internships"])
			+ len(context["habit_plans"])
			+ len(context["path_enrollments"])
			+ len(context["skills"])
		)
		if total_items == 0:
			continue
 
		message = frappe.render_template(
			"stridenex_app/templates/emails/monthly_summary.html", context
		)
 
		frappe.sendmail(
			recipients=[student.email_id],
			subject=f"Your {month_name} {year} Progress Summary",
			message=message,
			reference_doctype="Student",
			reference_name=student.name,
		)
 
	frappe.db.commit()
 
 
def build_student_summary(student, start_date, end_date, month_name, year):
	student_id = student.name
 
	# 1. Project Enrollments applied this month
	projects = frappe.get_all(
		"Student Project Enrollment",
		filters={
			"student": student_id,
			"applied_on": ["between", [start_date, end_date]],
		},
		fields=["project", "status", "applied_on", "match_score"],
		order_by="applied_on desc",
	)
 
	# 2. Internship Applications applied this month
	internships = frappe.get_all(
		"Internship Application",
		filters={
			"student": student_id,
			"applied_on": ["between", [start_date, end_date]],
		},
		fields=["internship", "status", "applied_on", "match_score"],
		order_by="applied_on desc",
	)
 
	# 3. Habit Plans that started this month OR were active during the month
	habit_plans = frappe.get_all(
		"Habit Plan",
		filters=[
			["student", "=", student_id],
			["start_date", "<=", end_date],
			[
				"start_date", ">=", start_date
			],  # started within the month; change logic below for "active during" instead
		],
		fields=["name", "plan_name", "start_date", "end_date", "status"],
		order_by="start_date desc",
	)
	# attach habit rows (child table) for each plan
	for hp in habit_plans:
		doc = frappe.get_doc("Habit Plan", hp.name)
		hp["habits"] = [
			row.get("habit_name") or row.get("habit") or str(row.as_dict())
			for row in doc.habits
		]
 
	# 4. Career Path Enrollments (show current status/progress regardless of
	#    enrollment date, since this is ongoing progress, not a one-off event;
	#    swap to a date filter on enrolled_at if you only want new enrollments)
	path_enrollments = frappe.get_all(
		"Student Path Enrollment",
		filters={"student": student_id, "status": ["!=", "Abandoned"]},
		fields=["career_path", "status", "completion_percent", "target_date", "enrolled_at"],
		order_by="enrolled_at desc",
	)
 
	# 5. Skills first acquired this month
	skills = frappe.get_all(
		"Student Skill",
		filters={
			"student": student_id,
			"first_acquired": ["between", [start_date, end_date]],
		},
		fields=["skill", "current_level", "status", "first_acquired"],
		order_by="first_acquired desc",
	)
 
	return {
      "student_name": (
          f"{student.first_name or ''} {student.last_name or ''}"
      ).strip() or student.name,
      "month_name": month_name,
      "year": year,
      "projects": projects,
      "internships": internships,
      "habit_plans": habit_plans,
      "path_enrollments": path_enrollments,
      "skills": skills,
  }
 
def send_test_summary(student_id):
    student = frappe.get_doc("Student", student_id)

    if not student.email_id:
        frappe.throw("Student does not have an email_id")

    start_date, end_date, month_name, year = get_month_range()

    context = build_student_summary(
        student,
        start_date,
        end_date,
        month_name,
        year,
    )

    projects = context["projects"]
    internships = context["internships"]
    habit_plans = context["habit_plans"]
    path_enrollments = context["path_enrollments"]
    skills = context["skills"]

    # message = frappe.render_template(
    #     "stridenex_app/templates/emails/monthly_summary.html",
    #     context,
    # )
    
    message = f"""
<div style="margin:0;padding:20px;background:#f6f6f8;font-family:'Inter',Arial,sans-serif;">
    <div style="max-width:650px;margin:0 auto;background:#ffffff;border-radius:16px;overflow:hidden;border:1px solid #e2e8f0;">

        <!-- Header -->
        <div style="background:linear-gradient(135deg,#0f0fbd,#2e2ed9);padding:30px;text-align:center;">
            <h1 style="margin:0;color:#ffffff;font-size:28px;font-weight:700;">
                Monthly Progress Summary
            </h1>
            <p style="margin:8px 0 0;color:#dbe4ff;font-size:14px;">
                {month_name} {year}
            </p>
        </div>

        <!-- Body -->
        <div style="padding:30px;">

            <p style="margin-top:0;color:#101622;font-size:15px;">
                Hello <strong>{student}</strong>,
            </p>

            <p style="color:#64748B;font-size:14px;line-height:1.6;">
                Here's a snapshot of your activity on StrideNex during {month_name}.
            </p>

            <!-- Summary Cards -->
            <table width="100%" cellspacing="0" cellpadding="0" style="margin-top:20px;">
                <tr>
                    <td width="50%" style="padding:8px;">
                        <div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:12px;padding:16px;text-align:center;">
                            <div style="font-size:28px;font-weight:700;color:#0f0fbd;">
                                {len(projects)}
                            </div>
                            <div style="font-size:13px;color:#64748B;">
                                Project Applications
                            </div>
                        </div>
                    </td>

                    <td width="50%" style="padding:8px;">
                        <div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:12px;padding:16px;text-align:center;">
                            <div style="font-size:28px;font-weight:700;color:#ff6b00;">
                                {len(internships)}
                            </div>
                            <div style="font-size:13px;color:#64748B;">
                                Internship Applications
                            </div>
                        </div>
                    </td>
                </tr>

                <tr>
                    <td width="50%" style="padding:8px;">
                        <div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:12px;padding:16px;text-align:center;">
                            <div style="font-size:28px;font-weight:700;color:#0f0fbd;">
                                {len(habit_plans)}
                            </div>
                            <div style="font-size:13px;color:#64748B;">
                                Habit Plans
                            </div>
                        </div>
                    </td>

                    <td width="50%" style="padding:8px;">
                        <div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:12px;padding:16px;text-align:center;">
                            <div style="font-size:28px;font-weight:700;color:#ff6b00;">
                                {len(skills)}
                            </div>
                            <div style="font-size:13px;color:#64748B;">
                                Skills Added
                            </div>
                        </div>
                    </td>
                </tr>
            </table>

            {
                f'''
                <div style="margin-top:28px;padding:18px;background:#f8fafc;border-left:4px solid #ff6b00;border-radius:8px;">
                    <h3 style="margin:0 0 10px;color:#101622;font-size:16px;">
                        Career Path Progress
                    </h3>

                    {
                        "".join(
                            f'<div style="margin-bottom:8px;font-size:14px;color:#475569;">'
                            f'<strong>{p.career_path}</strong> — {p.completion_percent}% Complete'
                            f'</div>'
                            for p in path_enrollments[:3]
                        )
                    }
                </div>
                '''
                if path_enrollments else ""
            }

            {
                f'''
                <div style="margin-top:24px;">
                    <h3 style="margin-bottom:10px;color:#101622;font-size:16px;">
                        Recently Added Skills
                    </h3>

                    {
                        "".join(
                            f'<span style="display:inline-block;background:#eef2ff;color:#0f0fbd;padding:6px 12px;border-radius:20px;font-size:12px;margin:4px;">{s.skill}</span>'
                            for s in skills[:5]
                        )
                    }
                </div>
                '''
                if skills else ""
            }

            <!-- Footer -->
            <div style="margin-top:32px;padding-top:20px;border-top:1px solid #e2e8f0;">
                <p style="margin:0;color:#64748B;font-size:13px;line-height:1.6;">
                    Keep learning, building, and growing.
                </p>

                <p style="margin:10px 0 0;color:#101622;font-weight:600;">
                    Team StrideNex
                </p>
            </div>

        </div>
    </div>
</div>
"""

    frappe.sendmail(
        recipients=[student.email_id],
        subject=f"[TEST] Your {month_name} {year} Progress Summary",
        message=message,
    )
    frappe.db.commit()

    return "Sent"



# apps/stridenex_app/stridenex_app/tasks/industry_monthly_summary.py
#
# Sends every Industry a month-end email showing:
#   - How many Internships they posted this month, total applicants, selected
#   - How many Industry Projects they posted this month, total applicants, selected
#
# SCHEDULING — add to hooks.py:
#
#   scheduler_events = {
#       "monthly": [
#           "stridenex_app.tasks.industry_monthly_summary.send_industry_monthly_summary"
#       ]
#   }
#
# FIELD MAPPING (confirmed against your "Industry list" doctype JSON):
#   - Industry list -> "email" (contact email), "company_name" (display name + doc name,
#     since autoname is field:company_name)
#   - Internship / Industry Project are ASSUMED to have a link field "industry"
#     pointing to Industry list. ADJUST if your actual fieldname differs.

import calendar
import traceback

import frappe
from frappe.utils import getdate, get_first_day, get_last_day, add_months

DASHBOARD_URL = "https://devstridenex.quantcloud.in"

INTERNSHIP_SELECTED_STATUSES = ("Selected",)
PROJECT_SELECTED_STATUSES = ("Selected", "Awarded")


def get_month_range(reference_date=None, use_previous_month=True):
	"""Return (start_date, end_date, month_name, year) for the reporting window."""
	ref = getdate(reference_date or frappe.utils.nowdate())
	if use_previous_month:
		ref = add_months(ref, -1)
	start_date = get_first_day(ref)
	end_date = get_last_day(ref)
	month_name = calendar.month_name[start_date.month]
	return start_date, end_date, month_name, start_date.year


# ---------------------------------------------------------------------------
# HELPER — use this from bench console to find the exact industry name/ID
# ---------------------------------------------------------------------------

def list_industries(search=None):
	"""Quick lookup helper. Run from bench console:

	    from stridenex_app.tasks.industry_monthly_summary import list_industries
	    list_industries()                 # list all
	    list_industries("codeworks")      # filter by partial name (case-insensitive)
	"""
	filters = {}
	if search:
		filters = {"company_name": ["like", f"%{search}%"]}
	rows = frappe.get_all(
		"Industry list",
		filters=filters,
		fields=["name", "company_name", "email", "status"],
	)
	for r in rows:
		print(f"name={r.name!r}  company_name={r.company_name!r}  email={r.email!r}  status={r.status}")
	return rows


# ---------------------------------------------------------------------------
# DATA GATHERING
# ---------------------------------------------------------------------------

def build_industry_summary(industry, start_date, end_date, month_name, year):
	industry_id = industry.get("name")

	# ---------------- Internships ----------------
	all_internships = frappe.get_all(
		"Internship",
		filters={"industry": industry_id},          # ADJUST if link fieldname differs
		fields=["name", "title"],
	)
	all_internship_ids = [i.name for i in all_internships]

	new_internship_count = frappe.db.count(
		"Internship",
		filters={
			"industry": industry_id,                # ADJUST
			"creation": ["between", [start_date, end_date]],
		},
	)

	internship_apps = []
	if all_internship_ids:
		internship_apps = frappe.get_all(
			"Internship Application",
			filters={
				"internship": ["in", all_internship_ids],
				"applied_on": ["between", [start_date, end_date]],
			},
			fields=["internship", "status"],
		)
	total_internship_applicants = len(internship_apps)
	selected_internship_applicants = len(
		[a for a in internship_apps if a.status in INTERNSHIP_SELECTED_STATUSES]
	)

	internship_title_by_id = {i.name: (i.title or i.name) for i in all_internships}
	apps_by_internship = {}
	for a in internship_apps:
		apps_by_internship.setdefault(a.internship, []).append(a)

	internship_breakdown = sorted(
		[
			{
				"title": internship_title_by_id.get(iid, iid),
				"applicants": len(apps),
				"selected": len([a for a in apps if a.status in INTERNSHIP_SELECTED_STATUSES]),
			}
			for iid, apps in apps_by_internship.items()
		],
		key=lambda x: x["applicants"],
		reverse=True,
	)[:5]

	# ---------------- Industry Projects ----------------
	all_projects = frappe.get_all(
		"Industry Project",
		filters={"industry": industry_id},          # ADJUST if link fieldname differs
		fields=["name", "project_name"],
	)
	all_project_ids = [p.name for p in all_projects]

	new_project_count = frappe.db.count(
		"Industry Project",
		filters={
			"industry": industry_id,                # ADJUST
			"creation": ["between", [start_date, end_date]],
		},
	)

	project_apps = []
	if all_project_ids:
		project_apps = frappe.get_all(
			"Student Project Enrollment",
			filters={
				"project": ["in", all_project_ids],
				"applied_on": ["between", [start_date, end_date]],
			},
			fields=["project", "status"],
		)
	total_project_applicants = len(project_apps)
	selected_project_applicants = len(
		[a for a in project_apps if a.status in PROJECT_SELECTED_STATUSES]
	)

	project_title_by_id = {p.name: (p.title or p.name) for p in all_projects}
	apps_by_project = {}
	for a in project_apps:
		apps_by_project.setdefault(a.project, []).append(a)

	project_breakdown = sorted(
		[
			{
				"title": project_title_by_id.get(pid, pid),
				"applicants": len(apps),
				"selected": len([a for a in apps if a.status in PROJECT_SELECTED_STATUSES]),
			}
			for pid, apps in apps_by_project.items()
		],
		key=lambda x: x["applicants"],
		reverse=True,
	)[:5]

	return {
		"industry_name": industry.get("company_name") or industry.get("name"),
		"month_name": month_name,
		"year": year,
		"dashboard_url": DASHBOARD_URL,
		"new_internship_count": new_internship_count,
		"total_internship_applicants": total_internship_applicants,
		"selected_internship_applicants": selected_internship_applicants,
		"internship_breakdown": internship_breakdown,
		"new_project_count": new_project_count,
		"total_project_applicants": total_project_applicants,
		"selected_project_applicants": selected_project_applicants,
		"project_breakdown": project_breakdown,
	}


# ---------------------------------------------------------------------------
# JINJA TEMPLATE
# ---------------------------------------------------------------------------

INDUSTRY_SUMMARY_TEMPLATE = """
<div style="margin:0;padding:20px;background:#f6f6f8;font-family:'Inter',Arial,sans-serif;">
    <div style="max-width:650px;margin:0 auto;background:#ffffff;border-radius:16px;overflow:hidden;border:1px solid #e2e8f0;">

        <div style="background:linear-gradient(135deg,#0f0fbd,#2e2ed9);padding:30px;text-align:center;">
            <h1 style="margin:0;color:#ffffff;font-size:28px;font-weight:700;">
                Monthly Hiring Summary
            </h1>
            <p style="margin:8px 0 0;color:#dbe4ff;font-size:14px;">
                {{ month_name }} {{ year }}
            </p>
        </div>

        <div style="padding:30px;">

            <p style="margin-top:0;color:#101622;font-size:15px;">
                Hello <strong>{{ industry_name }}</strong>,
            </p>

            <p style="color:#64748B;font-size:14px;line-height:1.6;">
                Here's how your listings performed on StrideNex during {{ month_name }}.
            </p>

            <table width="100%" cellspacing="0" cellpadding="0" style="margin-top:20px;">
                <tr>
                    <td width="50%" style="padding:8px;">
                        <div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:12px;padding:16px;text-align:center;">
                            <div style="font-size:28px;font-weight:700;color:#0f0fbd;">
                                {{ new_internship_count }}
                            </div>
                            <div style="font-size:13px;color:#64748B;">
                                Internships Posted
                            </div>
                        </div>
                    </td>

                    <td width="50%" style="padding:8px;">
                        <div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:12px;padding:16px;text-align:center;">
                            <div style="font-size:28px;font-weight:700;color:#ff6b00;">
                                {{ total_internship_applicants }}
                            </div>
                            <div style="font-size:13px;color:#64748B;">
                                Internship Applicants
                            </div>
                        </div>
                    </td>
                </tr>

                <tr>
                    <td width="50%" style="padding:8px;">
                        <div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:12px;padding:16px;text-align:center;">
                            <div style="font-size:28px;font-weight:700;color:#0f0fbd;">
                                {{ new_project_count }}
                            </div>
                            <div style="font-size:13px;color:#64748B;">
                                Projects Posted
                            </div>
                        </div>
                    </td>

                    <td width="50%" style="padding:8px;">
                        <div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:12px;padding:16px;text-align:center;">
                            <div style="font-size:28px;font-weight:700;color:#ff6b00;">
                                {{ total_project_applicants }}
                            </div>
                            <div style="font-size:13px;color:#64748B;">
                                Project Applicants
                            </div>
                        </div>
                    </td>
                </tr>
            </table>

            <div style="margin-top:28px;padding:18px;background:#f8fafc;border-left:4px solid #ff6b00;border-radius:8px;">
                <h3 style="margin:0 0 10px;color:#101622;font-size:16px;">
                    Selections This Month
                </h3>
                <div style="margin-bottom:8px;font-size:14px;color:#475569;">
                    <strong>Internships:</strong> {{ selected_internship_applicants }} student(s) selected
                </div>
                <div style="font-size:14px;color:#475569;">
                    <strong>Projects:</strong> {{ selected_project_applicants }} student(s) selected
                </div>
            </div>

            {% if internship_breakdown %}
            <div style="margin-top:24px;">
                <h3 style="margin-bottom:10px;color:#101622;font-size:16px;">
                    Top Internships
                </h3>
                {% for r in internship_breakdown %}
                <span style="display:inline-block;background:#eef2ff;color:#0f0fbd;padding:6px 12px;border-radius:20px;font-size:12px;margin:4px;">
                    {{ r.title }} &mdash; {{ r.applicants }} applicants, {{ r.selected }} selected
                </span>
                {% endfor %}
            </div>
            {% endif %}

            {% if project_breakdown %}
            <div style="margin-top:24px;">
                <h3 style="margin-bottom:10px;color:#101622;font-size:16px;">
                    Top Industry Projects
                </h3>
                {% for r in project_breakdown %}
                <span style="display:inline-block;background:#eef2ff;color:#0f0fbd;padding:6px 12px;border-radius:20px;font-size:12px;margin:4px;">
                    {{ r.title }} &mdash; {{ r.applicants }} applicants, {{ r.selected }} selected
                </span>
                {% endfor %}
            </div>
            {% endif %}

            <div style="text-align:center;margin-top:28px;">
                <a href="{{ dashboard_url }}"
                   style="background:#ff6b00;color:#ffffff;padding:12px 24px;
                   text-decoration:none;border-radius:6px;display:inline-block;font-size:14px;">
                    View Full Dashboard
                </a>
            </div>

            <div style="margin-top:32px;padding-top:20px;border-top:1px solid #e2e8f0;">
                <p style="margin:0;color:#64748B;font-size:13px;line-height:1.6;">
                    Thanks for hiring through StrideNex.
                </p>

                <p style="margin:10px 0 0;color:#101622;font-weight:600;">
                    Team StrideNex
                </p>
            </div>

        </div>
    </div>
</div>
"""


def render_industry_summary_html(context):
	return frappe.render_template(INDUSTRY_SUMMARY_TEMPLATE, context)


# ---------------------------------------------------------------------------
# SEND FUNCTIONS
# ---------------------------------------------------------------------------

def send_industry_monthly_summary():
	"""Scheduler entry point — sends every Industry their monthly summary."""
	start_date, end_date, month_name, year = get_month_range()

	industries = frappe.get_all(
		"Industry list", fields=["name", "company_name", "email"]
	)

	sent_count = 0
	skipped_count = 0
	failed_count = 0

	for industry in industries:
		try:
			if not industry.get("email"):
				skipped_count += 1
				continue

			context = build_industry_summary(industry, start_date, end_date, month_name, year)

			total_activity = (
				context["new_internship_count"]
				+ context["total_internship_applicants"]
				+ context["new_project_count"]
				+ context["total_project_applicants"]
			)
			if total_activity == 0:
				skipped_count += 1
				continue

			message = render_industry_summary_html(context)

			frappe.sendmail(
				recipients=[industry.email],
				subject=f"Your {month_name} {year} Hiring Summary - StrideNex",
				message=message,
				reference_doctype="Industry list",
				reference_name=industry.name,
				now=True,
			)
			sent_count += 1

		except Exception:
			failed_count += 1
			frappe.log_error(
				title=f"Industry Monthly Summary Failed: {industry.get('name')}",
				message=traceback.format_exc(),
			)
			continue

	frappe.db.commit()
	frappe.logger().info(
		f"Industry monthly summary run complete: sent={sent_count}, "
		f"skipped={skipped_count}, failed={failed_count}"
	)


def send_test_industry_summary(industry_id, override_email=None):
	"""Run manually from bench console to test a single industry.

	industry_id must be the EXACT document name — since Industry list's
	autoname is field:company_name, this is the exact company_name value.
	Use list_industries() first if you're not sure of the exact spelling.

	override_email: optionally send to a different address than the one
	stored on the record (handy for testing without touching real data).
	"""
	industry = frappe.get_doc("Industry list", industry_id)

	recipient = override_email or industry.email
	if not recipient:
		frappe.throw("Industry does not have an email, and no override_email was given")

	start_date, end_date, month_name, year = get_month_range()

	context = build_industry_summary(
		{"name": industry.name, "company_name": industry.company_name},
		start_date, end_date, month_name, year,
	)

	message = render_industry_summary_html(context)

	frappe.sendmail(
		recipients=[recipient],
		subject=f"[TEST] Your {month_name} {year} Hiring Summary - StrideNex",
		message=message,
		now=True,
	)
	frappe.db.commit()

	return "Sent"