"""
Diagnostic script — College Event Email & Notification

Run:
    bench execute stridenex_app.api_stridenex_app.diagnose_event_notification.run_diagnosis
"""

import frappe
from frappe.utils import nowdate, add_days

COLLEGE = "D.Y.Patil Technical campus"
TEST_EMAIL = "stu2@gmail.com"


def _p(msg):
    print(msg)


def run_diagnosis():
    _p("\n" + "="*60)
    _p(" DIAGNOSIS: College Event Email & Notification")
    _p("="*60)

    # ── 1. Outgoing email server ──────────────────────────────────────────
    _p("\n[1] Outgoing Email Server config:")
    email_accounts = frappe.get_all(
        "Email Account",
        filters={"enable_outgoing": 1},
        fields=["name", "email_id", "smtp_server", "smtp_port", "enable_outgoing"],
    )
    if email_accounts:
        for ea in email_accounts:
            _p(f"    ✅ {ea.name} | {ea.email_id} | {ea.smtp_server}:{ea.smtp_port}")
    else:
        _p("    ❌ NO outgoing email account configured — frappe.sendmail() will silently do nothing!")

    # ── 2. Email Queue — recent records ──────────────────────────────────
    _p("\n[2] Email Queue — last 5 records:")
    queue_rows = frappe.db.sql("""
        SELECT name, status, creation, error
        FROM `tabEmail Queue`
        ORDER BY creation DESC
        LIMIT 5
    """, as_dict=True)
    if queue_rows:
        for r in queue_rows:
            _p(f"    {r.name} | status={r.status} | created={r.creation}")
            if r.error:
                _p(f"       ERROR: {r.error[:200]}")
    else:
        _p("    ❌ Email Queue is empty — sendmail() is not queuing anything")

    # ── 3. Email Queue for stu2 specifically ─────────────────────────────
    _p(f"\n[3] Email Queue records for {TEST_EMAIL}:")
    stu2_queue = frappe.db.sql("""
        SELECT eq.name, eq.status, eq.creation, eqr.recipient
        FROM `tabEmail Queue` eq
        LEFT JOIN `tabEmail Queue Recipient` eqr ON eqr.parent = eq.name
        WHERE eqr.recipient = %(email)s
        ORDER BY eq.creation DESC
        LIMIT 5
    """, {"email": TEST_EMAIL}, as_dict=True)
    if stu2_queue:
        for r in stu2_queue:
            _p(f"    ✅ {r.name} | status={r.status} | created={r.creation}")
    else:
        _p(f"    ❌ No emails queued for {TEST_EMAIL}")

    # ── 4. Notification Log for stu2 ─────────────────────────────────────
    _p(f"\n[4] Notification Log (in-app) for {TEST_EMAIL}:")
    notif_logs = frappe.get_all(
        "Notification Log",
        filters={"for_user": TEST_EMAIL},
        fields=["name", "subject", "type", "creation"],
        order_by="creation desc",
        limit=5,
    )
    if notif_logs:
        for n in notif_logs:
            _p(f"    ✅ {n.name} | {n.subject} | created={n.creation}")
    else:
        _p(f"    ❌ No Notification Log entries for {TEST_EMAIL}")

    # ── 5. Background workers running? ───────────────────────────────────
    _p("\n[5] Background job queue status:")
    try:
        from rq import Queue as RQueue
        from frappe.utils.background_jobs import get_redis_conn
        conn = get_redis_conn()
        for qname in ["default", "short", "long"]:
            q = RQueue(qname, connection=conn)
            _p(f"    Queue '{qname}': {len(q)} pending jobs")
    except Exception as ex:
        _p(f"    ⚠️  Could not check RQ queues: {ex}")

    # ── 6. Error Log — College Event related ─────────────────────────────
    _p("\n[6] Recent Error Logs (College Event / Notification):")
    errors = frappe.get_all(
        "Error Log",
        filters={"method": ["like", "%College Event%"]},
        fields=["name", "method", "error", "creation"],
        order_by="creation desc",
        limit=5,
    )
    if errors:
        for e in errors:
            _p(f"    ⚠️  {e.name} | {e.method} | {e.creation}")
            _p(f"       {str(e.error)[:300]}")
    else:
        _p("    No Error Logs found for College Event")

    # ── 7. Live test: direct sendmail with now=True ───────────────────────
    _p(f"\n[7] LIVE TEST — frappe.sendmail() with now=True to {TEST_EMAIL}:")
    queue_before = frappe.db.count("Email Queue")
    try:
        frappe.sendmail(
            recipients=[TEST_EMAIL],
            subject="[DIAGNOSE] StrideNex — Event Notification Test",
            message="""
            <div style="font-family:Arial,sans-serif;padding:20px;">
                <h2 style="color:#0f0fbd;">🎉 Notification Test</h2>
                <p>This is a <strong>diagnostic email</strong> sent directly via
                <code>frappe.sendmail(now=True)</code>.</p>
                <p>If you received this, the email pipeline is working correctly.</p>
                <p>— StrideNex Dev Team</p>
            </div>
            """,
            now=True,  # ← bypass queue, send immediately
        )
        frappe.db.commit()
        queue_after = frappe.db.count("Email Queue")
        _p(f"    Email Queue before: {queue_before} | after: {queue_after}")
        if queue_after > queue_before:
            _p(f"    ✅ sendmail() added {queue_after - queue_before} record(s) to Email Queue")
        else:
            _p(f"    ⚠️  Queue count unchanged — sendmail() may have sent directly OR failed silently")
    except Exception as ex:
        _p(f"    ❌ sendmail() raised exception: {ex}")
        frappe.log_error(frappe.get_traceback(), "Diagnose sendmail")

    # ── 8. Live test: direct in-app notification ─────────────────────────
    _p(f"\n[8] LIVE TEST — direct Notification Log insert for {TEST_EMAIL}:")
    notif_before = frappe.db.count("Notification Log", {"for_user": TEST_EMAIL})
    try:
        from frappe.desk.doctype.notification_log.notification_log import enqueue_create_notification
        notif_doc = frappe._dict({
            "type": "Alert",
            "document_type": "College Event",
            "document_name": "TEST-EVENT",
            "subject": "[DIAGNOSE] Test College Event Notification",
            "from_user": "Administrator",
            "email_content": "This is a test in-app notification from the diagnostic script.",
        })
        enqueue_create_notification([TEST_EMAIL], notif_doc)
        frappe.db.commit()

        import time
        time.sleep(2)  # give background job a moment

        notif_after = frappe.db.count("Notification Log", {"for_user": TEST_EMAIL})
        _p(f"    Notification Log before: {notif_before} | after: {notif_after}")
        if notif_after > notif_before:
            _p(f"    ✅ In-app notification created successfully")
        else:
            _p(f"    ⚠️  No new Notification Log — background worker may not be running")
            _p(f"       Fix: run 'bench start' or 'bench worker' to start background workers")
    except Exception as ex:
        _p(f"    ❌ enqueue_create_notification() raised exception: {ex}")
        frappe.log_error(frappe.get_traceback(), "Diagnose in-app notification")

    # ── SUMMARY ───────────────────────────────────────────────────────────
    _p("\n" + "─"*60)
    _p("DIAGNOSIS COMPLETE — check findings above")
    _p("─"*60)
    _p("""
COMMON FIXES:
  ❌ No outgoing email account → Go to Settings > Email Account > Add SMTP
  ❌ Email not in queue        → frappe.sendmail() is silently failing
  ❌ No notification log       → Background worker not running
                                  Run: bench worker --queue short,default,long
  ❌ Queue jobs stuck          → Run: bench doctor
    """)


