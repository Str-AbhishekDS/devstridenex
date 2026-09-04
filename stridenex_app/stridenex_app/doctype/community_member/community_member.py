# Copyright (c) 2026, QTPL and contributors
# For license information, please see license.txt

# import frappe
from frappe.model.document import Document


class CommunityMember(Document):
	pass

import frappe


@frappe.whitelist(allow_guest=True)
def update_community_member_status(name=None, status=None):
    """
    Update only the status of a Community Member.

    Required:
        name   - Community Member document name
        status - Pending / Approved / Rejected / Blocked
    """

    try:
        # -----------------------------------
        # VALIDATION
        # -----------------------------------
        if not name:
            return {
                "status": 400,
                "message": "Community Member name is required"
            }

        if not status:
            return {
                "status": 400,
                "message": "Status is required"
            }

        # -----------------------------------
        # VALID STATUS
        # -----------------------------------
        allowed_statuses = [
            "Pending",
            "Approved",
            "Rejected",
            "Blocked"
        ]

        if status not in allowed_statuses:
            return {
                "status": 400,
                "message": "Invalid status",
                "allowed_statuses": allowed_statuses
            }

        # -----------------------------------
        # CHECK DOCUMENT
        # -----------------------------------
        if not frappe.db.exists("Community Member", name):
            return {
                "status": 404,
                "message": "Community Member not found"
            }

        # -----------------------------------
        # UPDATE STATUS
        # -----------------------------------
        frappe.db.set_value(
            "Community Member",
            name,
            "status",
            status
        )

        frappe.db.commit()

        # -----------------------------------
        # RESPONSE
        # -----------------------------------
        return {
            "status": 200,
            "message": "Community Member status updated successfully",
            "data": {
                "name": name,
                "status": status
            }
        }

    except Exception as e:
        frappe.log_error(
            frappe.get_traceback(),
            "Update Community Member Status API Error"
        )

        return {
            "status": 500,
            "message": "Failed to update status",
            "error": str(e)
        }

