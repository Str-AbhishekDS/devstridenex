# Copyright (c) 2026, QTPL and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import get_url, format_date, getdate, today
from frappe.desk.doctype.notification_log.notification_log import make_notification_logs, enqueue_create_notification
from stridenex_app.api_stridenex_app.app_utils import (
    gen_response,
    exception_handel, get_pagination_params, make_cache_key, make_pagination_meta
)


def resolve_college_name(college):
    """Resolve a college email to its document name if needed."""
    if not college:
        return college
    if "@" in college:
        resolved = frappe.db.get_value("College", {"email": college}, "name")
        if resolved:
            return resolved
    return college


class CollegeEvent(Document):

    def autoname(self):
        if self.event and self.start_date:
            start_date = getdate(self.start_date)
            base_name = f"{self.event}-{start_date.strftime('%b %d %Y')}"

            if frappe.db.exists("College Event", base_name):
                count = 1
                while frappe.db.exists(
                    "College Event",
                    f"{base_name}-{count}"
                ):
                    count += 1
                self.name = f"{base_name}-{count}"
            else:
                self.name = base_name

    def after_insert(self):
        """
        Triggered when college SAVES (creates) a new event.
        Enqueues bulk notification so the save returns instantly.
        """
        if not frappe.flags.in_test:
            frappe.enqueue(
                method="stridenex_app.stridenex_app.doctype.college_event.college_event.notify_students_background",
                queue="long",
                timeout=1800,
                event_name=self.name,
                enqueue_after_commit=True,
            )

    def notify_students(self):
        """Send Frappe system notifications to all matching students for this event."""
        # Prevent duplicate notifications for the same event
        if frappe.db.exists("Notification Log", {
            "document_type": self.doctype,
            "document_name": self.name
        }):
            frappe.log_error(
                title="College Event Notification (skipped)",
                message=f"Notification already sent for event {self.name}. Skipping duplicate."
            )
            return

        student_users = self.get_matching_student_users()
        if not student_users:
            frappe.log_error(
                title="College Event Notification",
                message=f"No matching student users found for event {self.name} (Scope: {self.participation_scope}, College: {self.college})"
            )
            return

        subject = _("New {0}: {1}").format(self.event_type or "Event", self.event)
        from_user = self.owner if (self.owner and self.owner != "Guest") else "Administrator"

        notification_doc = frappe._dict({
            "type": "Alert",
            "document_type": self.doctype,
            "document_name": self.name,
            "subject": subject,
            "from_user": from_user,
            "email_content": _("Starts on: {0}").format(
                format_date(self.start_date) if self.start_date else "N/A"
            ),
        })

        try:
            enqueue_create_notification(student_users, notification_doc)
            frappe.log_error(
                title="College Event Notification (sent)",
                message=(
                    f"Event: {self.name} | College: {self.college} | "
                    f"Recipients: {len(student_users)} | Users: {student_users[:10]}"
                )
            )
        except Exception as notify_err:
            frappe.log_error(
                title="College Event Notification (failed)",
                message=(
                    f"Event: {self.name} | College: {self.college} | "
                    f"Error: {notify_err}\n{frappe.get_traceback()}"
                )
            )

    def get_matching_student_users(self):
        """Fetch emails of enabled student users belonging to this college/scope."""
        college = resolve_college_name(self.college)
        if not college:
            return []

        if self.participation_scope == "Inter College":
            # Get university of the event's college
            university = frappe.db.get_value("College", college, "university")
            if not university:
                return []

            # Get all colleges under the same university
            colleges = frappe.get_all(
                "College",
                filters={"university": university},
                pluck="name"
            )
            if not colleges:
                return []

            # Get streams of the event's college
            streams = frappe.get_all(
                "College Courses Table",
                filters={"parent": college},
                pluck="stream"
            )
            if not streams:
                return []

            return frappe.db.sql_list(
                """
                SELECT DISTINCT u.email
                FROM `tabUser` u
                INNER JOIN `tabHas Role` hr ON hr.parent = u.name
                INNER JOIN `tabStudent` s ON s.email_id = u.email
                WHERE u.enabled = 1
                  AND s.college IN %s
                  AND s.stream IN %s
                  AND hr.role IN ('Student', 'Student Base', 'Student Pro', 'Student lite')
                """,
                (tuple(colleges), tuple(streams)),
            )
        else:
            # Intra College — all students of the same college
            return frappe.db.sql_list(
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

    def get_matching_students(self):
        """
        Fetch students based on participation scope:
          - Intra College: all students of the same college.
          - Inter College: students of all colleges under the same university who have the same stream.
        Keep for backward compatibility.
        """
        college = resolve_college_name(self.college)
        if self.participation_scope == "Inter College":
            # 1. Get university of the event's college
            university = frappe.db.get_value("College", college, "university")
            if not university:
                return []

            # 2. Get all colleges under the same university
            colleges = frappe.get_all(
                "College",
                filters={"university": university},
                pluck="name"
            )
            if not colleges:
                return []

            # 3. Get streams of the event's college
            streams = frappe.get_all(
                "College Courses Table",
                filters={"parent": college},
                pluck="stream"
            )
            if not streams:
                return []

            # 4. Filter students of those colleges with those streams
            filters = {
                "college": ["in", colleges],
                "stream": ["in", streams]
            }
        else:
            # Intra College — all students of the same college
            filters = {"college": college}

        return frappe.get_all(
            "Student",
            filters=filters,
            fields=["name", "first_name", "email_id", "stream"],
        )

    def send_event_notification(self, student_user):
        """Keep for backward compatibility."""
        notification_doc = frappe._dict({
            "type": "Alert",
            "document_type": self.doctype,
            "document_name": self.name,
            "subject": _("New {0}: {1}").format(self.event_type or "Event", self.event),
            "from_user": frappe.session.user or "Administrator",
            "email_content": _("Starts on: {0}").format(
                format_date(self.start_date) if self.start_date else "N/A"
            ),
        })
        # Direct DB insert for in-app alerts
        make_notification_logs(notification_doc, [student_user])


def notify_students_background(event_name):
    """
    Background job called by frappe.enqueue from CollegeEvent.after_insert.
    Sends email + in-app notification to every matching student.
    """
    import time
    # Force a database rollback to discard any cached transaction states and start a fresh transaction
    frappe.db.rollback()

    doc = None
    # Retry loop with rollback to safely handle database transaction synchronization or replica lag
    for attempt in range(5):
        try:
            doc = frappe.get_doc("College Event", event_name)
            break
        except frappe.DoesNotExistError:
            if attempt < 4:
                time.sleep(0.5)
                frappe.db.rollback()
            else:
                raise

    try:
        # Switch to Administrator context so 'from_user' is never 'Guest'
        original_user = frappe.session.user
        frappe.set_user("Administrator")
        try:
            doc.notify_students()
            frappe.db.commit()
        finally:
            frappe.set_user(original_user)
    except Exception:
        frappe.db.rollback()
        frappe.log_error(
            title=f"College Event Bulk Notification Failed: {event_name}",
            message=frappe.get_traceback(),
        )


DEFAULT_PAGE_SIZE = 20

@frappe.whitelist(allow_guest=True)
def get_college_event_list(college=None, student=None, page=1, page_size=DEFAULT_PAGE_SIZE, filter="upcoming"):
    """
    Fetch college events with optional date-based filtering.
    """
    try:
        page, page_size, limit, offset = get_pagination_params(page, page_size)

        if college:
            college = resolve_college_name(college)

        # ── Base scope filter (Intra-College OR matching college) ──────────────
        scope_filters = [
            [
                "College Event",
                "participation_scope",
                "=",
                "Intra College"
            ],
            "or",
            [
                "College Event",
                "college",
                "=",
                college
            ]
        ]

        # ── Date filter ────────────────────────────────────────────────────────
        today_date = today()  # returns "YYYY-MM-DD" string

        if filter == "upcoming":
            # Show events that have not yet ended (end_date >= today)
            date_filters = [
                ["College Event", "end_date", ">=", today_date]
            ]
        elif filter == "past":
            # Show only events that have already ended (end_date < today)
            date_filters = [
                ["College Event", "end_date", "<", today_date]
            ]
        else:
            # filter == "all" — no date restriction
            date_filters = []

        # Combine scope + date filters
        combined_filters = scope_filters + (["and"] + date_filters if date_filters else [])

        # ── Determine sort order ───────────────────────────────────────────────
        if filter == "past":
            order_by = "end_date desc"   # most recently ended first
        else:
            order_by = "start_date asc"  # soonest upcoming first

        # ── Fetch paginated events ─────────────────────────────────────────────
        events = frappe.get_all(
            "College Event",
            filters=combined_filters,
            fields=["*"],
            order_by=order_by,
            limit_page_length=limit,
            limit_start=offset
        )

        total = frappe.db.count("College Event", filters=combined_filters)

        # ── Registration status lookup ─────────────────────────────────────────
        registration_map = {}

        if student:
            registrations = frappe.get_all(
                "Student Event Registeration",
                filters={"student": student},
                fields=["event", "status"]
            )
            registration_map = {
                r["event"]: r["status"]
                for r in registrations
            }

        # Attach registration status to every event
        for event in events:
            event["registration_status"] = (
                registration_map.get(event["name"], "Not Registered")
                if student
                else "Not Registered"
            )

        return gen_response(
            status=200,
            message="College event list fetched successfully",
            data={
                "events": events,
                "filter": filter,
                "pagination": make_pagination_meta(
                    total,
                    page,
                    page_size
                )
            }
        )

    except Exception as e:
        return exception_handel(e)
    

@frappe.whitelist(allow_guest=True)
def create_college_event():
    try:
        data = frappe.request.get_json()

        if not data:
            return {"status": 400, "message": "Request body is required"}

        doc = frappe.get_doc({
            "doctype": "College Event",
            "event": data.get("event"),
            "college": resolve_college_name(data.get("college")),
            "start_date": data.get("start_date"),
            "end_date": data.get("end_date"),
            "price": data.get("price"),
            "event_type": data.get("event_type"),
            "participation_scope":data.get("participation_scope")
        })

        doc.insert(ignore_permissions=True)
        frappe.db.commit()

        return {
            "status": 200,
            "message": "College Event created successfully",
            "data": doc.name
        }

    except Exception as e:
        return {"status": 500, "message": str(e)}

@frappe.whitelist(allow_guest=True)
def update_college_event(name):
    try:
        data = frappe.request.get_json()

        if not data:
            return {"status": 400, "message": "No data provided"}

        doc = frappe.get_doc("College Event", name)
       

        doc.update(data)
        if "college" in data:
            doc.college = resolve_college_name(data.get("college"))

        doc.save(ignore_permissions=True)
        frappe.db.commit()

        return {
            "status": 200,
            "message": "College Event updated successfully",
            "data": doc.as_dict()
        }

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Update College Event Error")
        return {
            "status": 500,
            "message": str(e)
        }

@frappe.whitelist(allow_guest=True)
def delete_college_event(name):
    try:
        if not name:
            return {"status": 400, "message": "Document name is required"}

        frappe.delete_doc("College Event", name, ignore_permissions=True)

        return {
            "status": 200,
            "message": "College Event deleted successfully"
        }

    except Exception as e:
        return {"status": 500, "message": str(e)}