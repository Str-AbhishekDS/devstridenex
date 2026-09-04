# Copyright (c) 2026, QTPL and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe import _
from frappe.utils import format_datetime
from frappe.desk.doctype.notification_log.notification_log import enqueue_create_notification
from stridenex_app.api_stridenex_app.app_utils import (
    gen_response,
    exception_handel,
    get_pagination_params,
    make_cache_key,
    make_pagination_meta,
)

DEFAULT_PAGE_SIZE = 20


def resolve_college_name(college):
    """Resolve a college email to its document name if needed."""
    if not college:
        return college
    if "@" in college:
        resolved = frappe.db.get_value("College", {"email": college}, "name")
        if resolved:
            return resolved
    return college


class CollegeNotice(Document):
    pass


# ── Helper: get all student user emails for a college ────────────────────────
def _get_college_student_users(college):
    """Return a list of enabled student user emails belonging to *college*."""
    college = resolve_college_name(college)
    if not college:
        return []

    users = frappe.db.sql_list(
        """
        SELECT DISTINCT u.email
        FROM `tabUser` u
        INNER JOIN `tabHas Role` hr ON hr.parent = u.name
        INNER JOIN `tabStudent` s ON s.email_id = u.email
        WHERE u.enabled = 1
          AND s.college = %s
          AND hr.role IN ('Student', 'Student Base', 'Student Pro', 'Student lite')
        """,
        (college,),
    )

    frappe.log_error(
        title="College Notice Student Lookup",
        message=f"College: '{college}' | Found {len(users)} student users.",
    )
    return users


# ── Standalone post-commit notification dispatcher ───────────────────────────
def notify_notice_students(notice_name):
    """
    Send a Frappe system notification to all students of the college
    that issued this notice.

    Must be called *after* frappe.db.commit() so the document is fully
    visible to background workers. Switches to Administrator context
    so 'from_user' is never 'Guest'.
    """
    if not notice_name:
        return

    original_user = frappe.session.user
    frappe.set_user("Administrator")
    try:
        doc = frappe.get_doc("College Notice", notice_name)

        # Duplicate guard
        if frappe.db.exists("Notification Log", {
            "document_type": "College Notice",
            "document_name": notice_name,
        }):
            frappe.log_error(
                title="College Notice Notification (skipped)",
                message=f"Notification already sent for notice {notice_name}.",
            )
            return

        student_users = _get_college_student_users(doc.college)
        if not student_users:
            frappe.log_error(
                title="College Notice Notification",
                message=(
                    f"No matching student users found for notice {notice_name} "
                    f"(College: {doc.college})"
                ),
            )
            return

        notice_type = doc.notice_type or "Notice"
        subject = _(f"📢 New {notice_type}: {{0}}").format(doc.notice or notice_name)

        details = []
        if doc.notice:
            details.append(f"Notice: {doc.notice}")
        if doc.notice_type:
            details.append(f"Type: {doc.notice_type}")
        if doc.date:
            details.append(f"Date: {doc.date}")
        if doc.college:
            details.append(f"College: {doc.college}")

        email_content = _(
            "A new notice has been posted on your college notice board.\n\n{0}"
        ).format("\n".join(details))

        from_user = (
            doc.owner
            if (doc.owner and doc.owner != "Guest")
            else "Administrator"
        )

        notification_doc = frappe._dict({
            "type": "Alert",
            "document_type": "College Notice",
            "document_name": notice_name,
            "subject": subject,
            "from_user": from_user,
            "email_content": email_content,
        })

        try:
            enqueue_create_notification(student_users, notification_doc)
            frappe.log_error(
                title="College Notice Notification (sent)",
                message=(
                    f"Notice: {notice_name} | College: {doc.college} | "
                    f"Recipients: {len(student_users)} | Users: {student_users[:10]}"
                ),
            )
        except Exception as notify_err:
            frappe.log_error(
                title="College Notice Notification (failed)",
                message=(
                    f"Notice: {notice_name} | College: {doc.college} | "
                    f"Error: {notify_err}\n{frappe.get_traceback()}"
                ),
            )
    finally:
        frappe.set_user(original_user)


# ── API endpoints ─────────────────────────────────────────────────────────────

@frappe.whitelist(allow_guest=True)
def get_college_notice_list(college=None, page=1, page_size=DEFAULT_PAGE_SIZE):
    try:
        page, page_size, limit, offset = get_pagination_params(page, page_size)

        filters = {}
        if college:
            filters["college"] = resolve_college_name(college)

        events = frappe.get_all(
            "College Notice",
            filters=filters,
            fields=["*"],
            order_by="creation desc",
            limit_page_length=limit,
            limit_start=offset,
        )

        total = frappe.db.count("College Notice", filters=filters)

        return gen_response(
            status=200,
            message="College event list fetched successfully",
            data={
                "notice": events,
                "pagination": make_pagination_meta(total, page, page_size),
            },
        )

    except Exception as e:
        return exception_handel(e)


@frappe.whitelist(allow_guest=True)
def create_college_notice():
    try:
        data = frappe.request.get_json()

        if not data:
            return {"status": 400, "message": "Request body is required"}

        doc = frappe.get_doc({
            "doctype": "College Notice",
            "college": resolve_college_name(data.get("college")),
            "notice": data.get("notice"),
            "date": data.get("date"),
            "notice_type": data.get("notice_type"),
            "company": data.get("company"),
        })

        doc.insert(ignore_permissions=True)

        # ── Commit FIRST so document is fully visible to background workers ──
        frappe.db.commit()

        # ── Dispatch notifications as Administrator (not Guest) ──────────────
        try:
            notify_notice_students(doc.name)
        except Exception as notify_err:
            # Log but don't fail the API response
            frappe.log_error(
                title="create_college_notice: notification dispatch failed",
                message=f"Notice: {doc.name} | Error: {notify_err}\n{frappe.get_traceback()}",
            )

        return {
            "status": 200,
            "message": "College Notice created successfully",
            "data": {"name": doc.name},
        }

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Create College Notice Error")
        return {"status": 500, "message": str(e)}


@frappe.whitelist(allow_guest=True)
def update_college_notice(name):
    try:
        data = frappe.request.get_json()

        if not name:
            return {"status": 400, "message": "Document name is required"}

        doc = frappe.get_doc("College Notice", name)

        fields = ["college", "notice", "date", "notice_type", "company"]
        for field in fields:
            if field in data:
                doc.set(field, data.get(field))

        doc.save(ignore_permissions=True)

        return {"status": 200, "message": "College Notice updated successfully"}

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Update College Notice Error")
        return {"status": 500, "message": str(e)}


@frappe.whitelist(allow_guest=True)
def delete_college_notice(name):
    try:
        if not name:
            return {"status": 400, "message": "Document name is required"}

        frappe.delete_doc("College Notice", name, ignore_permissions=True)

        return {"status": 200, "message": "College Notice deleted successfully"}

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Delete College Notice Error")
        return {"status": 500, "message": str(e)}