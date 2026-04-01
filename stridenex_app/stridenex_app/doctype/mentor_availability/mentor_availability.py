# Copyright (c) 2024, Your Company and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe import _
from frappe.utils import get_time


class MentorAvailability(Document):

    def validate(self):
        self.validate_time_range()
        self.check_duplicate_slot()

    def validate_time_range(self):
        """Ensure from_time is strictly before to_time."""
        if self.from_time and self.to_time:
            if self.from_time >= self.to_time:
                frappe.throw(_("From Time must be earlier than To Time."))

    def check_duplicate_slot(self):
        """
        Prevent overlapping availability slots for the same mentor on the same day.
        Only checks against other active (is_available = 1) slots.
        """
        existing = frappe.get_all(
            "Mentor Availability",
            filters={
                "mentor": self.mentor,
                "day": self.day,
                "is_available": 1,
                "name": ["!=", self.name],
            },
            fields=["name", "from_time", "to_time"],
        )

        for slot in existing:
            if _times_overlap(self.from_time, self.to_time, slot.from_time, slot.to_time):
                frappe.throw(
                    _(
                        "An overlapping availability slot already exists for {0} on {1} "
                        "({2} – {3}). Please adjust your time range."
                    ).format(self.mentor, self.day, slot.from_time, slot.to_time)
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

@frappe.whitelist()
def get_mentor_weekly_availability(mentor):
    """
    Return the full weekly availability grid for a mentor, grouped by day.

    Usage (JS):
        frappe.call({
            method: "your_app.doctype.mentor_availability.mentor_availability.get_mentor_weekly_availability",
            args: { mentor: "user@example.com" },
            callback(r) { console.log(r.message); }
        });

    Response shape:
        {
            "Monday":    [{ "name": "MA-0001", "from_time": "10:00:00", "to_time": "11:00:00" }, ...],
            "Tuesday":   [...],
            ...
            "Sunday":    []
        }
    """
    if not mentor:
        frappe.throw(_("Mentor is required."))

    slots = frappe.get_all(
        "Mentor Availability",
        filters={"mentor": mentor, "is_available": 1},
        fields=["name", "day", "from_time", "to_time"],
        order_by="from_time asc",
    )

    days_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    availability = {day: [] for day in days_order}

    for slot in slots:
        availability[slot.day].append({
            "name": slot.name,
            "from_time": str(slot.from_time),
            "to_time": str(slot.to_time),
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
    weekly_slots = frappe.get_all(
        "Mentor Availability",
        filters={"mentor": mentor, "day": day_name, "is_available": 1},
        fields=["from_time", "to_time"],
        order_by="from_time asc",
    )

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