def send_direct_to_stu2():
    """
    End-to-end test — creates one College Event, sends email (now=True) and
    in-app notification directly to stu2@gmail.com, verifies both were created.

    Run:
        bench execute stridenex_app.api_stridenex_app.diagnose_event_notification.send_direct_to_stu2
    """
    from frappe.utils import add_days, nowdate, format_date, get_url
    from frappe.desk.doctype.notification_log.notification_log import make_notification_logs

    _p("\n" + "="*60)
    _p(" DIRECT E2E TEST — stu2@gmail.com event notification")
    _p("="*60)

    student_email = "stu2@gmail.com"
    college = "D.Y.Patil Technical campus"

    # 1. Confirm student
    student = frappe.db.get_value(
        "Student", {"email_id": student_email},
        ["name", "first_name", "email_id"], as_dict=True,
    )
    if not student:
        _p(f"[FAIL] {student_email} not found"); return
    _p(f"[OK]   Student: {student.first_name} <{student.email_id}>")

    # 2. Create draft event (no submit = no on_submit hook)
    doc = frappe.get_doc({
        "doctype": "College Event",
        "event": "E2E Test Event",
        "college": college,
        "event_type": "Hackathon",
        "participation_scope": "Intra College",
        "start_date": add_days(nowdate(), 3),
        "end_date": add_days(nowdate(), 5),
        "price": "Free",
    })
    doc.insert(ignore_permissions=True)
    frappe.db.commit()
    _p(f"[OK]   Event created: {doc.name}")

    record_url = get_url(f"/app/college-event/{doc.name}")

    # 3. Send email with now=True
    q_before = frappe.db.count("Email Queue")
    try:
        frappe.sendmail(
            recipients=[student_email],
            subject=f"[E2E TEST] New Event: {doc.event}",
            message=f"""
            <div style="font-family:Arial,sans-serif;padding:24px;background:#f6f6f8;">
              <div style="max-width:600px;margin:0 auto;background:#fff;border-radius:12px;
                          padding:28px;border:1px solid #e2e8f0;">
                <h2 style="color:#0f0fbd;">New Event: {doc.event}</h2>
                <p>Dear <strong>{student.first_name}</strong>,</p>
                <p>A new <strong>{doc.event_type}</strong> has been announced
                   by <strong>{college}</strong>.</p>
                <ul>
                  <li><strong>Start:</strong> {format_date(doc.start_date)}</li>
                  <li><strong>End:</strong>   {format_date(doc.end_date)}</li>
                  <li><strong>Price:</strong> {doc.price or 'Free'}</li>
                </ul>
                <a href="{record_url}"
                   style="background:#ff6b00;color:#fff;padding:12px 24px;
                          border-radius:6px;text-decoration:none;
                          display:inline-block;margin-top:12px;font-weight:600;">
                  View Event &rarr;
                </a>
                <p style="margin-top:24px;color:#64748b;font-size:13px;">
                  StrideNex Events Team
                </p>
              </div>
            </div>
            """,
            now=True,
            reference_doctype=doc.doctype,
            reference_name=doc.name,
        )
        frappe.db.commit()
        q_after = frappe.db.count("Email Queue")
        delta_q = q_after - q_before
        _p(f"[EMAIL] Queue: {q_before} → {q_after} (delta={delta_q})")
        _p(f"[{'OK' if delta_q > 0 else 'FAIL'}]   Email {'sent & stored' if delta_q > 0 else 'NOT stored — check SMTP'}")
    except Exception as ex:
        _p(f"[FAIL]  sendmail raised: {ex}")
        frappe.log_error(frappe.get_traceback(), "send_direct_to_stu2 email")

    # 4. In-app notification — direct insert (no worker needed)
    n_before = frappe.db.count("Notification Log", {"for_user": student_email})
    try:
        notification_doc = frappe._dict({
            "type": "Alert",
            "document_type": doc.doctype,
            "document_name": doc.name,
            "subject": f"[E2E TEST] New Event: {doc.event}",
            "from_user": frappe.session.user or "Administrator",
            "email_content": f"Starts on {format_date(doc.start_date)}. Don't miss it!",
        })
        make_notification_logs(notification_doc, [student_email])
        frappe.db.commit()
        n_after = frappe.db.count("Notification Log", {"for_user": student_email})
        delta_n = n_after - n_before
        _p(f"[NOTIF] Log: {n_before} → {n_after} (delta={delta_n})")
        _p(f"[{'OK' if delta_n > 0 else 'FAIL'}]   In-app notification {'created' if delta_n > 0 else 'NOT created'}")
    except Exception as ex:
        _p(f"[FAIL]  make_notification_logs raised: {ex}")
        frappe.log_error(frappe.get_traceback(), "send_direct_to_stu2 notification")

    # 5. Cleanup
    try:
        frappe.delete_doc("College Event", doc.name, ignore_permissions=True)
        frappe.db.commit()
        _p(f"[CLEAN] Test event {doc.name} deleted")
    except Exception as ex:
        _p(f"[WARN]  Cleanup failed: {ex}")

    _p("\n[DONE] E2E test complete.\n")


