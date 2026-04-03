# Copyright (c) 2026, QTPL and contributors
# For license information, please see license.txt

# mentor_offering/doctype/mentor_offering_booking/mentor_offering_booking.py

import frappe
from frappe.model.document import Document

class MentorOfferingBooking(Document):

    def autoname(self):
        from frappe.model.naming import make_autoname
        self.name = make_autoname("MOB-.YYYY.-.#####")

    def validate(self):
        self.fetch_mentor_from_offering()

    def fetch_mentor_from_offering(self):
        if self.offering and not self.mentor:
            self.mentor = frappe.db.get_value("Mentor Offering", self.offering, "mentor")

    def on_submit(self):
        self.update_offering_aggregates()

    def on_cancel(self):
        self.update_offering_aggregates()

    def update_offering_aggregates(self):
        offering = frappe.get_doc("Mentor Offering", self.offering)
        offering.update_aggregates()


@frappe.whitelist()
def submit_review(booking_name, rating, review_text):
    if not booking_name:
        frappe.throw("Booking name is required")

    # Validate booking exists
    if not frappe.db.exists("Mentor Offering Booking", booking_name):
        frappe.throw("Invalid Booking")

    # Get booking status
    booking = frappe.db.get_value(
        "Mentor Offering Booking",
        booking_name,
        ["status", "docstatus", "offering"],
        as_dict=True
    )

    if booking.docstatus != 1:
        frappe.throw("Booking must be submitted")

    if booking.status != "Completed":
        frappe.throw("Only completed sessions can be reviewed")

    # ✅ Update directly (NO doc.save)
    frappe.db.set_value("Mentor Offering Booking", booking_name, {
        "rating": float(rating),
        "review": review_text
    })

    # 🔥 Update aggregates
    offering = frappe.get_doc("Mentor Offering", booking.offering)
    offering.update_aggregates()

    return {"success": True}

@frappe.whitelist()
def update_status(booking_name, status):
    doc = frappe.get_doc("Mentor Offering Booking", booking_name)

    if doc.docstatus != 1:
        frappe.throw("Only submitted bookings can be updated.")

    if status not in ["Completed", "Cancelled"]:
        frappe.throw("Invalid status")

    doc.db_set("status", status)

    # 🔥 Update aggregates
    offering = frappe.get_doc("Mentor Offering", doc.offering)
    offering.update_aggregates()

    return {"success": True}