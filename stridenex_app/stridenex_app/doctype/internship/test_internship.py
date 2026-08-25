# Copyright (c) 2026, QTPL and Contributors
# See license.txt

import sys
import unittest
from unittest.mock import MagicMock, patch

# Ensure frappe stubbing if run outside of live bench
try:
    import frappe
except ImportError:
    import types
    frappe = types.ModuleType("frappe")
    frappe.whitelist = lambda **kw: (lambda f: f)
    frappe.local = types.SimpleNamespace()
    frappe.local.response = {}
    frappe.response = {}
    frappe.db = MagicMock()
    sys.modules["frappe"] = frappe

from stridenex_app.stridenex_app.doctype.internship.internship import get_internship_list


class TestGetInternshipList(unittest.TestCase):
    def setUp(self):
        # Reset mock/real response dicts
        if hasattr(frappe, "local") and hasattr(frappe.local, "response"):
            frappe.local.response = {}
        else:
            frappe.response = {}

    @patch("stridenex_app.stridenex_app.doctype.internship.internship.frappe.get_all")
    @patch("stridenex_app.stridenex_app.doctype.internship.internship.frappe.get_doc")
    def test_get_internship_list_no_student(self, mock_get_doc, mock_get_all):
        # Mock Internship.get_all returns
        mock_get_all.side_effect = [
            # First call: internships
            [
                {"name": "INT-01", "title": "Backend Intern", "creation": "2026-01-01"},
                {"name": "INT-02", "title": "Frontend Intern", "creation": "2026-01-02"},
            ],
            # Second call: Internship Required Skill
            [
                {"parent": "INT-01", "skill": "Python"},
                {"parent": "INT-02", "skill": "React"},
            ]
        ]

        # Mock Internship get_doc for courses/departments/academic_years
        mock_doc = MagicMock()
        mock_doc.course = []
        mock_doc.department = []
        mock_doc.academic_year = []
        mock_get_doc.return_value = mock_doc

        get_internship_list(student=None)

        # Check response in frappe.response or frappe.local.response
        response = getattr(frappe.local, "response", None) or getattr(frappe, "response", {})
        self.assertEqual(response.get("status"), 200)
        data = response.get("data", {})
        internships = data.get("internships", [])
        
        self.assertEqual(len(internships), 2)
        # Without student, match_score should be 0
        self.assertEqual(internships[0]["match_score"], 0)
        self.assertEqual(internships[1]["match_score"], 0)

    @patch("stridenex_app.stridenex_app.doctype.internship.internship.frappe.get_all")
    @patch("stridenex_app.stridenex_app.doctype.internship.internship.frappe.get_doc")
    @patch("stridenex_app.fit_score_engine._resolve_student")
    @patch("stridenex_app.fit_score_engine._get_student_skill_map")
    @patch("stridenex_app.fit_score_engine._score_coverage_and_depth")
    @patch("stridenex_app.fit_score_engine._score_quality")
    @patch("stridenex_app.fit_score_engine._score_breadth")
    def test_get_internship_list_with_student_sorting(
        self, mock_breadth, mock_quality, mock_cov_depth, mock_skill_map,
        mock_resolve, mock_get_doc, mock_get_all
    ):
        # Setup mocks
        mock_resolve.return_value = "STU-001"
        mock_skill_map.return_value = {"Python": {"status": "Verified"}}

        # Mock get_all calls
        mock_get_all.side_effect = [
            # Internships
            [
                {"name": "INT-01", "title": "Backend Intern", "creation": "2026-01-01"},
                {"name": "INT-02", "title": "Frontend Intern", "creation": "2026-01-02"},
            ],
            # Internship Required Skill
            [
                {"parent": "INT-01", "skill": "Python"},
                {"parent": "INT-02", "skill": "React"},
            ],
            # Student Applications (empty list)
            []
        ]

        # Mock doc
        mock_doc = MagicMock()
        mock_doc.course = []
        mock_doc.department = []
        mock_doc.academic_year = []
        mock_get_doc.return_value = mock_doc

        # Mock the scoring outputs:
        # For INT-01 (Python): coverage & depth = 30, quality = 10, breadth = 0 -> 50
        # For INT-02 (React): coverage & depth = 10, quality = 5, breadth = 0 -> 20
        mock_cov_depth.side_effect = [(30.0, 10.0, ["Python"], []), (10.0, 5.0, [], ["React"])]
        mock_quality.side_effect = [10.0, 5.0]
        mock_breadth.side_effect = [0.0, 0.0]

        get_internship_list(student="test@example.com")

        # Verify sorted response
        response = getattr(frappe.local, "response", None) or getattr(frappe, "response", {})
        self.assertEqual(response.get("status"), 200, response.get("message"))
        data = response.get("data", {})
        internships = data.get("internships", [])

        self.assertEqual(len(internships), 2)
        # INT-01 should be first because it has a match score of 50 vs INT-02's score of 20
        self.assertEqual(internships[0]["name"], "INT-01")
        self.assertEqual(internships[0]["match_score"], 50)
        self.assertEqual(internships[1]["name"], "INT-02")
        self.assertEqual(internships[1]["match_score"], 20)
