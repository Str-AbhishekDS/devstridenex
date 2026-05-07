# File: stridenex_app/api/admin_notification.py

import frappe
from frappe import _
from frappe.utils import now_datetime

@frappe.whitelist(allow_guest=True)
def get_notifications(module=None):
    """
    GET /api/method/stridenex_app.api.admin_notification.get_notifications
    Query Params:
        - module (optional): Student | College | Industry | Mentor
    
    Returns notifications where:
        - schedule_a_notification <= current datetime (i.e., time to show)
        - Optionally filtered by select_module
        - Only submitted (docstatus=1) documents
    """

    filters = {
        "schedule_a_notification": ("<=", now_datetime()),
    }

    if module:
        valid_modules = ["Student", "College", "Industry", "Mentor"]
        if module not in valid_modules:
            frappe.throw(_("Invalid module. Must be one of: {0}").format(", ".join(valid_modules)))
        filters["select_module"] = module

    notifications = frappe.get_all(
        "Admin Notification",
        filters=filters,
        fields=[
            "name",
            "title",
            "select_module",
            "schedule_a_notification",
            "message",
            "status",
            "creation",
        ],
        order_by="schedule_a_notification desc",
    )

    return {
        "status": "success",
        "count": len(notifications),
        "data": notifications,
    }

@frappe.whitelist(allow_guest=False)
def mark_as_seen(notification_name):
    """
    POST /api/method/stridenex_app.api.admin_notification.mark_as_seen
    Body:
        - notification_name: name/ID of the Admin Notification doc (e.g., "Admin Notification-00001")
    
    Transitions status from 'Unseen' to 'Seen'.
    Note: Since the doctype is submittable, we use db_set to bypass submit lock.
    """

    if not notification_name:
        frappe.throw(_("notification_name is required"))

    # Check if document exists
    if not frappe.db.exists("Admin Notification", notification_name):
        frappe.throw(_("Notification '{0}' not found").format(notification_name), frappe.DoesNotExistError)

    doc = frappe.get_doc("Admin Notification", notification_name)

    if doc.docstatus != 1:
        frappe.throw(_("Only submitted notifications can be updated"))

    if doc.status == "Seen":
        return {
            "status": "info",
            "message": "Notification is already marked as Seen",
            "name": notification_name,
        }

    # db_set bypasses the submit lock on docstatus=1 docs
    doc.db_set("status", "Seen", update_modified=True)
    frappe.db.commit()

    return {
        "status": "success",
        "message": "Notification marked as Seen",
        "name": notification_name,
    }


@frappe.whitelist(allow_guest=False)
def mark_all_as_seen(module=None):
    """
    POST /api/method/stridenex_app.api.admin_notification.mark_all_as_seen
    Body:
        - module (optional): Mark all unseen for a specific module
    """

    filters = {
        "docstatus": 1,
        "status": "Unseen",
        "schedule_a_notification": ("<=", now_datetime()),
    }

    if module:
        filters["select_module"] = module

    unseen_docs = frappe.get_all("Admin Notification", filters=filters, pluck="name")

    if not unseen_docs:
        return {"status": "info", "message": "No unseen notifications found", "updated": 0}

    frappe.db.set_value(
        "Admin Notification",
        {"name": ("in", unseen_docs)},
        "status",
        "Seen",
    )
    frappe.db.commit()

    return {
        "status": "success",
        "message": f"{len(unseen_docs)} notification(s) marked as Seen",
        "updated": len(unseen_docs),
        "names": unseen_docs,
    }