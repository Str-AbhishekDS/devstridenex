import unittest
from unittest.mock import patch
import frappe

class TestCollegeCampusDrives(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Create a test college
        cls.college_name = "Test Campus Drive College"
        if not frappe.db.exists("College", cls.college_name):
            c_doc = frappe.get_doc({
                "doctype": "College",
                "college_name": cls.college_name,
                "college_code": "TCDC-123",
                "email": "test_college_drive_admin@example.com",
                "status": "Active"
            })
            c_doc.insert(ignore_permissions=True)
        else:
            frappe.db.set_value("College", cls.college_name, "email", "test_college_drive_admin@example.com")
        frappe.db.commit()

        # Create a student user
        cls.student_email = "test_drive_student@example.com"
        if not frappe.db.exists("User", cls.student_email):
            user = frappe.get_doc({
                "doctype": "User",
                "email": cls.student_email,
                "first_name": "DriveTest",
                "last_name": "Student",
                "send_welcome_email": 0,
                "enabled": 1,
                "roles": [{"role": "Student"}]
            })
            user.insert(ignore_permissions=True)
            frappe.db.commit()

        # Create student record linked to that college
        if not frappe.db.exists("Student", cls.student_email):
            student = frappe.get_doc({
                "doctype": "Student",
                "email_id": cls.student_email,
                "first_name": "DriveTest",
                "last_name": "Student",
                "college": cls.college_name
            })
            student.insert(ignore_permissions=True)
            frappe.db.commit()

        # Create another student belonging to a different college
        cls.other_college = "Other Test College"
        if not frappe.db.exists("College", cls.other_college):
            c_doc = frappe.get_doc({
                "doctype": "College",
                "college_name": cls.other_college,
                "college_code": "OTC-123",
                "email": "other_college_admin@example.com",
                "status": "Active"
            })
            c_doc.insert(ignore_permissions=True)
        else:
            frappe.db.set_value("College", cls.other_college, "email", "other_college_admin@example.com")
        frappe.db.commit()

        cls.other_student_email = "other_drive_student@example.com"
        if not frappe.db.exists("User", cls.other_student_email):
            user = frappe.get_doc({
                "doctype": "User",
                "email": cls.other_student_email,
                "first_name": "OtherDrive",
                "last_name": "Student",
                "send_welcome_email": 0,
                "enabled": 1,
                "roles": [{"role": "Student"}]
            })
            user.insert(ignore_permissions=True)
            frappe.db.commit()

        if not frappe.db.exists("Student", cls.other_student_email):
            student = frappe.get_doc({
                "doctype": "Student",
                "email_id": cls.other_student_email,
                "first_name": "OtherDrive",
                "last_name": "Student",
                "college": cls.other_college
            })
            student.insert(ignore_permissions=True)
            frappe.db.commit()

    @classmethod
    def tearDownClass(cls):
        # Cleanup students
        for email in [cls.student_email, cls.other_student_email]:
            if frappe.db.exists("Student", email):
                frappe.delete_doc("Student", email, force=True, ignore_permissions=True)
            if frappe.db.exists("User", email):
                frappe.delete_doc("User", email, force=True, ignore_permissions=True)

        # Cleanup colleges
        for col in [cls.college_name, cls.other_college]:
            if frappe.db.exists("College", col):
                frappe.delete_doc("College", col, force=True, ignore_permissions=True)

        frappe.db.commit()

    def setUp(self):
        self.created_docs = []

    def tearDown(self):
        for doc in reversed(self.created_docs):
            if frappe.db.exists(doc.doctype, doc.name):
                if doc.docstatus == 1:
                    doc.cancel()
                frappe.delete_doc(doc.doctype, doc.name, force=True, ignore_permissions=True)
        frappe.db.commit()

    @patch("frappe.sendmail")
    @patch("stridenex_app.stridenex_app.doctype.college_campus_drives.college_campus_drives.enqueue_create_notification")
    @patch("frappe.db.exists")
    def test_campus_drive_notification_on_submit(self, mock_exists, mock_enqueue, mock_sendmail):
        existing_notifications = set()

        def mock_exists_fn(dt, name=None):
            if dt == "Notification Log":
                doc_name = name.get("document_name") if isinstance(name, dict) else name
                if doc_name in existing_notifications:
                    return True
                return False
            return bool(frappe.db.get_value(dt, name))

        mock_exists.side_effect = mock_exists_fn

        # When enqueue is called, record that the notification has been "inserted"
        def mock_enqueue_fn(users, notification_doc):
            existing_notifications.add(notification_doc.get("document_name"))

        mock_enqueue.side_effect = mock_enqueue_fn

        # Create a campus drive for Test Campus Drive College (triggers after_insert)
        drive = frappe.get_doc({
            "doctype": "College Campus Drives",
            "college": self.college_name,
            "industry_name": "Test Tech Inc",
            "job_title": "Software Engineer",
            "drive_date": "2026-10-10 10:00:00",
            "registeration_deadline": "2026-10-05 18:00:00",
            "package_offered": "12 LPA",
            "criteria": "8.5",
            "backlog": 0
        })
        drive.insert(ignore_permissions=True)
        self.created_docs.append(drive)

        # Submit the drive (triggers on_submit, but should be blocked by duplicate prevention)
        drive.submit()

        # Check system notification was enqueued exactly once
        mock_enqueue.assert_called_once()
        recipients = mock_enqueue.call_args[0][0]
        notification_doc = mock_enqueue.call_args[0][1]

        # Verify our student is notified, but other college's student is not
        self.assertIn(self.student_email, recipients)
        self.assertNotIn(self.other_student_email, recipients)

        # Verify content contains drive information
        self.assertIn("Software Engineer", notification_doc["subject"])
        self.assertIn("Test Tech Inc", notification_doc["subject"])
        self.assertIn("12 LPA", notification_doc["email_content"])
        self.assertIn("8.5 CGPA", notification_doc["email_content"])
        self.assertIn("Max Backlogs Allowed: 0", notification_doc["email_content"])

        # Check that NO email was sent
        mock_sendmail.assert_not_called()

    @patch("frappe.sendmail")
    @patch("stridenex_app.stridenex_app.doctype.college_campus_drives.college_campus_drives.enqueue_create_notification")
    @patch("frappe.db.exists")
    def test_campus_drive_notification_resolves_college_email(self, mock_exists, mock_enqueue, mock_sendmail):
        existing_notifications = set()

        def mock_exists_fn(dt, name=None):
            if dt == "Notification Log":
                doc_name = name.get("document_name") if isinstance(name, dict) else name
                if doc_name in existing_notifications:
                    return True
                return False
            return bool(frappe.db.get_value(dt, name))

        mock_exists.side_effect = mock_exists_fn

        # Create a drive doc with the college's email
        drive = frappe.get_doc({
            "doctype": "College Campus Drives",
            "college": "test_college_drive_admin@example.com",
            "industry_name": "Email Tech Inc",
            "job_title": "Backend Developer",
            "drive_date": "2026-10-11 10:00:00",
            "registeration_deadline": "2026-10-06 18:00:00",
            "package_offered": "15 LPA",
            "criteria": "8.0",
            "backlog": 0
        })
        # Call notify_students directly to bypass DB Link validation during insert
        drive.notify_students()

        mock_enqueue.assert_called_once()
        recipients = mock_enqueue.call_args[0][0]

        # Verify our student is notified, showing email resolution works during notification dispatch
        self.assertIn(self.student_email, recipients)
        self.assertNotIn(self.other_student_email, recipients)

    def test_create_drive_api_resolves_college_email(self):
        # Test that the whitelist create_drive API resolves college email to the actual college name
        from stridenex_app.stridenex_app.doctype.college_campus_drives.college_campus_drives import create_drive
        from unittest.mock import MagicMock

        payload = {
            "college": "test_college_drive_admin@example.com",
            "industry_name": "API Tech Inc",
            "job_title": "Frontend Developer",
            "drive_date": "2026-10-12 10:00:00",
            "registeration_deadline": "2026-10-07 18:00:00",
            "package_offered": "10 LPA",
            "criteria": "7.5",
            "backlog": 0
        }

        # Mock frappe.request to return our payload via get_json
        mock_request = MagicMock()
        mock_request.get_json.return_value = payload

        with patch("frappe.request", mock_request):
            response = create_drive()
            self.assertEqual(response.get("status"), 200)
            
            drive_name = response.get("name")
            self.assertTrue(frappe.db.exists("College Campus Drives", drive_name))
            
            # Fetch the document and verify the college is stored as name, NOT email
            drive_doc = frappe.get_doc("College Campus Drives", drive_name)
            self.assertEqual(drive_doc.college, self.college_name)
            
            # Clean up the created drive
            self.created_docs.append(drive_doc)
