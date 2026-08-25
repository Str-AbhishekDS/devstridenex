# Copyright (c) 2026, QTPL and Contributors
# See license.txt

import frappe
from frappe.tests import IntegrationTestCase
from stridenex_app.stridenex_app.doctype.college_event.college_event import notify_students_background


class TestCollegeEventNotifications(IntegrationTestCase):
    def setUp(self):
        self.created_docs = []
        self.added_courses = []

        # 1. Dynamically find colleges for the test to avoid hardcoded names
        # Find two colleges under the same university
        shared_uni_colleges = frappe.db.sql("""
            SELECT c1.name as c1_name, c2.name as c2_name, c1.university
            FROM `tabCollege` c1
            JOIN `tabCollege` c2 ON c1.university = c2.university AND c1.name != c2.name
            WHERE c1.university IS NOT NULL AND c1.university != ''
              AND c1.university != 'Shivaji University'
            LIMIT 1
        """, as_dict=True)

        if not shared_uni_colleges:
            raise Exception("Test requires at least two colleges sharing the same university")

        self.college1_name = shared_uni_colleges[0].c1_name
        self.college2_name = shared_uni_colleges[0].c2_name
        self.university_name = shared_uni_colleges[0].university

        # Find one college under a different university
        other_uni_colleges = frappe.db.sql("""
            SELECT name FROM `tabCollege`
            WHERE university != %(uni)s AND university IS NOT NULL AND university != ''
            LIMIT 1
        """, {"uni": self.university_name}, as_dict=True)

        if not other_uni_colleges:
            raise Exception("Test requires a college under a different university")

        self.college3_name = other_uni_colleges[0].name

        # Ensure colleges have a shared stream/course setup
        college1_streams = frappe.get_all(
            "College Courses Table",
            filters={"parent": self.college1_name},
            pluck="stream"
        )
        if not college1_streams:
            c1_course = frappe.get_doc({
                "doctype": "College Courses Table",
                "parent": self.college1_name,
                "parenttype": "College",
                "parentfield": "courses",
                "stream": "Engineering"
            })
            c1_course.insert(ignore_permissions=True)
            self.added_courses.append(c1_course.name)
            college1_streams = ["Engineering"]

        stream = college1_streams[0]

        if not frappe.db.exists("College Courses Table", {"parent": self.college2_name, "stream": stream}):
            c2_course = frappe.get_doc({
                "doctype": "College Courses Table",
                "parent": self.college2_name,
                "parenttype": "College",
                "parentfield": "courses",
                "stream": stream
            })
            c2_course.insert(ignore_permissions=True)
            self.added_courses.append(c2_course.name)

        # 2. Create or update students for each college
        self.student1_email = "student1_north@example.com"
        if frappe.db.exists("Student", self.student1_email):
            s1 = frappe.get_doc("Student", self.student1_email)
            s1.college = self.college1_name
            s1.stream = stream
            s1.academic_year = "First Year"
            s1.save(ignore_permissions=True)
        else:
            s1 = frappe.get_doc({
                "doctype": "Student",
                "email_id": self.student1_email,
                "first_name": "Student1",
                "last_name": "North",
                "college": self.college1_name,
                "stream": stream,
                "academic_year": "First Year"
            })
            s1.insert(ignore_permissions=True)
            self.created_docs.append(s1)

        self.student2_email = "student2_south@example.com"
        if frappe.db.exists("Student", self.student2_email):
            s2 = frappe.get_doc("Student", self.student2_email)
            s2.college = self.college2_name
            s2.stream = stream
            s2.academic_year = "First Year"
            s2.save(ignore_permissions=True)
        else:
            s2 = frappe.get_doc({
                "doctype": "Student",
                "email_id": self.student2_email,
                "first_name": "Student2",
                "last_name": "South",
                "college": self.college2_name,
                "stream": stream,
                "academic_year": "First Year"
            })
            s2.insert(ignore_permissions=True)
            self.created_docs.append(s2)

        self.student3_email = "student3_west@example.com"
        if frappe.db.exists("Student", self.student3_email):
            s3 = frappe.get_doc("Student", self.student3_email)
            s3.college = self.college3_name
            s3.stream = "Engineering"  # Ensure it has a stream
            s3.academic_year = "First Year"
            s3.save(ignore_permissions=True)
        else:
            s3 = frappe.get_doc({
                "doctype": "Student",
                "email_id": self.student3_email,
                "first_name": "Student3",
                "last_name": "West",
                "college": self.college3_name,
                "stream": "Engineering",
                "academic_year": "First Year"
            })
            s3.insert(ignore_permissions=True)
            self.created_docs.append(s3)

        # 3. Create Users for students so system notifications can be logged
        for email in [self.student1_email, self.student2_email, self.student3_email]:
            if not frappe.db.exists("User", email):
                u = frappe.get_doc({
                    "doctype": "User",
                    "email": email,
                    "first_name": "StudentUser",
                    "send_welcome_email": 0,
                    "enabled": 1
                })
                u.insert(ignore_permissions=True)
                self.created_docs.append(u)

        frappe.db.commit()

    def tearDown(self):
        for doc in reversed(self.created_docs):
            if frappe.db.exists(doc.doctype, doc.name):
                try:
                    doc_obj = frappe.get_doc(doc.doctype, doc.name)
                    if doc_obj.docstatus == 1:
                        doc_obj.cancel()
                    frappe.delete_doc(doc.doctype, doc.name, force=True, ignore_permissions=True)
                except Exception:
                    pass
        
        for c_name in self.added_courses:
            frappe.db.delete("College Courses Table", {"name": c_name})

        frappe.db.commit()

    def test_intra_college_event_notification(self):
        # Create and submit an Intra College event hosted by College North
        event = frappe.get_doc({
            "doctype": "College Event",
            "event": "Intra College Hackathon",
            "college": self.college1_name,
            "start_date": "2026-09-01",
            "end_date": "2026-09-03",
            "price": "Free",
            "event_type": "Hackathon",
            "participation_scope": "Intra College"
        })
        event.insert(ignore_permissions=True)
        self.created_docs.append(event)
        event.submit()
        frappe.db.commit()

        # Run notification logic synchronously
        notify_students_background(event.name)

        # Assert only the student in College North (student1) received the system notification
        notif1 = frappe.db.exists("Notification Log", {"for_user": self.student1_email, "document_name": event.name})
        notif2 = frappe.db.exists("Notification Log", {"for_user": self.student2_email, "document_name": event.name})
        notif3 = frappe.db.exists("Notification Log", {"for_user": self.student3_email, "document_name": event.name})

        self.assertTrue(bool(notif1), f"Notification not found for matching student {self.student1_email}")
        self.assertFalse(bool(notif2), f"Notification found for non-matching student {self.student2_email}")
        self.assertFalse(bool(notif3), f"Notification found for non-matching student {self.student3_email}")

        # Assert no emails were generated in the Email Queue
        emails_created = frappe.db.exists("Email Queue", {
            "reference_doctype": "College Event",
            "reference_name": event.name
        })
        self.assertFalse(bool(emails_created), "Emails were created in the Email Queue")

    def test_inter_college_event_notification(self):
        # Create and submit an Inter College event hosted by College North
        event = frappe.get_doc({
            "doctype": "College Event",
            "event": "Inter College Championship",
            "college": self.college1_name,
            "start_date": "2026-09-10",
            "end_date": "2026-09-12",
            "price": "100",
            "event_type": "Competition",
            "participation_scope": "Inter College"
        })
        event.insert(ignore_permissions=True)
        self.created_docs.append(event)
        event.submit()
        frappe.db.commit()

        # Run notification logic synchronously
        notify_students_background(event.name)

        # Assert students in College North (student1) AND College South (student2) received the system notification
        notif1 = frappe.db.exists("Notification Log", {"for_user": self.student1_email, "document_name": event.name})
        notif2 = frappe.db.exists("Notification Log", {"for_user": self.student2_email, "document_name": event.name})
        notif3 = frappe.db.exists("Notification Log", {"for_user": self.student3_email, "document_name": event.name})

        self.assertTrue(bool(notif1), f"Notification not found for matching student {self.student1_email}")
        self.assertTrue(bool(notif2), f"Notification not found for matching student {self.student2_email}")
        self.assertFalse(bool(notif3), f"Notification found for non-matching student {self.student3_email}")

        # Assert no emails were generated in the Email Queue
        emails_created = frappe.db.exists("Email Queue", {
            "reference_doctype": "College Event",
            "reference_name": event.name
        })
        self.assertFalse(bool(emails_created), "Emails were created in the Email Queue")


def run_all():
    import unittest
    suite = unittest.TestLoader().loadTestsFromTestCase(TestCollegeEventNotifications)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    if not result.wasSuccessful():
        raise RuntimeError("Tests failed")
