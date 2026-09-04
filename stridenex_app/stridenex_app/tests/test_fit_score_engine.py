"""
test_fit_score_engine.py
========================
Unit tests for stridenex_app.fit_score_engine

These tests are standalone — they mock frappe so they run without a
live Frappe/MariaDB instance.

Run with:
    python -m pytest stridenex_app/stridenex_app/tests/test_fit_score_engine.py -v
"""

import sys
import types
import unittest
from unittest.mock import MagicMock, patch


# ---------------------------------------------------------------------------
# Minimal frappe stub so we can import fit_score_engine without a live bench
# ---------------------------------------------------------------------------
def _make_frappe_stub():
    stub = types.ModuleType("frappe")
    stub.whitelist = lambda **kw: (lambda f: f)  # no-op decorator
    stub.throw = lambda msg, exc=None: (_ for _ in ()).throw(ValueError(msg))
    stub.db = MagicMock()
    stub.get_all = MagicMock(return_value=[])
    stub.db.count = MagicMock(return_value=0)
    stub.db.get_value = MagicMock(return_value=None)
    stub.db.exists = MagicMock(return_value=True)
    stub.ValidationError = ValueError
    stub.DoesNotExistError = LookupError
    return stub


frappe_stub = _make_frappe_stub()
sys.modules["frappe"] = frappe_stub
sys.modules["frappe.utils"] = types.ModuleType("frappe.utils")
sys.modules["frappe.utils"].flt = float


