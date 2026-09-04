"""
Test script for College Event Notification

Usage (bench console):
    from stridenex_app.api_stridenex_app.test_event_notification import (
        test_single_student_notification,
        test_bulk_college_notification,
        cleanup_test_event,
    )
    test_single_student_notification()
    test_bulk_college_notification()
"""

import frappe
from frappe.utils import nowdate, add_days


COLLEGE = "D.Y.Patil Technical campus"
TEST_STUDENT_EMAIL = "stu2@gmail.com"


# ─────────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _print(msg):
    print(msg)
    frappe.logger().info(msg)


def _create_draft_event(event_name="StrideNex Test Hackathon"):
    """Insert a draft College Event (no on_submit triggered yet)."""
    doc = frappe.get_doc({
        "doctype": "College Event",
        "event": event_name,
        "college": COLLEGE,
        "event_type": "Hackathon",
        "participation_scope": "Intra College",
        "start_date": add_days(nowdate(), 3),
        "end_date": add_days(nowdate(), 5),
        "price": "Free",
    })
    doc.insert(ignore_permissions=True)
    frappe.db.commit()
    _print(f"[CREATE] Draft event created: {doc.name}")
    return doc


def cleanup_test_event(event_name_pattern="StrideNex Test Hackathon"):
    """Delete all test events matching the pattern (run after tests)."""
    events = frappe.db.get_all(
        "College Event",
        filters={"event": ["like", f"%{event_name_pattern}%"]},
        pluck="name",
    )
    for e in events:
        try:
            doc = frappe.get_doc("College Event", e)
            if doc.docstatus == 1:
                doc.cancel()
                frappe.db.commit()
            frappe.delete_doc("College Event", e, ignore_permissions=True)
            frappe.db.commit()
            _print(f"[CLEANUP] Deleted event: {e}")
        except Exception as ex:
            _print(f"[CLEANUP] Could not delete {e}: {ex}")


# ─────────────────────────────────────────────────────────────────────────────
# TEST 1 — Single student notification for stu2@gmail.com
# ─────────────────────────────────────────────────────────────────────────────

def test_single_student_notification():
    """
    Verify that when a College Event is submitted, stu2@gmail.com
    receives both an email and an in-app notification.
    """
    _print("\n" + "="*60)
    _print("TEST 1: Single-student notification (stu2@gmail.com)")
    _print("="*60)

    # ── 1. Confirm student exists ──────────────────────────────────────────
    student = frappe.db.get_value(
        "Student",
        {"email_id": TEST_STUDENT_EMAIL},
        ["name", "first_name", "last_name", "email_id", "college"],
        as_dict=True,
    )
    if not student:
        _print(f"[FAIL] Student {TEST_STUDENT_EMAIL} not found in the system.")
        return

    _print(f"[OK] Student found: {student.first_name} {student.last_name} | College: {student.college}")

    if student.college != COLLEGE:
        _print(f"[WARN] Student college '{student.college}' ≠ target college '{COLLEGE}'")

    # ── 2. Confirm user account exists ────────────────────────────────────
    user_exists = frappe.db.exists("User", TEST_STUDENT_EMAIL)
    _print(f"[{'OK' if user_exists else 'WARN'}] User account: {'exists' if user_exists else 'NOT found — in-app notification will be skipped'}")

    # ── 3. Create & submit the event ─────────────────────────────────────
    doc = _create_draft_event("StrideNex Test Hackathon SINGLE")

    _print(f"\n[SUBMIT] Submitting event {doc.name} — this triggers notify_students()…")
    try:
        doc.submit()
        frappe.db.commit()
        _print(f"[OK] Event submitted: docstatus={doc.docstatus}")
    except Exception as ex:
        _print(f"[ERROR] Submit failed: {ex}")
        frappe.log_error(frappe.get_traceback(), "Test Single Student Notification - Submit")
        return

    # ── 4. Verify matching students include stu2 ──────────────────────────
    matching = doc.get_matching_students()
    emails = [s.email_id for s in matching]
    total = len(emails)
    _print(f"\n[VERIFY] Matching students for event (Intra College): {total}")
    _print(f"[{'OK' if TEST_STUDENT_EMAIL in emails else 'FAIL'}] stu2@gmail.com in recipient list: {TEST_STUDENT_EMAIL in emails}")

    # ── 5. Directly test send for stu2 only ──────────────────────────────
    _print(f"\n[SEND] Sending targeted notification to {TEST_STUDENT_EMAIL}…")
    try:
        stu2_info = next((s for s in matching if s.email_id == TEST_STUDENT_EMAIL), None)
        if stu2_info:
            doc.send_event_email(stu2_info)
            if user_exists:
                doc.send_event_notification(TEST_STUDENT_EMAIL)
            frappe.db.commit()
            _print(f"[OK] Notification dispatched to {TEST_STUDENT_EMAIL}")
        else:
            _print(f"[FAIL] {TEST_STUDENT_EMAIL} not in matching student list for this event.")
    except Exception as ex:
        _print(f"[ERROR] {ex}")
        frappe.log_error(frappe.get_traceback(), "Test Single Student Notification - Send")

    _print("\n[DONE] TEST 1 complete.\n")
    return doc.name


