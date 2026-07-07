# Copyright (c) 2024, Your Company and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe import _
from frappe.utils import get_time


class MentorAvailability(Document):

    def validate(self):

        if self.schedule_type == "Each Day Same Schedule":
            if not self.from_time or not self.to_time:
                frappe.throw("From Time and To Time are required for Same schedule")

            if not self.days_multi:
                frappe.throw("Please select at least one day")

            self.validate_time_range()
            self.process_same_schedule()

        else:
            if not self.daily_schedule:
                frappe.throw("Please add at least one row in Daily Schedule")

            for row in self.daily_schedule:
                if not row.day or not row.from_time or not row.to_time:
                    frappe.throw("Each row must have Day, From Time and To Time")

                if row.from_time >= row.to_time:
                    frappe.throw(f"Invalid time range in {row.day}")

        self.check_duplicate_slot()

    def validate_time_range(self):
        """Ensure from_time is strictly before to_time."""
        if self.from_time and self.to_time:
            if self.from_time >= self.to_time:
                frappe.throw(_("From Time must be earlier than To Time."))

    
    def process_same_schedule(self):
        if not self.days_multi:
            frappe.throw("Please select at least one day")

        # Delete old generated rows
        frappe.db.delete("Mentor Availability Slot Child", {"parent": self.name})

        for d in self.days_multi:
            self.append("daily_schedule", {
                "day": d.day,
                "from_time": self.from_time,
                "to_time": self.to_time
            })
    

    def check_duplicate_slot(self):

        for row in self.daily_schedule:

            existing = frappe.get_all(
                "Mentor Availability",
                filters={
                    "mentor": self.mentor,
                    "is_available": 1,
                    "name": ["!=", self.name],
                },
                fields=["name"]
            )

            for doc in existing:
                other_doc = frappe.get_doc("Mentor Availability", doc.name)

                for other_row in other_doc.daily_schedule:
                    if row.day == other_row.day and _times_overlap(
                        row.from_time, row.to_time,
                        other_row.from_time, other_row.to_time
                    ):
                        frappe.throw(
                            f"Overlapping slot for {row.day} ({row.from_time}-{row.to_time})"
                        )

# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _times_overlap(start1, end1, start2, end2):
    start1 = get_time(start1)
    end1 = get_time(end1)
    start2 = get_time(start2)
    end2 = get_time(end2)

    return start1 < end2 and start2 < end1

# ------------------------------------------------------------------
# Whitelisted API Methods
# ------------------------------------------------------------------
@frappe.whitelist(allow_guest=False)
def get_mentor_weekly_availability(mentor):

    # ----------------------------------------------------------
    # PERMISSION CHECK
    # Respects Role Permission Manager configuration
    # ----------------------------------------------------------
    session_user = frappe.session.user

    if not frappe.has_permission(
        "Mentor Availability",
        ptype="read",
        user=session_user
    ):
        frappe.throw(
            "You do not have permission to access Mentor Availability.",
            frappe.PermissionError
        )

    docs = frappe.get_all(
        "Mentor Availability",
        filters={
            "mentor": mentor,
            "is_available": 1
        },
        fields=["name"]
    )

    availability = {
        day: []
        for day in [
            "Monday",
            "Tuesday",
            "Wednesday",
            "Thursday",
            "Friday",
            "Saturday",
            "Sunday"
        ]
    }

    for d in docs:

        doc = frappe.get_doc(
            "Mentor Availability",
            d.name
        )

        for row in doc.daily_schedule:

            availability[row.day].append({
                "from_time": str(row.from_time),
                "to_time": str(row.to_time)
            })

    return availability


@frappe.whitelist(allow_guest=False)
def save_mentor_availability(name=None, **kwargs):

    session_user = frappe.session.user

    # ---------------------------------------------------------
    # UPDATE
    # ---------------------------------------------------------
    if name:

        if not frappe.has_permission(
            "Mentor Availability",
            ptype="write",
            user=session_user
        ):
            frappe.throw(
                "You do not have permission to update Mentor Availability.",
                frappe.PermissionError
            )

        doc = frappe.get_doc(
            "Mentor Availability",
            name
        )

        doc.update(kwargs)

        # Respects Role Permission Manager
        doc.save()

        message = "Mentor Availability Updated Successfully"

    # ---------------------------------------------------------
    # CREATE
    # ---------------------------------------------------------
    else:

        if not frappe.has_permission(
            "Mentor Availability",
            ptype="create",
            user=session_user
        ):
            frappe.throw(
                "You do not have permission to create Mentor Availability.",
                frappe.PermissionError
            )

        doc = frappe.get_doc({
            "doctype": "Mentor Availability",
            **kwargs
        })

        # Respects Role Permission Manager
        doc.insert()

        message = "Mentor Availability Created Successfully"

    frappe.db.commit()

    return {
        "status": "success",
        "message": message,
        "name": doc.name
    }


@frappe.whitelist(allow_guest=False)
def delete_mentor_availability(mentor):

    # ----------------------------------------------------------
    # PERMISSION CHECK
    # Respects Role Permission Manager configuration
    # ----------------------------------------------------------
    session_user = frappe.session.user

    if not frappe.has_permission(
        "Mentor Availability",
        ptype="delete",
        user=session_user
    ):
        frappe.throw(
            "You do not have permission to delete Mentor Availability.",
            frappe.PermissionError
        )

    docs = frappe.get_all(
        "Mentor Availability",
        filters={"mentor": mentor},
        pluck="name"
    )

    for doc_name in docs:

        frappe.delete_doc(
            "Mentor Availability",
            doc_name
        )

    frappe.db.commit()

    return {
        "status": "success",
        "message": "All Mentor Availability Deleted Successfully"
    }