# Copyright (c) 2026, QTPL and contributors
# For license information, please see license.txt
#
# PATH: mentor_offering/doctype/mentor_request/mentor_request.py
#
# PURPOSE:
#   Created when a student browses Mentor Offerings and clicks "Book".
#   Mentor sees these on the Requests tab and can:
#     Accept  → creates Mentor Session Booking automatically
#     Decline → request closed
#     Suggest Alt Time → student sees new proposed slot

import frappe
from frappe.model.document import Document
from frappe import _
from frappe.utils import getdate, nowdate, date_diff


class MentorRequest(Document):

    def before_insert(self):
        self.auto_set_priority()
        self.fetch_session_type_from_offering()

    def validate(self):
        self.validate_not_self_request()
        self.validate_date_not_past()
        self.auto_set_priority()

    # ── Helpers ─────────────────────────────────────────────────────────────

    def validate_not_self_request(self):
        if self.student == self.mentor:
            frappe.throw(_("Student and Mentor cannot be the same user."))

    def validate_date_not_past(self):
        if self.requested_date and getdate(self.requested_date) < getdate(nowdate()):
            frappe.throw(_("Preferred date cannot be in the past."))

    def auto_set_priority(self):
        """
        Auto-calculate priority based on how soon the requested date is:
          High   = within 7 days  (urgent)
          Medium = 8–14 days
          Low    = 15+ days
        """
        if not self.requested_date:
            return
        days = date_diff(self.requested_date, nowdate())
        if days <= 7:
            self.priority = "High"
        elif days <= 14:
            self.priority = "Medium"
        else:
            self.priority = "Low"

    def fetch_session_type_from_offering(self):
        """Auto-fill session_type from the offering's category."""
        if self.offering and not self.session_type:
            cat = frappe.db.get_value("Mentor Offering", self.offering, "category")
            if cat:
                self.session_type = cat


# ─────────────────────────────────────────────────────────────────────────────
# API — called from Mentor Workspace Requests tab JS
# ─────────────────────────────────────────────────────────────────────────────

@frappe.whitelist()
def get_pending_requests(mentor):
    """
    Return all Pending requests for a mentor.
    Ordered: High priority first, then soonest date first.
    """
    rows = frappe.get_all(
        "Mentor Request",
        filters={"mentor": mentor, "status": "Pending"},
        fields=[
            "name", "student", "offering", "topic",
            "requested_date", "requested_time", "session_type",
            "priority", "student_message"
        ],
        order_by="FIELD(priority,'High','Medium','Low'), requested_date asc"
    )
    for r in rows:
        r["student_name"] = frappe.db.get_value("User", r.student, "full_name") or r.student
        r["offering_title"] = frappe.db.get_value("Mentor Offering", r.offering, "title") or r.offering
    return rows


@frappe.whitelist()
def get_request_counts(mentor):
    """
    Header card counts for the Requests tab.
    Returns: pending count, skill_verif pending count, approved this month.
    """
    pending = frappe.db.count("Mentor Request", {"mentor": mentor, "status": "Pending"})

    svr_pending = frappe.db.count(
        "Skill Verification Request", {"mentor": mentor, "status": "Pending"}
    )

    approved = frappe.db.sql("""
        SELECT COUNT(*) FROM `tabMentor Request`
        WHERE mentor = %s
          AND status = 'Accepted'
          AND MONTH(modified) = MONTH(CURDATE())
          AND YEAR(modified)  = YEAR(CURDATE())
    """, mentor)[0][0]

    return {
        "pending": pending,
        "svr_pending": svr_pending,
        "approved_this_month": int(approved),
    }


@frappe.whitelist()
def accept_request(request_name, from_time, to_time):
    """
    Accept a Mentor Request:
      1. Validate request is still Pending
      2. Create Mentor Session Booking (pulls date/mentor/student/offering from request)
      3. Set request status = Accepted, link back the booking
    """
    req = frappe.get_doc("Mentor Request", request_name)

    if req.status != "Pending":
        frappe.throw(_("Only Pending requests can be accepted."))

    # Fetch fee from offering
    fee = frappe.db.get_value("Mentor Offering", req.offering, "price_per_session") or 0

    booking = frappe.get_doc({
        "doctype": "Mentor Session Booking",
        "mentor": req.mentor,
        "student": req.student,
        "offering": req.offering,
        "mentor_request": req.name,
        "topic": req.topic,
        "session_date": req.requested_date,
        "from_time": from_time,
        "to_time": to_time,
        "meeting_type": req.session_type or "Career",
        "fee": fee,
        "status": "Scheduled",
    })
    booking.insert(ignore_permissions=True)

    req.status = "Accepted"
    req.session_booking = booking.name
    req.save(ignore_permissions=True)
    frappe.db.commit()

    return {"booking_name": booking.name}


@frappe.whitelist()
def decline_request(request_name, notes=None):
    """Decline a pending request."""
    req = frappe.get_doc("Mentor Request", request_name)
    if req.status != "Pending":
        frappe.throw(_("Only Pending requests can be declined."))

    req.status = "Declined"
    if notes:
        req.notes = notes
    req.save(ignore_permissions=True)
    frappe.db.commit()
    return {"status": "Declined"}


@frappe.whitelist()
def suggest_alt_time(request_name, alt_date, alt_time, notes=None):
    """Suggest a different date/time to the student."""
    req = frappe.get_doc("Mentor Request", request_name)
    if req.status != "Pending":
        frappe.throw(_("Only Pending requests can have an alt time suggested."))

    req.status = "Suggested Alt Time"
    req.alt_date = alt_date
    req.alt_time = alt_time
    if notes:
        req.notes = notes
    req.save(ignore_permissions=True)
    frappe.db.commit()
    return {"status": "Suggested Alt Time"}