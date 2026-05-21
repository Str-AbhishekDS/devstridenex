# Copyright (c) 2024, Your Company and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe import _
from frappe.utils import getdate, nowdate, get_time


class MentorBlockedTime(Document):

    def validate(self):
        self.validate_date_not_past()
        self.validate_time_range()
        self.check_overlap_with_existing_blocks()
        self.warn_if_booked_sessions_exist()

    def validate_date_not_past(self):
        """Block times cannot be set for past dates."""
        if getdate(self.date) < getdate(nowdate()):
            frappe.throw(_("Cannot block time for a past date ({0}).").format(self.date))

    def validate_time_range(self):
        """Ensure from_time is strictly before to_time."""
        if self.from_time and self.to_time:
            if self.from_time >= self.to_time:
                frappe.throw(_("From Time must be earlier than To Time."))
                

    def check_overlap_with_existing_blocks(self):
        """Prevent overlapping blocked-time entries for the same mentor on the same date."""
        existing = frappe.get_all(
            "Mentor Blocked Time",
            filters={
                "mentor": self.mentor,
                "date": self.date,
                "name": ["!=", self.name],
            },
            fields=["name", "from_time", "to_time"],
        )

        for block in existing:
            if _times_overlap(self.from_time, self.to_time, block.from_time, block.to_time):
                frappe.throw(
                    _(
                        "An overlapping blocked time already exists for {0} on {1} "
                        "({2} – {3})."
                    ).format(self.mentor, self.date, block.from_time, block.to_time)
                )

    def warn_if_booked_sessions_exist(self):
        """
        Issue a warning (not an error) if a booked session falls within the
        blocked window so the mentor can cancel / reschedule it manually.
        """
        booked = frappe.get_all(
            "Mentor Session Booking",
            filters={
                "mentor": self.mentor,
                "session_date": self.date,
                "status": "Scheduled",
            },
            fields=["name", "from_time", "to_time", "student"],
        )

        conflicting = [
            b for b in booked
            if _times_overlap(self.from_time, self.to_time, b.from_time, b.to_time)
        ]

        if conflicting:
            sessions = ", ".join(c.name for c in conflicting)
            frappe.msgprint(
                _(
                    "Warning: The following scheduled session(s) overlap with this blocked time "
                    "and should be rescheduled or cancelled: {0}"
                ).format(sessions),
                title=_("Conflicting Sessions"),
                indicator="orange",
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

@frappe.whitelist(allow_guest = True)
def get_blocked_times(mentor, from_date, to_date):
    """
    Return all blocked time slots for a mentor between two dates (inclusive).

    Args:
        mentor    (str): User ID of the mentor.
        from_date (str): Start date in YYYY-MM-DD.
        to_date   (str): End date in YYYY-MM-DD.

    Response shape:
        [
            {
                "name": "MBT-0001",
                "date": "2024-03-05",
                "from_time": "14:00:00",
                "to_time": "16:00:00",
                "reason": "Personal appointment"
            },
            ...
        ]
    """
    if not mentor:
        frappe.throw(_("Mentor is required."))
    if not from_date or not to_date:
        frappe.throw(_("Both from_date and to_date are required."))
    if getdate(from_date) > getdate(to_date):
        frappe.throw(_("from_date must be on or before to_date."))

    blocks = frappe.get_all(
        "Mentor Blocked Time",
        filters={
            "mentor": mentor,
            "date": ["between", [from_date, to_date]],
        },
        fields=["name", "date", "from_time", "to_time", "reason"],
        order_by="date asc, from_time asc",
    )

    return blocks

                    
@frappe.whitelist(allow_guest=True)
def block_time(mentor, date, from_time, to_time, reason=None):
    """
    Programmatically create a Mentor Blocked Time entry.
    Useful for bulk operations or external integrations.

    Returns:
        str: The name of the newly created document.
    """
    # if not frappe.has_permission("Mentor Blocked Time", "create"):
    #     frappe.throw(_("You do not have permission to block time."), frappe.PermissionError)

    doc = frappe.get_doc({
        "doctype": "Mentor Blocked Time",
        "mentor": mentor,
        "date": date,
        "from_time": from_time,
        "to_time": to_time,
        "reason": reason or "",
    })
    doc.insert(ignore_permissions=False)
    frappe.db.commit()
    return doc.name