# NOW import the engine (frappe is already stubbed)
from stridenex_app.fit_score_engine import (   # noqa: E402
    _get_required_skills,
    _get_student_skill_map,
    _score_coverage_and_depth,
    _score_quality,
    _score_breadth,
    get_fit_score,
    get_fit_scores_for_opportunity,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_skill(status="Verified", level="Intermediate", ai=0, ind_end=0, men_end=0):
    return {
        "status":                status,
        "current_level":         level,
        "ai_verified":           ai,
        "endorsement_count":     ind_end + men_end,
        "industry_endorsements": ind_end,
        "mentor_endorsements":   men_end,
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestScoreCoverageAndDepth(unittest.TestCase):

    def test_all_verified_expert(self):
        required = ["Python", "SQL"]
        skill_map = {
            "Python": _make_skill("Verified", "Expert"),
            "SQL":    _make_skill("Verified", "Expert"),
        }
        cov, depth, matched, missing = _score_coverage_and_depth(required, skill_map)
        self.assertEqual(cov,    50.0)   # 100% coverage
        self.assertEqual(depth,  20.0)   # Expert level — max depth
        self.assertEqual(matched, ["Python", "SQL"])
        self.assertEqual(missing, [])

    def test_all_missing(self):
        required = ["Python", "SQL"]
        cov, depth, matched, missing = _score_coverage_and_depth(required, {})
        self.assertEqual(cov, 0)
        self.assertEqual(depth, 0)
        self.assertEqual(matched, [])
        self.assertEqual(missing, ["Python", "SQL"])

    def test_partial_with_pending(self):
        required = ["Python", "SQL", "ML"]
        skill_map = {
            "Python": _make_skill("Verified",  "Advanced"),
            "SQL":    _make_skill("Pending",   "Beginner"),
            # ML missing
        }
        cov, depth, matched, missing = _score_coverage_and_depth(required, skill_map)
        # coverage_raw = 1.0 + 0.5 = 1.5 / 3 * 50 = 25
        self.assertAlmostEqual(cov, 25.0, places=2)
        # depth: Advanced(3) + Beginner(1) = 4, avg=2, (2/4)*20 = 10
        self.assertAlmostEqual(depth, 10.0, places=2)
        self.assertEqual(set(matched), {"Python", "SQL"})
        self.assertEqual(missing, ["ML"])

    def test_empty_required(self):
        cov, depth, matched, missing = _score_coverage_and_depth([], {"Python": _make_skill()})
        self.assertEqual(cov, 0)
        self.assertEqual(depth, 0)
        self.assertEqual(matched, [])
        self.assertEqual(missing, [])


class TestScoreQuality(unittest.TestCase):

    def test_no_matched_skills(self):
        self.assertEqual(_score_quality([], {}), 0.0)

    def test_ai_verified_capped(self):
        # 5 AI verified skills → 5*3=15 → capped at 10
        skill_map = {f"Skill{i}": _make_skill(ai=1) for i in range(5)}
        matched   = list(skill_map.keys())
        pts = _score_quality(matched, skill_map)
        self.assertEqual(pts, 10.0)   # ai cap is 10

    def test_industry_endorsements(self):
        skill_map = {
            "Python": _make_skill(ind_end=2),  # 2*4 = 8 pts
        }
        pts = _score_quality(["Python"], skill_map)
        self.assertEqual(pts, 8.0)

    def test_total_capped_at_20(self):
        skill_map = {
            "Python": _make_skill(ai=1, ind_end=5, men_end=10),
            "SQL":    _make_skill(ai=1, ind_end=5, men_end=10),
        }
        pts = _score_quality(list(skill_map), skill_map)
        self.assertEqual(pts, 20.0)  # hard cap

    def test_mentor_endorsements(self):
        skill_map = {
            "Python": _make_skill(men_end=2),  # 2*2 = 4 pts
        }
        pts = _score_quality(["Python"], skill_map)
        self.assertEqual(pts, 4.0)


class TestScoreBreadth(unittest.TestCase):

    def test_no_extra_skills(self):
        required = ["Python"]
        skill_map = {"Python": _make_skill("Verified")}
        self.assertEqual(_score_breadth(required, skill_map), 0)

    def test_extra_verified_skills(self):
        required  = ["Python"]
        skill_map = {
            "Python": _make_skill("Verified"),
            "SQL":    _make_skill("Verified"),   # extra
            "ML":     _make_skill("Verified"),   # extra
        }
        pts = _score_breadth(required, skill_map)
        self.assertEqual(pts, 4.0)   # 2 extras * 2

    def test_extra_pending_not_counted(self):
        required  = ["Python"]
        skill_map = {
            "Python": _make_skill("Verified"),
            "SQL":    _make_skill("Pending"),  # extra but NOT verified
        }
        pts = _score_breadth(required, skill_map)
        self.assertEqual(pts, 0.0)

    def test_breadth_capped_at_10(self):
        required  = ["Python"]
        skill_map = {f"Skill{i}": _make_skill("Verified") for i in range(10)}
        skill_map["Python"] = _make_skill("Verified")
        pts = _score_breadth(required, skill_map)
        self.assertEqual(pts, 10.0)  # cap


class TestGetFitScore(unittest.TestCase):
    """Integration-level tests mocking the DB layer."""

    def _mock_internship_scenario(self, required_skills, student_skills_data):
        """
        required_skills    : list of skill names
        student_skills_data: dict[skill_name -> (status, level, ai, ind_end, men_end)]
        """
        # Patch _get_required_skills
        def fake_required(*a, **kw):
            return required_skills

        # Patch _get_student_skill_map
        def fake_student_map(student):
            return {
                skill: _make_skill(*args)
                for skill, args in student_skills_data.items()
            }

        return fake_required, fake_student_map

    @patch("stridenex_app.fit_score_engine._resolve_student", return_value="STU-001")
    @patch("stridenex_app.fit_score_engine._get_required_skills")
    @patch("stridenex_app.fit_score_engine._get_student_skill_map")
    def test_perfect_fit(self, mock_skill_map, mock_required, mock_resolve):
        """A student with all required + 5 extra verified skills should score 100.

        Score breakdown:
          Coverage  : 2/2 verified           = 50
          Depth     : Expert avg=4, (4/4)*20 = 20
          Quality   : ai=min(6,10)=6, ind=min(24,10)=10, men=min(12,6)=6 → min(22,20)=20
          Breadth   : 5 extra verified * 2   = 10
          Total                              = 100
        """
        required = ["Python", "Django"]
        mock_required.return_value = required
        extra = {f"Skill{i}": _make_skill("Verified", "Advanced") for i in range(5)}
        skill_map = {
            "Python": _make_skill("Verified", "Expert", ai=1, ind_end=3, men_end=3),
            "Django": _make_skill("Verified", "Expert", ai=1, ind_end=3, men_end=3),
        }
        skill_map.update(extra)
        mock_skill_map.return_value = skill_map

        result = get_fit_score("Internship", "INT-001", "STU-001")
        self.assertEqual(result["fit_score"], 100)
        self.assertEqual(result["missing_skills"], [])

    @patch("stridenex_app.fit_score_engine._resolve_student", return_value="STU-001X")
    @patch("stridenex_app.fit_score_engine._get_required_skills")
    @patch("stridenex_app.fit_score_engine._get_student_skill_map")
    def test_max_without_breadth(self, mock_skill_map, mock_required, mock_resolve):
        """Max score without extra skills is 90 (coverage+depth+quality, breadth=0)."""
        mock_required.return_value = ["Python", "Django"]
        mock_skill_map.return_value = {
            "Python": _make_skill("Verified", "Expert", ai=1, ind_end=3, men_end=3),
            "Django": _make_skill("Verified", "Expert", ai=1, ind_end=3, men_end=3),
        }
        result = get_fit_score("Internship", "INT-001", "STU-001X")
        self.assertEqual(result["fit_score"], 90)
        self.assertEqual(result["breakdown"]["breadth_bonus"], 0)

    @patch("stridenex_app.fit_score_engine._resolve_student", return_value="STU-002")
    @patch("stridenex_app.fit_score_engine._get_required_skills")
    @patch("stridenex_app.fit_score_engine._get_student_skill_map")
    def test_zero_fit(self, mock_skill_map, mock_required, mock_resolve):
        """A student with NO required skills should score 0."""
        mock_required.return_value = ["Python", "Django"]
        mock_skill_map.return_value = {}

        result = get_fit_score("Internship", "INT-001", "STU-002")
        self.assertEqual(result["fit_score"], 0)
        self.assertEqual(result["matched_skills"], [])

    @patch("stridenex_app.fit_score_engine._resolve_student", return_value="STU-003")
    @patch("stridenex_app.fit_score_engine._get_required_skills")
    @patch("stridenex_app.fit_score_engine._get_student_skill_map")
    def test_partial_fit(self, mock_skill_map, mock_required, mock_resolve):
        """50% skill coverage with Intermediate level."""
        mock_required.return_value = ["Python", "SQL"]
        mock_skill_map.return_value = {
            "Python": _make_skill("Verified", "Intermediate"),
        }

        result = get_fit_score("Job", "JOB-001", "STU-003")
        # Coverage: 1/2 * 50 = 25
        # Depth: avg_level(Intermediate=2) / 4 * 20 = 10
        # Quality: 0 (no endorsements/AI)
        # Breadth: 0 (no extra skills)
        # Total = 35
        self.assertEqual(result["fit_score"], 35)
        self.assertIn("SQL", result["missing_skills"])

    @patch("stridenex_app.fit_score_engine._resolve_student", return_value="STU-004")
    @patch("stridenex_app.fit_score_engine._get_required_skills")
    @patch("stridenex_app.fit_score_engine._get_student_skill_map")
    def test_no_required_skills(self, mock_skill_map, mock_required, mock_resolve):
        """Opportunity with no required skills → fit_score = 0 with a note."""
        mock_required.return_value = []
        mock_skill_map.return_value = {"Python": _make_skill("Verified")}

        result = get_fit_score("Project", "PROJ-001", "STU-004")
        self.assertEqual(result["fit_score"], 0)
        self.assertIn("note", result)

    def test_invalid_opportunity_type(self):
        with self.assertRaises(ValueError):
            get_fit_score("Grant", "GRANT-001", "STU-001")


class TestGetFitScoresForOpportunity(unittest.TestCase):

    @patch("stridenex_app.fit_score_engine._get_required_skills")
    @patch("stridenex_app.fit_score_engine._get_applicants")
    @patch("stridenex_app.fit_score_engine._get_student_skill_map")
    def test_sorted_output(self, mock_skill_map, mock_applicants, mock_required):
        mock_required.return_value = ["Python"]
        mock_applicants.return_value = [
            {"student": "STU-A", "name": "APP-1", "applied_on": "2026-01-01", "status": "Applied"},
            {"student": "STU-B", "name": "APP-2", "applied_on": "2026-01-02", "status": "Applied"},
        ]

        def student_skills(student):
            if student == "STU-A":
                return {"Python": _make_skill("Verified", "Expert", ai=1)}
            return {}  # STU-B has no skills

        mock_skill_map.side_effect = student_skills

        result = get_fit_scores_for_opportunity("Internship", "INT-001")
        applicants = result["applicants"]
        self.assertEqual(len(applicants), 2)
        # STU-A should rank first
        self.assertEqual(applicants[0]["student"], "STU-A")
        self.assertGreater(applicants[0]["fit_score"], applicants[1]["fit_score"])
        self.assertEqual(applicants[1]["fit_score"], 0)


if __name__ == "__main__":
    unittest.main()
