"""
employability.py

Core logic for calculating and storing the Student Employability Score.

Location in your app (adjust `your_app` to your actual app name):
    apps/your_app/your_app/your_app/employability.py

This module is deliberately doctype-agnostic in its main entry point —
`recalculate_employability_score(student_name)` always recomputes the
score from scratch by reading live data from Student, Student Skill,
Internship Application, and Student Project Enrollment. It never does
incremental math (+10/-5), which avoids drift bugs over time.

Wire-up: see hooks.py in the same folder. Each related doctype's
on_update / after_insert / on_trash event calls a thin wrapper here,
which in turn calls recalculate_employability_score().
"""

import frappe
from frappe.utils import flt

# ---------------------------------------------------------------------
# CONFIG — tune these without touching the calculation logic below
# ---------------------------------------------------------------------

MAX_CGPA = 10.0  # change to 4.0 if you're on a 4-point scale

LEVEL_POINTS = {
    "Beginner": 25,
    "Intermediate": 50,
    "Advanced": 75,
    "Expert": 100,
}

VERIFY_FACTOR = {
    "Verified": 1.0,
    "Unverified": 0.5,
}

WEIGHTS = {
    "cgpa": 0.30,
    "skills": 0.30,
    "internship": 0.20,
    "project": 0.20,
}

INTERNSHIP_SELECTED_STATUS = "Selected"
INTERNSHIP_SCORE_PER_SELECTION = 50   # capped at 100 total
INTERNSHIP_SCORE_CAP = 100

PROJECT_COMPLETED_SCORE = 60
PROJECT_AWARDED_SCORE = 100


# ---------------------------------------------------------------------
# SUB-SCORE CALCULATORS
# ---------------------------------------------------------------------

def get_cgpa_score(student_doc) -> float:
    """Normalize CGPA to a 0-100 scale."""
    cgpa = flt(student_doc.cgpa)
    if MAX_CGPA <= 0:
        return 0.0
    score = (cgpa / MAX_CGPA) * 100
    return max(0.0, min(score, 100.0))


def get_skills_score(student_name: str) -> float:
    """
    Average of (level_points x verification_factor) across all
    Student Skill rows for this student. Averaging — not summing —
    means breadth alone doesn't inflate the score; depth and
    verification do.
    """
    skills = frappe.get_all(
        "Student Skill",
        filters={"student": student_name},
        fields=["current_level", "status"],
    )

    if not skills:
        return 0.0

    total = 0.0
    for s in skills:
        level_pts = LEVEL_POINTS.get(s.level, 0)
        verify_factor = VERIFY_FACTOR.get(s.status, 0.5)
        total += level_pts * verify_factor

    avg_score = total / len(skills)
    return max(0.0, min(avg_score, 100.0))


def get_internship_score(student_name: str) -> float:
    """
    Counts Internship Applications with status = 'Selected'.
    Scaled per selection, capped at 100 so multiple applications
    don't blow past a sane ceiling.
    """
    selected_count = frappe.db.count(
        "Internship Application",
        {"student": student_name, "status": INTERNSHIP_SELECTED_STATUS},
    )
    score = selected_count * INTERNSHIP_SCORE_PER_SELECTION
    return min(score, INTERNSHIP_SCORE_CAP)


def get_project_score(student_name: str) -> float:
    """
    Best-of, not additive: Awarded > Completed > none.
    Prevents a student from gaming the score by enrolling in many
    projects without finishing them well.
    """
    projects = frappe.get_all(
        "Student Project Enrollment",
        filters={"student": student_name},
        fields=["status"],
    )

    if any(p.status == "Awarded" for p in projects):
        return PROJECT_AWARDED_SCORE
    if any(p.status == "Completed" for p in projects):
        return PROJECT_COMPLETED_SCORE
    return 0.0


# ---------------------------------------------------------------------
# MAIN ENTRY POINT
# ---------------------------------------------------------------------

def recalculate_employability_score(student_name: str) -> float:
    """
    Recomputes and persists the employability_score for a single
    student. Safe to call frequently — uses frappe.db.set_value so it
    does NOT re-trigger Student's own doc_events (avoids infinite
    loops when this is itself called from a Student hook).
    """
    if not student_name:
        return 0.0

    student = frappe.get_doc("Student", student_name)

    cgpa_score = get_cgpa_score(student)
    skills_score = get_skills_score(student_name)
    internship_score = get_internship_score(student_name)
    project_score = get_project_score(student_name)

    final_score = (
        WEIGHTS["cgpa"] * cgpa_score
        + WEIGHTS["skills"] * skills_score
        + WEIGHTS["internship"] * internship_score
        + WEIGHTS["project"] * project_score
    )
    final_score = round(final_score, 2)

    frappe.db.set_value("Student", student_name, "employability_score", final_score)

    return final_score


# ---------------------------------------------------------------------
# HOOK WRAPPERS
# Called from hooks.py's doc_events. Each just extracts the student
# link from the triggering doc and delegates to the main function.
# ---------------------------------------------------------------------

def update_score_from_student(doc, method=None):
    """Triggered on Student on_update — only recompute if cgpa changed,
    to avoid unnecessary writes on unrelated field edits."""
    if doc.has_value_changed("cgpa"):
        recalculate_employability_score(doc.name)


def update_score_from_skill(doc, method=None):
    """Triggered on Student Skill: after_insert / on_update / on_trash."""
    if doc.student:
        recalculate_employability_score(doc.student)


def update_score_from_internship(doc, method=None):
    """Triggered on Internship Application: after_insert / on_update / on_trash."""
    if doc.student:
        recalculate_employability_score(doc.student)


def update_score_from_project(doc, method=None):
    """Triggered on Student Project Enrollment: after_insert / on_update / on_trash."""
    if doc.student:
        recalculate_employability_score(doc.student)