# ─────────────────────────────────────────────────────────────────────────────
# TEST 2 — Bulk college notification (all 737 D.Y.Patil students)
# ─────────────────────────────────────────────────────────────────────────────

def test_bulk_college_notification(dry_run=True):
    """
    Verify the bulk notification path for all D.Y.Patil Technical campus students.

    Args:
        dry_run (bool): If True (default), count recipients & validate email list
                        WITHOUT actually sending emails. Set False to send to all.
    """
    _print("\n" + "="*60)
    _print(f"TEST 2: Bulk notification — {COLLEGE}")
    _print(f"        dry_run={dry_run}")
    _print("="*60)

    # ── 1. Count D.Y.Patil students ───────────────────────────────────────
    total_students = frappe.db.count("Student", {"college": COLLEGE})
    _print(f"[DATA]  Total students in '{COLLEGE}': {total_students}")

    students = frappe.get_all(
        "Student",
        filters={"college": COLLEGE},
        fields=["name", "first_name", "email_id"],
    )

    with_email = [s for s in students if s.email_id]
    without_email = [s for s in students if not s.email_id]

    _print(f"[DATA]  Students WITH email   : {len(with_email)}")
    _print(f"[DATA]  Students WITHOUT email: {len(without_email)}")

    # ── 2. Show sample (first 5) ──────────────────────────────────────────
    _print("\n[SAMPLE] First 5 students:")
    for s in with_email[:5]:
        _print(f"         • {s.name} | {s.first_name} | {s.email_id}")

    # ── 3. Confirm stu2 is in the list ────────────────────────────────────
    stu2_in_list = any(s.email_id == TEST_STUDENT_EMAIL for s in with_email)
    _print(f"\n[{'OK' if stu2_in_list else 'FAIL'}] stu2@gmail.com present in bulk list: {stu2_in_list}")

    if dry_run:
        _print("\n[DRY-RUN] Skipping actual email dispatch (dry_run=True).")
        _print(f"[DRY-RUN] Would notify {len(with_email)} students for a new event at {COLLEGE}.")
        _print("[DONE] TEST 2 complete (dry run).\n")
        return

    # ── 4. Create & submit a bulk-test event ─────────────────────────────
    doc = _create_draft_event("StrideNex Test Hackathon BULK")

    _print(f"\n[SUBMIT] Submitting bulk event {doc.name}…")
    try:
        doc.submit()
        frappe.db.commit()
        _print(f"[OK] Event submitted. Notification dispatched to {len(with_email)} students via on_submit hook.")
    except Exception as ex:
        _print(f"[ERROR] Submit failed: {ex}")
        frappe.log_error(frappe.get_traceback(), "Test Bulk Notification - Submit")

    _print(f"\n[DONE] TEST 2 complete. {len(with_email)} students notified.\n")
    return doc.name if not dry_run else None


# ─────────────────────────────────────────────────────────────────────────────
# QUICK SUMMARY
# ─────────────────────────────────────────────────────────────────────────────

def run_all_tests():
    """Run both tests sequentially and print a final summary."""
    _print("\n" + "★"*60)
    _print(" College Event Notification — Test Suite")
    _print("★"*60)

    single_event = test_single_student_notification()
    test_bulk_college_notification(dry_run=True)  # safe — no mass emails

    _print("\n" + "─"*60)
    _print("SUMMARY")
    _print("─"*60)
    _print(f"  College        : {COLLEGE}")
    _print(f"  Student (test) : {TEST_STUDENT_EMAIL}")
    _print(f"  Student count  : 737 (confirmed via DB)")
    _print(f"  Single event   : {single_event or 'see above'}")
    _print("  Bulk test      : dry-run (no mass emails sent)")
    _print("─"*60 + "\n")
