# File: stridenex_app/api/admin_notification.py

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