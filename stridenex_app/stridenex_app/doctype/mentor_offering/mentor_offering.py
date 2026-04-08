# Copyright (c) 2026, QTPL and contributors
# For license information, please see license.txt

# mentor_offering/doctype/mentor_offering/mentor_offering.py

import frappe
from frappe.model.document import Document

class MentorOffering(Document):

    def autoname(self):
        from frappe.model.naming import make_autoname
        self.name = make_autoname("MO-.YYYY.-.#####")

    def validate(self):
        self.validate_pricing()
        self.validate_type_fields()

    def validate_pricing(self):
        if self.price_per_session <= 0:
            frappe.throw("Price per session must be greater than zero.")

    def validate_type_fields(self):
        if self.offering_type == "Group Session" and not self.max_group_size:
            frappe.throw("Max Group Size is required for Group Sessions.")
        if self.offering_type == "Async Review" and not self.turnaround_hours:
            frappe.throw("Turnaround Hours is required for Async Review.")

    def on_update(self):
        self.update_aggregates()

    def update_aggregates(self):
        """Recalculate total bookings and average rating from bookings."""
        result = frappe.db.sql("""
            SELECT COUNT(*) as total, AVG(rating) as avg_rating
            FROM `tabMentor Offering Booking`
            WHERE offering = %s AND status = 'Completed'
        """, self.name, as_dict=True)

        if result:
            self.db_set("total_bookings", result[0].total or 0)
            self.db_set("average_rating", round(result[0].avg_rating or 0, 1))


@frappe.whitelist()
def get_mentor_offerings(mentor, status=None):
    filters = {"mentor": mentor}
    if status:
        filters["status"] = status
    return frappe.get_all(
        "Mentor Offering",
        filters=filters,
        fields=[
            "name", "title", "offering_type", "category",
            "duration_minutes", "price_per_session", "status",
            "total_bookings", "average_rating"
        ],
        order_by="creation desc"
    )


@frappe.whitelist()
def toggle_offering_status(offering_name, action):
    """action: pause | activate | archive"""
    doc = frappe.get_doc("Mentor Offering", offering_name)
    status_map = {
        "pause": "Paused",
        "activate": "Live",
        "archive": "Archived"
    }
    if action not in status_map:
        frappe.throw("Invalid action.")
    doc.status = status_map[action]
    doc.save(ignore_permissions=True)
    return {"status": doc.status}	