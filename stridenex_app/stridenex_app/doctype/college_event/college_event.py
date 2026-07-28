# Copyright (c) 2026, QTPL and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from stridenex_app.api_stridenex_app.app_utils import (
    gen_response,
    exception_handel,get_pagination_params,make_cache_key,make_pagination_meta
)


import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import get_url, format_date, getdate
from frappe.desk.doctype.notification_log.notification_log import enqueue_create_notification


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

    def on_submit(self):
        self.notify_students()

    def notify_students(self):
        students = self.get_matching_students()
        if not students:
            frappe.log_error(
                title="College Event Notification",
                message=f"No matching students found for event {self.name} (Scope: {self.participation_scope}, College: {self.college})"
            )
            return

        for student in students:
            self.send_event_email(student)
            if student.get("user"):
                self.send_event_notification(student.get("user"))

    def get_matching_students(self):
        """Fetch students based on participation scope - Intra (same college) or Inter (same university)."""
        if self.participation_scope == "Inter College":
            colleges = self.get_colleges_under_same_university()
        else:
            colleges = [self.college]

        filters = {"college": ["in", colleges]}

        return frappe.get_all(
            "Student",
            filters=filters,
            fields=["name", "first_name", "email_id"],
        )

    def get_colleges_under_same_university(self):
        """Return all colleges sharing the same university as this event's college."""
        university = frappe.db.get_value("College", self.college, "university")
        if not university:
            return [self.college]

        return frappe.get_all(
            "College",
            filters={"university": university},
            pluck="name",
        )

    def send_event_email(self, student):
        if not student.get("email_id"):
            frappe.log_error(
                title="College Event Mail",
                message=f"No email found for student {student.get('name')} (Event: {self.name})"
            )
            return

        record_url = get_url(f"/app/college-event/{self.name}")

        subject = _("New {0}: {1}").format(self.event_type or "Event", self.event)

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
                                        🎉 New {self.event_type or 'Event'} Announced
                                    </h1>
                                    <p style="margin:8px 0 0;color:#dbeafe;font-size:14px;">
                                        {self.participation_scope or 'Intra College'} Participation
                                    </p>
                                </td>
                            </tr>

                            <!-- Body -->
                            <tr>
                                <td style="padding:32px;">

                                    <p style="margin:0 0 20px;color:#1E293B;font-size:16px;line-height:1.8;">
                                        Dear <strong>{student.get('first_name') or 'Student'}</strong>,
                                    </p>

                                    <p style="margin:0 0 24px;color:#1E293B;font-size:15px;line-height:1.8;">
                                        A new {self.event_type or 'event'} has been announced. Check the details below and register before it starts.
                                    </p>

                                    <!-- Event Highlight -->
                                    <div style="background:#eef2ff;border-left:4px solid #0f0fbd;padding:18px;border-radius:8px;margin-bottom:24px;">
                                        <p style="margin:0;color:#1E293B;font-size:15px;line-height:1.8;">
                                            <strong>🎯 Event:</strong> {self.event}<br>
                                            <strong>🏷️ Type:</strong> {self.event_type}<br>
                                            <strong>🌐 Scope:</strong> {self.participation_scope or 'Intra College'}
                                        </p>
                                    </div>

                                    <!-- Details -->
                                    <div style="background:#f8fafc;border:1px solid #e2e8f0;padding:18px;border-radius:8px;margin-bottom:24px;">
                                        <h3 style="margin:0 0 12px;color:#0f0fbd;font-size:16px;">
                                            Event Details
                                        </h3>

                                        <p style="margin:0;color:#1E293B;font-size:14px;line-height:1.9;">
                                            <strong>📅 Start Date:</strong> {format_date(self.start_date) if self.start_date else 'N/A'}<br>
                                            <strong>📅 End Date:</strong> {format_date(self.end_date) if self.end_date else 'N/A'}<br>
                                            <strong>💰 Price:</strong> {self.price or 'Free'}
                                        </p>
                                    </div>

                                    <!-- CTA -->
                                    <div style="text-align:center;margin:30px 0;">
                                        <a href="{record_url}"
                                        style="background:#ff6b00;color:#ffffff;text-decoration:none;
                                                padding:14px 30px;border-radius:8px;
                                                font-size:15px;font-weight:600;display:inline-block;">
                                            View Event Details →
                                        </a>
                                    </div>

                                    <!-- Note -->
                                    <div style="background:#fff7ed;border-left:4px solid #ff6b00;padding:16px 18px;border-radius:8px;">
                                        <p style="margin:0;color:#9a3412;font-size:14px;line-height:1.8;">
                                            Don't miss this opportunity. Register early to secure your spot.
                                        </p>
                                    </div>

                                </td>
                            </tr>

                            <!-- Footer -->
                            <tr>
                                <td style="background:#0F172A;padding:24px;text-align:center;">
                                    <p style="margin:0;color:#ffffff;font-size:15px;font-weight:600;">
                                        StrideNex Events Team
                                    </p>

                                    <p style="margin:10px 0 0;color:#94a3b8;font-size:13px;">
                                        Bringing Opportunities Closer to You
                                    </p>

                                    <div style="margin-top:16px;padding-top:16px;border-top:1px solid #334155;">
                                        <p style="margin:0;color:#94a3b8;font-size:12px;">
                                            This notification was sent automatically by StrideNex.
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
            recipients=[student["email_id"]],
            subject=subject,
            message=message,
            reference_doctype=self.doctype,
            reference_name=self.name,
        )

    def send_event_notification(self, student_user):
        notification_doc = frappe._dict({
            "type": "Alert",
            "document_type": self.doctype,
            "document_name": self.name,
            "subject": _("New {0}: {1}").format(self.event_type or "Event", self.event),
            "from_user": frappe.session.user,
            "email_content": _("Starts on: {0}").format(
                format_date(self.start_date) if self.start_date else "N/A"
            ),
        })
        enqueue_create_notification([student_user], notification_doc)

DEFAULT_PAGE_SIZE = 20

@frappe.whitelist(allow_guest=True)
def get_college_event_list(college=None, student=None, page=1, page_size=DEFAULT_PAGE_SIZE):
    try:
        page, page_size, limit, offset = get_pagination_params(page, page_size)

        filters = {}

        # Optional filter
        if college:
            filters["college"] = college

        # Get paginated events
        events = frappe.get_all(
            "College Event",
            filters=[
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
            ],
            fields=["*"],
            order_by="creation desc",
            limit_page_length=limit,
            limit_start=offset
        )

        total = frappe.db.count("College Event", filters=[
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
            ],)

        # Get registration status (if student provided)
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

        # Attach registration status
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
            "college": data.get("college"),
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