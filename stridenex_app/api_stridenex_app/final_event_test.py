"""
Final College Event System-Notification Test Suite

Verifies:
  1) Intra College: Creates event -> only students of that college get in-app notifications.
  2) Inter College: Creates event -> students of same university AND same stream get notifications.
  3) No emails are sent or queued (email notifications are completely removed).

Run:
    bench execute stridenex_app.api_stridenex_app.final_event_test.run_full_test
"""

import frappe
from frappe.utils import add_days, nowdate

COLLEGE             = "D.Y.Patil Technical campus"
INTRA_TEST_EMAIL    = "stu2@gmail.com"  # Belongs to COLLEGE, stream: Commerce
INTER_TEST_EMAIL    = "ab10@g.com"      # Belongs to university sister college, stream: Engineering


def _p(msg):
    print(msg)


def _cleanup(event_name):
    try:
        if frappe.db.exists("College Event", event_name):
            frappe.delete_doc("College Event", event_name, ignore_permissions=True)
            frappe.db.commit()
            _p(f"  [CLEAN] Test event {event_name} deleted")
    except Exception as ex:
        _p(f"  [WARN]  Cleanup failed: {ex}")


def _create_event(event_title, scope):
    """Insert a College Event (triggers after_insert -> notify_students_background)."""
    doc = frappe.get_doc({
        "doctype": "College Event",
        "event": event_title,
        "college": COLLEGE,
        "event_type": "Hackathon",
        "participation_scope": scope,
        "start_date": add_days(nowdate(), 5),
        "end_date":   add_days(nowdate(), 7),
        "price": "Free",
    })
    doc.insert(ignore_permissions=True)
    frappe.db.commit()
    return doc


def _notify_now(doc):
    """Run notification generation synchronously to inspect results immediately."""
    from stridenex_app.stridenex_app.doctype.college_event.college_event import notify_students_background
    notify_students_background(doc.name)


def test_intra_college():
    _p("\n" + "="*60)
    _p("TEST A — Intra College (Same College, Any Stream)")
    _p("="*60)

    # Count matching students
    students = frappe.get_all("Student", filters={"college": COLLEGE}, fields=["name", "email_id"])
    _p(f"  Total students in '{COLLEGE}': {len(students)}")

    # Verify INTRA_TEST_EMAIL is in this college
    stu_exists = any(s.email_id == INTRA_TEST_EMAIL for s in students)
    _p(f"  Student '{INTRA_TEST_EMAIL}' belongs to this college: {'YES ✅' if stu_exists else 'NO ❌'}")

    doc = _create_event("Intra Test System Notif", "Intra College")
    _p(f"  Created Event: {doc.name}")

    # Trigger
    _notify_now(doc)

    # Check for direct notification log existence linked to this event
    notif_exists = frappe.db.exists("Notification Log", {
        "for_user": INTRA_TEST_EMAIL,
        "document_name": doc.name
    })

    # Check if any emails were generated for this event in Email Queue
    emails_created = frappe.db.exists("Email Queue", {
        "reference_doctype": "College Event",
        "reference_name": doc.name
    })

    _p(f"  System Notification Log exists for '{INTRA_TEST_EMAIL}': {'YES ✅' if notif_exists else 'NO ❌'}")
    _p(f"  Emails created in queue for this event: {'YES ❌' if emails_created else 'NO ✅'}")

    # Assertions
    pass_notif = bool(notif_exists)
    pass_email = not emails_created

    _p(f"  [{'PASS ✅' if pass_notif else 'FAIL ❌'}] System notification generated for same-college student")
    _p(f"  [{'PASS ✅' if pass_email else 'FAIL ❌'}] No emails created in Email Queue")

    _cleanup(doc.name)
    return pass_notif and pass_email


def test_inter_college():
    _p("\n" + "="*60)
    _p("TEST B — Inter College (Same University + Same Stream)")
    _p("="*60)

    # University & stream of the creating college
    university = frappe.db.get_value("College", COLLEGE, "university")
    streams = frappe.get_all("College Courses Table", filters={"parent": COLLEGE}, pluck="stream")

    _p(f"  Creator College: {COLLEGE}")
    _p(f"  University     : {university}")
    _p(f"  College Streams: {streams}")

    # Check target test students
    stu_intra = frappe.db.get_value("Student", {"email_id": INTRA_TEST_EMAIL}, ["college", "stream"], as_dict=True)
    stu_inter = frappe.db.get_value("Student", {"email_id": INTER_TEST_EMAIL}, ["college", "stream"], as_dict=True)

    _p(f"  Student A ({INTRA_TEST_EMAIL}): College={stu_intra.college}, Stream={stu_intra.stream}")
    _p(f"  Student B ({INTER_TEST_EMAIL}): College={stu_inter.college}, Stream={stu_inter.stream}")

    doc = _create_event("Inter Test System Notif", "Inter College")
    _p(f"  Created Event: {doc.name}")

    # Trigger
    _notify_now(doc)

    # Verify presence/absence of notifications for this specific event
    notif_a = frappe.db.exists("Notification Log", {
        "for_user": INTRA_TEST_EMAIL,
        "document_name": doc.name
    })
    notif_b = frappe.db.exists("Notification Log", {
        "for_user": INTER_TEST_EMAIL,
        "document_name": doc.name
    })

    # Check if any emails were generated for this event in Email Queue
    emails_created = frappe.db.exists("Email Queue", {
        "reference_doctype": "College Event",
        "reference_name": doc.name
    })

    _p(f"  Notification Log exists for Student A (diff stream): {'YES ❌' if notif_a else 'NO ✅'}")
    _p(f"  Notification Log exists for Student B (same stream + university): {'YES ✅' if notif_b else 'NO ❌'}")
    _p(f"  Emails created in queue for this event: {'YES ❌' if emails_created else 'NO ✅'}")

    # Assertions
    pass_a = not notif_a
    pass_b = bool(notif_b)
    pass_q = not emails_created

    _p(f"  [{'PASS ✅' if pass_a else 'FAIL ❌'}] Student A (wrong stream) was not notified")
    _p(f"  [{'PASS ✅' if pass_b else 'FAIL ❌'}] Student B (same university + same stream) was notified")
    _p(f"  [{'PASS ✅' if pass_q else 'FAIL ❌'}] No emails created in Email Queue")

    _cleanup(doc.name)
    return pass_a and pass_b and pass_q


def run_full_test():
    _p("\n" + "★"*60)
    _p(" College Event Notification — SYSTEM NOTIFICATION TEST")
    _p("★"*60)

    frappe.flags.in_test = True

    # Pre-flight checks
    for email in [INTRA_TEST_EMAIL, INTER_TEST_EMAIL]:
        if not frappe.db.exists("Student", {"email_id": email}):
            _p(f"[ABORT] Test student {email} not found in database."); return
        if not frappe.db.exists("User", email):
            _p(f"[ABORT] Test User {email} not found in database."); return

    result_a = test_intra_college()
    result_b = test_inter_college()

    _p("\n" + "─"*60)
    _p("FINAL TEST RESULTS")
    _p("─"*60)
    _p(f"  Intra College Notification: {'PASS ✅' if result_a else 'FAIL ❌'}")
    _p(f"  Inter College Notification: {'PASS ✅' if result_b else 'FAIL ❌'}")
    _p("─"*60 + "\n")
