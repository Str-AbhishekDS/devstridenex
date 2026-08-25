# Copyright (c) 2026, QTPL and Contributors
# See license.txt

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import add_days, add_years, today

class IntegrationTestStudent(IntegrationTestCase):
	def setUp(self):
		super().setUp()
		self.student_email = "test_dob_student@example.com"
		# Get or create a test college
		self.college = frappe.db.get_value("College", {}, "name") or "Test College"
		if not frappe.db.exists("College", self.college):
			c_doc = frappe.get_doc({
				"doctype": "College",
				"college_name": self.college,
				"status": "Active"
			})
			c_doc.insert(ignore_permissions=True)
			self.college = c_doc.name

		# Clean up any existing test student
		if frappe.db.exists("Student", self.student_email):
			frappe.delete_doc("Student", self.student_email, force=True, ignore_permissions=True)

	def tearDown(self):
		if frappe.db.exists("Student", self.student_email):
			frappe.delete_doc("Student", self.student_email, force=True, ignore_permissions=True)
		super().tearDown()

	def test_invalid_date_of_birth_future_and_today(self):
		# Future date
		future_dob = add_days(today(), 1)
		student = frappe.get_doc({
			"doctype": "Student",
			"email_id": self.student_email,
			"first_name": "Test",
			"last_name": "Student",
			"college": self.college,
			"date_of_birth": future_dob
		})
		self.assertRaises(frappe.ValidationError, student.insert, ignore_permissions=True)

		# Today's date
		today_dob = today()
		student.date_of_birth = today_dob
		self.assertRaises(frappe.ValidationError, student.insert, ignore_permissions=True)

	def test_invalid_date_of_birth_too_young(self):
		# 14 years ago (too young, minimum age is 15)
		young_dob = add_years(today(), -14)
		student = frappe.get_doc({
			"doctype": "Student",
			"email_id": self.student_email,
			"first_name": "Test",
			"last_name": "Student",
			"college": self.college,
			"date_of_birth": young_dob
		})
		self.assertRaises(frappe.ValidationError, student.insert, ignore_permissions=True)

	def test_valid_date_of_birth(self):
		# 20 years ago (valid age)
		valid_dob = add_years(today(), -20)
		student = frappe.get_doc({
			"doctype": "Student",
			"email_id": self.student_email,
			"first_name": "Test",
			"last_name": "Student",
			"college": self.college,
			"date_of_birth": valid_dob
		})
		student.insert(ignore_permissions=True)
		self.assertTrue(frappe.db.exists("Student", self.student_email))