def test_bulk_all_students():
    """
    Bulk test — creates one College Event for D.Y.Patil Technical campus,
    calls notify_students() directly, and verifies that EVERY student
    received an email + in-app notification.

    Run:
        bench execute stridenex_app.api_stridenex_app.diagnose_event_notification.test_bulk_all_students
    """
    from frappe.utils import add_days, nowdate, format_date

    COLLEGE = "D.Y.Patil Technical campus"

    _p("\n" + "="*60)
    _p(f" BULK TEST — All students of {COLLEGE}")
    _p("="*60)

    # ── 1. Count students ─────────────────────────────────────────────────
    all_students = frappe.get_all(
        "Student",
        filters={"college": COLLEGE},
        fields=["name", "first_name", "email_id"],
    )
    with_email    = [s for s in all_students if s.email_id]
    without_email = [s for s in all_students if not s.email_id]

    _p(f"\n[DATA] Total students     : {len(all_students)}")
    _p(f"[DATA] With email         : {len(with_email)}")
    _p(f"[DATA] Without email      : {len(without_email)} (will be skipped)")

    if not with_email:
        _p("[FAIL] No students with email — aborting."); return

    # ── 2. Create draft event ─────────────────────────────────────────────
    doc = frappe.get_doc({
        "doctype": "College Event",
        "event": "Bulk Test Hackathon",
        "college": COLLEGE,
        "event_type": "Hackathon",
        "participation_scope": "Intra College",
        "start_date": add_days(nowdate(), 5),
        "end_date":   add_days(nowdate(), 7),
        "price": "Free",
    })
    doc.insert(ignore_permissions=True)
    frappe.db.commit()
    _p(f"\n[OK]   Event created: {doc.name}")

    # ── 3. Snapshot counters before ───────────────────────────────────────
    q_before = frappe.db.count("Email Queue")
    n_before = frappe.db.count("Notification Log")
    _p(f"[SNAP] Email Queue before    : {q_before}")
    _p(f"[SNAP] Notification Log before: {n_before}")

    # ── 4. Trigger notification for ALL students ──────────────────────────
    _p(f"\n[SEND] Calling notify_students() for {len(with_email)} students…")
    sent_email = 0
    sent_notif = 0
    skipped    = 0
    errors     = 0

    students = doc.get_matching_students()
    for student in students:
        try:
            if not student.get("email_id"):
                skipped += 1
                continue

            doc.send_event_email(student)
            sent_email += 1

            user_id = student.get("email_id")
            if user_id and frappe.db.exists("User", user_id):
                doc.send_event_notification(user_id)
                sent_notif += 1

        except Exception as ex:
            errors += 1
            frappe.log_error(
                title=f"Bulk Test Error — {student.get('email_id')}",
                message=frappe.get_traceback()
            )

    frappe.db.commit()

    # ── 5. Snapshot counters after ────────────────────────────────────────
    q_after = frappe.db.count("Email Queue")
    n_after = frappe.db.count("Notification Log")
    delta_q = q_after - q_before
    delta_n = n_after - n_before

    _p(f"\n[RESULT] Emails attempted  : {sent_email}")
    _p(f"[RESULT] Emails in queue   : {delta_q}  (expected ~{len(with_email)})")
    _p(f"[RESULT] Notifications     : {delta_n}  (created in-app logs)")
    _p(f"[RESULT] Skipped (no email): {skipped}")
    _p(f"[RESULT] Errors            : {errors}")

    ok_email = delta_q == sent_email
    _p(f"\n[{'OK' if ok_email else 'WARN'}] Email queue delta matches sent count: {ok_email}")
    _p(f"[{'OK' if delta_n > 0 else 'WARN'}] In-app notifications created: {delta_n > 0}")

    # ── 6. Sample — show last 5 stu2 emails in queue ─────────────────────
    stu2_q = frappe.db.sql("""
        SELECT eq.name, eq.status, eq.creation
        FROM `tabEmail Queue` eq
        LEFT JOIN `tabEmail Queue Recipient` eqr ON eqr.parent = eq.name
        WHERE eqr.recipient = 'stu2@gmail.com'
        ORDER BY eq.creation DESC
        LIMIT 3
    """, as_dict=True)
    _p(f"\n[VERIFY] stu2@gmail.com last 3 queue entries:")
    for r in stu2_q:
        _p(f"         • {r.name} | status={r.status} | {r.creation}")

    # ── 7. Cleanup ────────────────────────────────────────────────────────
    try:
        frappe.delete_doc("College Event", doc.name, ignore_permissions=True)
        frappe.db.commit()
        _p(f"\n[CLEAN] Test event {doc.name} deleted")
    except Exception as ex:
        _p(f"[WARN]  Cleanup failed: {ex}")

    _p(f"""
{"="*60}
BULK TEST SUMMARY
{"="*60}
  College         : {COLLEGE}
  Total students  : {len(all_students)}
  Emails queued   : {delta_q} / {len(with_email)}
  Notifications   : {delta_n}
  Errors          : {errors}
{"="*60}
""")


