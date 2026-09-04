import unittest
from unittest.mock import patch, MagicMock
import frappe

class TestOpportunityNotifications(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Find or create a test college
        college = frappe.db.get_value("College", {}, "name") or "Default College"
        if not frappe.db.exists("College", college):
            c_doc = frappe.get_doc({
                "doctype": "College",
                "college_name": college,
                "status": "Active"
            })
            c_doc.insert(ignore_permissions=True)
            college = c_doc.name

        # Find or create courses
        courses = frappe.get_all("Courses", limit=2, pluck="name")
        if len(courses) >= 2:
            cls.course_match = courses[0]
            cls.course_mismatch = courses[1]
        else:
            # Create a course matching and a course mismatching
            course_match_doc = frappe.get_doc({
                "doctype": "Courses",
                "course_name": "Test Course Match",
                "college": college
            })
            course_match_doc.insert(ignore_permissions=True)
            cls.course_match = course_match_doc.name

            course_mismatch_doc = frappe.get_doc({
                "doctype": "Courses",
                "course_name": "Test Course Mismatch",
                "college": college
            })
            course_mismatch_doc.insert(ignore_permissions=True)
            cls.course_mismatch = course_mismatch_doc.name

        # Find or create departments
        cls.dept_match = "Test Department Match"
        if not frappe.db.exists("College Department", cls.dept_match):
            dept = frappe.get_doc({
                "doctype": "College Department",
                "department_name": cls.dept_match
            })
            dept.insert(ignore_permissions=True)
            
        cls.dept_mismatch = "Test Department Mismatch"
        if not frappe.db.exists("College Department", cls.dept_mismatch):
            dept = frappe.get_doc({
                "doctype": "College Department",
                "department_name": cls.dept_mismatch
            })
            dept.insert(ignore_permissions=True)

        # Find or create skills
        cls.skill_match = "Test Skill Match"
        if not frappe.db.exists("Skill", cls.skill_match):
            skill = frappe.get_doc({
                "doctype": "Skill",
                "skill_name": cls.skill_match,
                "skill_level_schema": "Beginner→Expert"
            })
            skill.insert(ignore_permissions=True)

        cls.skill_mismatch = "Test Skill Mismatch"
        if not frappe.db.exists("Skill", cls.skill_mismatch):
            skill = frappe.get_doc({
                "doctype": "Skill",
                "skill_name": cls.skill_mismatch,
                "skill_level_schema": "Beginner→Expert"
            })
            skill.insert(ignore_permissions=True)

        # Create a test student User if none exists
        cls.student_email = "test_notif_student_unique@example.com"
        if not frappe.db.exists("User", cls.student_email):
            user = frappe.get_doc({
                "doctype": "User",
                "email": cls.student_email,
                "first_name": "TestNotif",
                "last_name": "StudentUser",
                "send_welcome_email": 0,
                "enabled": 1,
                "roles": [{"role": "Student"}]
            })
            user.insert(ignore_permissions=True)
            
        # Create a test Student record linked to this User if none exists
        if not frappe.db.exists("Student", cls.student_email):
            student = frappe.get_doc({
                "doctype": "Student",
                "email_id": cls.student_email,
                "first_name": "TestNotif",
                "last_name": "StudentUser",
                "college": college,
                "course": cls.course_match,
                "department": cls.dept_match
            })
            student.insert(ignore_permissions=True)
        else:
            student = frappe.get_doc("Student", cls.student_email)
            student.department = cls.dept_match
            student.save(ignore_permissions=True)

        # Find or create Student Skill
        cls.student_skill_match_name = None
        student_skill_filters = {"student": cls.student_email, "skill": cls.skill_match}
        if not frappe.db.exists("Student Skill", student_skill_filters):
            student_skill = frappe.get_doc({
                "doctype": "Student Skill",
                "student": cls.student_email,
                "skill": cls.skill_match,
                "status": "Verified",
                "current_level": "Intermediate"
            })
            student_skill.insert(ignore_permissions=True)
            cls.student_skill_match_name = student_skill.name
        else:
            cls.student_skill_match_name = frappe.db.get_value("Student Skill", student_skill_filters, "name")
            
        frappe.db.commit()

        # Find or create a test industry
        cls.industry_name = "Test Notification Industry"
        if not frappe.db.exists("Industry list", cls.industry_name):
            industry = frappe.get_doc({
                "doctype": "Industry list",
                "company_name": cls.industry_name,
                "status": "Active"
            })
            industry.insert(ignore_permissions=True)
            frappe.db.commit()

    @classmethod
    def tearDownClass(cls):
        # Clean up Student Skill
        student_skills = frappe.get_all("Student Skill", filters={"student": cls.student_email})
        for ss in student_skills:
            frappe.delete_doc("Student Skill", ss.name, force=True, ignore_permissions=True)

        # Clean up Student
        if frappe.db.exists("Student", cls.student_email):
            frappe.delete_doc("Student", cls.student_email, force=True, ignore_permissions=True)
        # Clean up User
        if frappe.db.exists("User", cls.student_email):
            frappe.delete_doc("User", cls.student_email, force=True, ignore_permissions=True)
        # Clean up Industry
        if frappe.db.exists("Industry list", cls.industry_name):
            frappe.delete_doc("Industry list", cls.industry_name, force=True, ignore_permissions=True)
        
        # Clean up College Departments
        for d in ["Test Department Match", "Test Department Mismatch"]:
            if frappe.db.exists("College Department", d):
                frappe.delete_doc("College Department", d, force=True, ignore_permissions=True)

        # Clean up Skills
        for s in ["Test Skill Match", "Test Skill Mismatch"]:
            if frappe.db.exists("Skill", s):
                frappe.delete_doc("Skill", s, force=True, ignore_permissions=True)

        # Clean up courses we might have created
        for c in ["Test Course Match", "Test Course Mismatch"]:
            matching_courses = frappe.get_all("Courses", filters={"course_name": c}, pluck="name")
            for mc in matching_courses:
                frappe.delete_doc("Courses", mc, force=True, ignore_permissions=True)

        frappe.db.commit()

    def setUp(self):
        self.created_docs = []

    def tearDown(self):
        # Delete created docs in reverse order
        for doc in reversed(self.created_docs):
            if frappe.db.exists(doc.doctype, doc.name):
                # Cancel first if submitted
                if doc.docstatus == 1:
                    doc.cancel()
                frappe.delete_doc(doc.doctype, doc.name, force=True, ignore_permissions=True)
        frappe.db.commit()

    @patch("frappe.desk.doctype.notification_log.notification_log.enqueue_create_notification")
    def test_project_triggers_notification_when_course_matches(self, mock_enqueue):
        # Project requiring student's course
        project = frappe.get_doc({
            "doctype": "Industry Project",
            "project_name": "Test Match Project",
            "project_code": "TMP01",
            "industry": self.industry_name,
            "status": "Active",
            "duration": 3,
            "application_deadline": "2026-12-31",
            "course": [{"course": self.course_match}]
        })
        project.insert(ignore_permissions=True)
        self.created_docs.append(project)

        project.submit()

        mock_enqueue.assert_called_once()
        recipients = mock_enqueue.call_args[0][0]
        self.assertIn(self.student_email, recipients)

    @patch("frappe.desk.doctype.notification_log.notification_log.enqueue_create_notification")
    def test_project_does_not_trigger_notification_when_course_mismatches(self, mock_enqueue):
        # Project requiring a different course
        project = frappe.get_doc({
            "doctype": "Industry Project",
            "project_name": "Test Mismatch Project",
            "project_code": "TMP02",
            "industry": self.industry_name,
            "status": "Active",
            "duration": 3,
            "application_deadline": "2026-12-31",
            "course": [{"course": self.course_mismatch}]
        })
        project.insert(ignore_permissions=True)
        self.created_docs.append(project)

        project.submit()

        # It should not find our student email because of mismatch
        if mock_enqueue.called:
            recipients = mock_enqueue.call_args[0][0]
            self.assertNotIn(self.student_email, recipients)

    @patch("frappe.desk.doctype.notification_log.notification_log.enqueue_create_notification")
    def test_project_triggers_notification_when_no_courses_specified(self, mock_enqueue):
        # Project with no course requirements specified (open to all)
        project = frappe.get_doc({
            "doctype": "Industry Project",
            "project_name": "Test Open Project",
            "project_code": "TMP03",
            "industry": self.industry_name,
            "status": "Active",
            "duration": 3,
            "application_deadline": "2026-12-31"
        })
        project.insert(ignore_permissions=True)
        self.created_docs.append(project)

        project.submit()

        mock_enqueue.assert_called_once()
        recipients = mock_enqueue.call_args[0][0]
        self.assertIn(self.student_email, recipients)

    @patch("frappe.desk.doctype.notification_log.notification_log.enqueue_create_notification")
    def test_internship_triggers_notification_when_course_matches(self, mock_enqueue):
        internship = frappe.get_doc({
            "doctype": "Internship",
            "title": "Test Match Internship",
            "industry": self.industry_name,
            "status": "Active",
            "duration": 6,
            "location": "Remote",
            "work_mode": "Remote",
            "stipend": 2000,
            "application_deadline": "2026-12-31",
            "course": [{"course": self.course_match}]
        })
        internship.insert(ignore_permissions=True)
        self.created_docs.append(internship)

        internship.submit()

        mock_enqueue.assert_called_once()
        recipients = mock_enqueue.call_args[0][0]
        self.assertIn(self.student_email, recipients)

    @patch("frappe.desk.doctype.notification_log.notification_log.enqueue_create_notification")
    def test_internship_does_not_trigger_notification_when_course_mismatches(self, mock_enqueue):
        internship = frappe.get_doc({
            "doctype": "Internship",
            "title": "Test Mismatch Internship",
            "industry": self.industry_name,
            "status": "Active",
            "duration": 6,
            "location": "Remote",
            "work_mode": "Remote",
            "stipend": 2000,
            "application_deadline": "2026-12-31",
            "course": [{"course": self.course_mismatch}]
        })
        internship.insert(ignore_permissions=True)
        self.created_docs.append(internship)

        internship.submit()

        if mock_enqueue.called:
            recipients = mock_enqueue.call_args[0][0]
            self.assertNotIn(self.student_email, recipients)

    @patch("frappe.desk.doctype.notification_log.notification_log.enqueue_create_notification")
    def test_job_triggers_notification_when_course_matches(self, mock_enqueue):
        job = frappe.get_doc({
            "doctype": "Industry Job Profile",
            "job_title": "Test Match Job",
            "industry": self.industry_name,
            "status": "Open",
            "location": "Boston",
            "employment_type": "Full Time",
            "salary_from": 50000,
            "salary_to": 70000,
            "last_date": "2026-12-31",
            "job_description": "We are looking for a Data Scientist...",
            "course": [{"course": self.course_match}]
        })
        job.insert(ignore_permissions=True)
        self.created_docs.append(job)

        job.submit()

        mock_enqueue.assert_called_once()
        recipients = mock_enqueue.call_args[0][0]
        self.assertIn(self.student_email, recipients)

    @patch("frappe.desk.doctype.notification_log.notification_log.enqueue_create_notification")
    def test_job_does_not_trigger_notification_when_course_mismatches(self, mock_enqueue):
        job = frappe.get_doc({
            "doctype": "Industry Job Profile",
            "job_title": "Test Mismatch Job",
            "industry": self.industry_name,
            "status": "Open",
            "location": "Boston",
            "employment_type": "Full Time",
            "salary_from": 50000,
            "salary_to": 70000,
            "last_date": "2026-12-31",
            "job_description": "We are looking for a Data Scientist...",
            "course": [{"course": self.course_mismatch}]
        })
        job.insert(ignore_permissions=True)
        self.created_docs.append(job)

        job.submit()

        if mock_enqueue.called:
            recipients = mock_enqueue.call_args[0][0]
            self.assertNotIn(self.student_email, recipients)

    @patch("frappe.desk.doctype.notification_log.notification_log.enqueue_create_notification")
    def test_project_triggers_notification_when_department_matches(self, mock_enqueue):
        project = frappe.get_doc({
            "doctype": "Industry Project",
            "project_name": "Test Match Dept Project",
            "project_code": "TMDP01",
            "industry": self.industry_name,
            "status": "Active",
            "duration": 3,
            "application_deadline": "2026-12-31",
            "department": [{"department": self.dept_match}]
        })
        project.insert(ignore_permissions=True)
        self.created_docs.append(project)

        project.submit()

        mock_enqueue.assert_called_once()
        recipients = mock_enqueue.call_args[0][0]
        self.assertIn(self.student_email, recipients)

    @patch("frappe.desk.doctype.notification_log.notification_log.enqueue_create_notification")
    def test_project_does_not_trigger_notification_when_department_mismatches(self, mock_enqueue):
        project = frappe.get_doc({
            "doctype": "Industry Project",
            "project_name": "Test Mismatch Dept Project",
            "project_code": "TMDP02",
            "industry": self.industry_name,
            "status": "Active",
            "duration": 3,
            "application_deadline": "2026-12-31",
            "department": [{"department": self.dept_mismatch}]
        })
        project.insert(ignore_permissions=True)
        self.created_docs.append(project)

        project.submit()

        if mock_enqueue.called:
            recipients = mock_enqueue.call_args[0][0]
            self.assertNotIn(self.student_email, recipients)

    @patch("frappe.desk.doctype.notification_log.notification_log.enqueue_create_notification")
    def test_project_triggers_notification_when_skill_matches(self, mock_enqueue):
        project = frappe.get_doc({
            "doctype": "Industry Project",
            "project_name": "Test Match Skill Project",
            "project_code": "TMSP01",
            "industry": self.industry_name,
            "status": "Active",
            "duration": 3,
            "application_deadline": "2026-12-31",
            "required_skills": [{"skill": self.skill_match}]
        })
        project.insert(ignore_permissions=True)
        self.created_docs.append(project)

        project.submit()

        mock_enqueue.assert_called_once()
        recipients = mock_enqueue.call_args[0][0]
        self.assertIn(self.student_email, recipients)

    @patch("frappe.desk.doctype.notification_log.notification_log.enqueue_create_notification")
    def test_project_does_not_trigger_notification_when_skill_mismatches(self, mock_enqueue):
        project = frappe.get_doc({
            "doctype": "Industry Project",
            "project_name": "Test Mismatch Skill Project",
            "project_code": "TMSP02",
            "industry": self.industry_name,
            "status": "Active",
            "duration": 3,
            "application_deadline": "2026-12-31",
            "required_skills": [{"skill": self.skill_mismatch}]
        })
        project.insert(ignore_permissions=True)
        self.created_docs.append(project)

        project.submit()

        if mock_enqueue.called:
            recipients = mock_enqueue.call_args[0][0]
            self.assertNotIn(self.student_email, recipients)


class TestCollegeSelectionNotifications(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # 1. Create a test college with email
        cls.college_name = "Test Notification College"
        cls.college_email = "test_college_admin@example.com"
        if not frappe.db.exists("College", cls.college_name):
            c_doc = frappe.get_doc({
                "doctype": "College",
                "college_name": cls.college_name,
                "college_code": "TNC-999",
                "email": cls.college_email,
                "status": "Active"
            })
            c_doc.insert(ignore_permissions=True)
            frappe.db.commit()

        # 2. Create a User for college email so system notification can be created
        if not frappe.db.exists("User", cls.college_email):
            user = frappe.get_doc({
                "doctype": "User",
                "email": cls.college_email,
                "first_name": "College",
                "last_name": "Admin",
                "send_welcome_email": 0,
                "enabled": 1
            })
            user.insert(ignore_permissions=True)
            frappe.db.commit()

        # 3. Create student
        cls.student_email = "college_test_student@example.com"
        if not frappe.db.exists("Student", cls.student_email):
            student = frappe.get_doc({
                "doctype": "Student",
                "email_id": cls.student_email,
                "first_name": "CollegeTest",
                "last_name": "Student",
                "college": cls.college_name
            })
            student.insert(ignore_permissions=True)
            frappe.db.commit()

        # 4. Create User for student
        if not frappe.db.exists("User", cls.student_email):
            user = frappe.get_doc({
                "doctype": "User",
                "email": cls.student_email,
                "first_name": "CollegeTest",
                "last_name": "Student",
                "send_welcome_email": 0,
                "enabled": 1,
                "roles": [{"role": "Student"}]
            })
            user.insert(ignore_permissions=True)
            frappe.db.commit()

        cls.industry_name = "Test College Industry"
        if not frappe.db.exists("Industry list", cls.industry_name):
            industry = frappe.get_doc({
                "doctype": "Industry list",
                "company_name": cls.industry_name,
                "status": "Active"
            })
            industry.insert(ignore_permissions=True)
            frappe.db.commit()

        cls.project_name = "Test College Project"
        cls.project_id = None
        existing_project = frappe.db.get_value("Industry Project", {"project_name": cls.project_name}, "name")
        if existing_project:
            cls.project_id = existing_project
        else:
            project = frappe.get_doc({
                "doctype": "Industry Project",
                "project_name": cls.project_name,
                "project_code": "TCP-999",
                "industry": cls.industry_name,
                "status": "Active"
            })
            project.insert(ignore_permissions=True)
            cls.project_id = project.name
            frappe.db.commit()

    @classmethod
    def tearDownClass(cls):
        # Clean up
        if frappe.db.exists("Student", cls.student_email):
            frappe.delete_doc("Student", cls.student_email, force=True, ignore_permissions=True)
        if frappe.db.exists("User", cls.student_email):
            frappe.delete_doc("User", cls.student_email, force=True, ignore_permissions=True)
        if frappe.db.exists("User", cls.college_email):
            frappe.delete_doc("User", cls.college_email, force=True, ignore_permissions=True)
        if frappe.db.exists("College", cls.college_name):
            frappe.delete_doc("College", cls.college_name, force=True, ignore_permissions=True)
        if cls.project_id and frappe.db.exists("Industry Project", cls.project_id):
            frappe.delete_doc("Industry Project", cls.project_id, force=True, ignore_permissions=True)
        if frappe.db.exists("Industry list", cls.industry_name):
            frappe.delete_doc("Industry list", cls.industry_name, force=True, ignore_permissions=True)
        frappe.db.commit()

    def setUp(self):
        self.created_docs = []

    def tearDown(self):
        for doc in reversed(self.created_docs):
            if frappe.db.exists(doc.doctype, doc.name):
                frappe.delete_doc(doc.doctype, doc.name, force=True, ignore_permissions=True)
        frappe.db.commit()

    @patch("frappe.sendmail")
    def test_college_notified_on_student_selection(self, mock_sendmail):
        # Create an application
        app = frappe.get_doc({
            "doctype": "Student Applications",
            "student": self.student_email,
            "opportunity_type": "Project",
            "project": self.project_id,
            "industry": self.industry_name,
            "status": "Applied"
        })
        app.insert(ignore_permissions=True)
        self.created_docs.append(app)

        # Update status to Selected
        app.status = "Selected"
        app.save(ignore_permissions=True)
        frappe.db.commit()

        # Assert the student status update email was sent (not the college email)
        self.assertGreaterEqual(mock_sendmail.call_count, 1)
        
        # Extract recipients from mock calls
        called_recipients = []
        for call_args in mock_sendmail.call_args_list:
            args, kwargs = call_args
            recips = kwargs.get("recipients") or (args[0] if args else [])
            if isinstance(recips, list):
                called_recipients.extend(recips)
            else:
                called_recipients.append(recips)
                
        self.assertIn(self.college_email, called_recipients)
        self.assertIn(self.student_email, called_recipients)

        # Assert system notification log was created for college user
        notification_exists = frappe.db.exists("Notification Log", {
            "for_user": self.college_email,
            "document_type": "Student Applications",
            "document_name": app.name
        })
        self.assertTrue(notification_exists)

        # Cleanup notification log
        if notification_exists:
            frappe.delete_doc("Notification Log", notification_exists, force=True, ignore_permissions=True)
            frappe.db.commit()


class TestIndustryResponseNotifications(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Find or create a test college
        cls.college_name = "Test Industry Notification College"
        cls.college_email = "test_industry_college_admin@example.com"
        if not frappe.db.exists("College", cls.college_name):
            c_doc = frappe.get_doc({
                "doctype": "College",
                "college_name": cls.college_name,
                "college_code": "TINC-999",
                "email": cls.college_email,
                "status": "Active"
            })
            c_doc.insert(ignore_permissions=True)
            frappe.db.commit()

        # Create a test student
        cls.student_email = "ind_test_student@example.com"
        if not frappe.db.exists("User", cls.student_email):
            user = frappe.get_doc({
                "doctype": "User",
                "email": cls.student_email,
                "first_name": "IndustryTest",
                "last_name": "Student",
                "send_welcome_email": 0,
                "enabled": 1,
                "roles": [{"role": "Student"}]
            })
            user.insert(ignore_permissions=True)
            
        if not frappe.db.exists("Student", cls.student_email):
            student = frappe.get_doc({
                "doctype": "Student",
                "email_id": cls.student_email,
                "first_name": "IndustryTest",
                "last_name": "Student",
                "college": cls.college_name
            })
            student.insert(ignore_permissions=True)

        # Create a test industry with email
        cls.industry_name = "Test Industry Response Co"
        cls.industry_email = "test_industry_rep@example.com"
        if not frappe.db.exists("Industry list", cls.industry_name):
            industry = frappe.get_doc({
                "doctype": "Industry list",
                "company_name": cls.industry_name,
                "email": cls.industry_email,
                "status": "Active"
            })
            industry.insert(ignore_permissions=True)

        # Create user for industry
        if not frappe.db.exists("User", cls.industry_email):
            user = frappe.get_doc({
                "doctype": "User",
                "email": cls.industry_email,
                "first_name": "Industry",
                "last_name": "Rep",
                "send_welcome_email": 0,
                "enabled": 1
            })
            user.insert(ignore_permissions=True)

        # Create project
        cls.project_name = "Test Industry Project"
        cls.project_id = None
        existing_project = frappe.db.get_value("Industry Project", {"project_name": cls.project_name}, "name")
        if existing_project:
            cls.project_id = existing_project
        else:
            project = frappe.get_doc({
                "doctype": "Industry Project",
                "project_name": cls.project_name,
                "project_code": "TIP-999",
                "industry": cls.industry_name,
                "status": "Active"
            })
            project.insert(ignore_permissions=True)
            cls.project_id = project.name
            
        frappe.db.commit()

    @classmethod
    def tearDownClass(cls):
        if frappe.db.exists("Student", cls.student_email):
            frappe.delete_doc("Student", cls.student_email, force=True, ignore_permissions=True)
        if frappe.db.exists("User", cls.student_email):
            frappe.delete_doc("User", cls.student_email, force=True, ignore_permissions=True)
        if frappe.db.exists("User", cls.industry_email):
            frappe.delete_doc("User", cls.industry_email, force=True, ignore_permissions=True)
        if frappe.db.exists("Industry list", cls.industry_name):
            frappe.delete_doc("Industry list", cls.industry_name, force=True, ignore_permissions=True)
        if cls.project_id and frappe.db.exists("Industry Project", cls.project_id):
            frappe.delete_doc("Industry Project", cls.project_id, force=True, ignore_permissions=True)
        if frappe.db.exists("College", cls.college_name):
            frappe.delete_doc("College", cls.college_name, force=True, ignore_permissions=True)
        frappe.db.commit()

    def setUp(self):
        self.created_docs = []

    def tearDown(self):
        for doc in reversed(self.created_docs):
            if frappe.db.exists(doc.doctype, doc.name):
                frappe.delete_doc(doc.doctype, doc.name, force=True, ignore_permissions=True)
        frappe.db.commit()

    @patch("frappe.sendmail")
    def test_industry_notified_on_offer_acceptance(self, mock_sendmail):
        # Create application with status Selected
        app = frappe.get_doc({
            "doctype": "Student Applications",
            "student": self.student_email,
            "opportunity_type": "Project",
            "project": self.project_id,
            "industry": self.industry_name,
            "status": "Selected"
        })
        app.insert(ignore_permissions=True)
        self.created_docs.append(app)

        # Transition to Accepted
        app.status = "Accepted"
        app.save(ignore_permissions=True)
        frappe.db.commit()

        # Assert industry email was sent
        self.assertGreaterEqual(mock_sendmail.call_count, 1)
        called_recipients = []
        for call_args in mock_sendmail.call_args_list:
            args, kwargs = call_args
            recips = kwargs.get("recipients") or (args[0] if args else [])
            if isinstance(recips, list):
                called_recipients.extend(recips)
            else:
                called_recipients.append(recips)

        self.assertIn(self.industry_email, called_recipients)

        # Assert Notification Log exists
        notification_exists = frappe.db.exists("Notification Log", {
            "for_user": self.industry_email,
            "document_type": "Student Applications",
            "document_name": app.name
        })
        self.assertTrue(notification_exists)

        if notification_exists:
            frappe.delete_doc("Notification Log", notification_exists, force=True, ignore_permissions=True)
            frappe.db.commit()

    @patch("frappe.sendmail")
    def test_industry_notified_on_offer_rejection(self, mock_sendmail):
        # Create application with status Selected
        app = frappe.get_doc({
            "doctype": "Student Applications",
            "student": self.student_email,
            "opportunity_type": "Project",
            "project": self.project_id,
            "industry": self.industry_name,
            "status": "Selected"
        })
        app.insert(ignore_permissions=True)
        self.created_docs.append(app)

        # Transition to Rejected
        app.status = "Rejected"
        app.save(ignore_permissions=True)
        frappe.db.commit()

        # Assert industry email was sent
        self.assertGreaterEqual(mock_sendmail.call_count, 1)
        called_recipients = []
        for call_args in mock_sendmail.call_args_list:
            args, kwargs = call_args
            recips = kwargs.get("recipients") or (args[0] if args else [])
            if isinstance(recips, list):
                called_recipients.extend(recips)
            else:
                called_recipients.append(recips)

        self.assertIn(self.industry_email, called_recipients)

        # Assert Notification Log exists
        notification_exists = frappe.db.exists("Notification Log", {
            "for_user": self.industry_email,
            "document_type": "Student Applications",
            "document_name": app.name
        })
        self.assertTrue(notification_exists)

        if notification_exists:
            frappe.delete_doc("Notification Log", notification_exists, force=True, ignore_permissions=True)
            frappe.db.commit()


def run_all():
    import unittest
    suite1 = unittest.TestLoader().loadTestsFromTestCase(TestOpportunityNotifications)
    suite2 = unittest.TestLoader().loadTestsFromTestCase(TestCollegeSelectionNotifications)
    suite3 = unittest.TestLoader().loadTestsFromTestCase(TestIndustryResponseNotifications)
    suite = unittest.TestSuite([suite1, suite2, suite3])
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    if not result.wasSuccessful():
        raise RuntimeError("Tests failed")
