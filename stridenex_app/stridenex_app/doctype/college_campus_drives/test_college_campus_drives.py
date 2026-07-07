# Copyright (c) 2026, QTPL and Contributors
# See license.txt

import frappe
from frappe.tests import IntegrationTestCase


# On IntegrationTestCase, the doctype test records and all
# link-field test record dependencies are recursively loaded
# Use these module variables to add/remove to/from that list
EXTRA_TEST_RECORD_DEPENDENCIES = []  # eg. ["User"]
IGNORE_TEST_RECORD_DEPENDENCIES = []  # eg. ["User"]



class IntegrationTestCollegeCampusDrives(IntegrationTestCase):
	"""
	Integration tests for CollegeCampusDrives.
	Use this class for testing interactions between multiple components.
	"""

	pass

@frappe.whitelist()
def get_placement_counts():
    placed = frappe.db.count("Campus Drive Application", 
        filters={"status": "Selected", "docstatus": 1})
    
    shortlisted = frappe.db.count("Campus Drive Application", 
        filters={"status": "Shortlisted", "docstatus": ["!=", 2]})
    
    applied = frappe.db.count("Campus Drive Application", 
        filters={"status": ["in", ["Applied", "Shortlisted", "Selected"]], 
                 "docstatus": ["!=", 2]})
    
    # Students who exist but have zero applications
    all_students = frappe.db.count("Student", filters={"docstatus": 1})
    students_applied = frappe.db.sql("""
        SELECT COUNT(DISTINCT student) FROM `tabCampus Drive Application`
        WHERE docstatus != 2
    """)[0][0]
    not_applied = all_students - students_applied

    return {
        "placed": placed,
        "shortlisted": shortlisted,
        "applied_to_drives": applied,
        "not_applied_yet": not_applied
    }