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

def get_mentor_weekly_availability(mentor):

    docs = frappe.get_all(
        "Mentor Availability",
        filters={"mentor": mentor, "is_available": 1},
        fields=["name"]
    )

    availability = {day: [] for day in ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"]}

    for d in docs:
        doc = frappe.get_doc("Mentor Availability", d.name)

        for row in doc.daily_schedule:
            availability[row.day].append({
                "from_time": str(row.from_time),
                "to_time": str(row.to_time)
            })

    return availability


@frappe.whitelist()
def get_available_slots_for_date(mentor, date):
    """
    Return all availability slots for a mentor on a given date, annotated with
    booking and block status. The front-end uses this to render the availability grid.

    Args:
        mentor (str): User ID of the mentor.
        date   (str): ISO date string, e.g. "2024-03-01".

    Response shape:
        [
            {
                "from_time": "10:00:00",
                "to_time":   "11:00:00",
                "is_blocked": false,
                "is_booked":  true,
                "available":  false
            },
            ...
        ]
    """
    if not mentor or not date:
        frappe.throw(_("Both Mentor and Date are required."))

    date_obj = frappe.utils.getdate(date)
    day_name = date_obj.strftime("%A")   # "Monday", "Tuesday", …

    # Weekly availability for the resolved weekday
    weekly_slots = []

    docs = frappe.get_all(
        "Mentor Availability",
        filters={"mentor": mentor, "is_available": 1},
        fields=["name"]
    )

    for d in docs:
        doc = frappe.get_doc("Mentor Availability", d.name)

        for row in doc.daily_schedule:
            if row.day == day_name:
                weekly_slots.append(row)


    # Blocked times on this specific date
    blocked_slots = frappe.get_all(
        "Mentor Blocked Time",
        filters={"mentor": mentor, "date": date},
        fields=["from_time", "to_time"],
    )

    # Active bookings on this specific date
    booked_slots = frappe.get_all(
        "Mentor Session Booking",
        filters={
            "mentor": mentor,
            "session_date": date,
            "status": ["in", ["Scheduled", "Completed"]],
        },
        fields=["from_time", "to_time"],
    )

    result = []
    for slot in weekly_slots:
        is_blocked = any(
            _times_overlap(slot.from_time, slot.to_time, b.from_time, b.to_time)
            for b in blocked_slots
        )
        is_booked = any(
            _times_overlap(slot.from_time, slot.to_time, bk.from_time, bk.to_time)
            for bk in booked_slots
        )
        result.append({
            "from_time": str(slot.from_time),
            "to_time": str(slot.to_time),
            "is_blocked": is_blocked,
            "is_booked": is_booked,
            "available": not is_blocked and not is_booked,
        })

    return result