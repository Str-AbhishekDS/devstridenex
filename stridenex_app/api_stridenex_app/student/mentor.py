import frappe

@frappe.whitelist()
def get_booked_sessions(student_email=None):
    if not student_email:
        frappe.throw("Student email is required")

    sessions = frappe.get_all(
        "Mentor Session Booking",
        filters={"student": student_email, "status": ["in", ["Pending", "Scheduled", "Accepted"]], "mentor_request_status": ["not in", ["Declined"]]},
        fields=["name", "mentor","offering_type", "session_date","session_date", "session_type", "status", "priority", "topic", "from_time", "to_time", "duration"]
    )

    return sessions

