"""
employability.py

Core logic for calculating and storing the Student Employability Score.
"""

import frappe
from frappe.utils import flt

# ---------------------------------------------------------------------
# CONFIG — tune these without touching the calculation logic below
# ---------------------------------------------------------------------

WEIGHTS = {
    "cgpa": 0.30,
    "skills": 0.70,
}

# ---------------------------------------------------------------------
# SUB-SCORE CALCULATORS
# ---------------------------------------------------------------------

def get_cgpa_score(student_doc) -> float:
    """Normalize CGPA to a 0-100 scale."""
    cgpa = flt(student_doc.cgpa)
    score = (cgpa / 10.0) * 100
    return max(0.0, min(score, 100.0))


# ---------------------------------------------------------------------
# MAIN ENTRY POINT
# ---------------------------------------------------------------------

def recalculate_employability_score(student_name_or_doc) -> float:
    """
    Recomputes and persists the employability_score for a single
    student based on the required skills for their active Student Path Enrollments,
    or falls back to their Stream, Course, and Department (Educational Skill Requirements)
    combined with their CGPA.
    """
    if not student_name_or_doc:
        return 0.0

    if isinstance(student_name_or_doc, str):
        student = frappe.get_doc("Student", student_name_or_doc)
        student_name = student_name_or_doc
    else:
        student = student_name_or_doc
        student_name = student.name

    # 1. CGPA Score (30% weight)
    cgpa_score = get_cgpa_score(student)

    # 2. Skills Score (70% weight)
    # Check if student is enrolled in any active Career Path
    active_enrollments = frappe.get_all(
        "Student Path Enrollment",
        filters={"student": student_name, "status": "Active"},
        fields=["name"]
    )

    required_skills = []
    if active_enrollments:
        enrollment_names = [e.name for e in active_enrollments]
        milestones = frappe.get_all(
            "Student Milestone Progress",
            filters={"parent": ["in", enrollment_names], "parentfield": "milestone_progress"},
            fields=["skill"]
        )
        required_skills = sorted(list(set(m.skill for m in milestones if m.skill)))
    else:
        # Find the best matching Educational Skill Requirement
        requirements = frappe.get_all(
            "Educational Skill Requirement",
            fields=["name", "stream", "course", "department"]
        )
        
        best_match = None
        best_score = -1
        
        for r in requirements:
            if r.stream and r.stream != student.stream:
                continue
            if r.course and r.course != student.course:
                continue
            if r.department and r.department != student.department:
                continue
                
            # Match score to prioritize more specific combinations
            match_score = 0
            if r.stream and r.stream == student.stream:
                match_score += 4
            if r.course and r.course == student.course:
                match_score += 2
            if r.department and r.department == student.department:
                match_score += 1
                
            if match_score > best_score:
                best_score = match_score
                best_match = r.name

        if best_match:
            req_doc = frappe.get_doc("Educational Skill Requirement", best_match)
            required_skills = [d.skill for d in req_doc.skills if d.skill]

    if not required_skills:
        skills_score = 0.0
    else:
        student_skills = frappe.get_all(
            "Student Skill",
            filters={"student": student_name, "status": ["!=", "Rejected"]},
            fields=["skill", "status"]
        )
        student_skill_map = {s["skill"]: s for s in student_skills}
        
        total_points = 0.0
        for req_skill in required_skills:
            if req_skill in student_skill_map:
                status = student_skill_map[req_skill]["status"]
                if status == "Verified":
                    total_points += 1.0
                else:
                    total_points += 0.5
        
        skills_score = (total_points / len(required_skills)) * 100.0

    # Combine score
    final_score = (WEIGHTS["cgpa"] * cgpa_score) + (WEIGHTS["skills"] * skills_score)
    final_score = round(final_score, 2)

    if isinstance(student_name_or_doc, str):
        frappe.db.set_value("Student", student_name, "employability_score", final_score)
    else:
        student.employability_score = final_score

    return final_score


# ---------------------------------------------------------------------
# HOOK WRAPPERS
# Called from hooks.py's doc_events. Each just extracts the student
# link from the triggering doc and delegates to the main function.
# ---------------------------------------------------------------------

def update_score_from_student(doc, method=None):
    """Triggered on Student before_save — recompute if new, or if cgpa, stream, course, or department changed."""
    if (doc.is_new() or
        doc.has_value_changed("cgpa") or 
        doc.has_value_changed("stream") or 
        doc.has_value_changed("course") or 
        doc.has_value_changed("department")):
        score = recalculate_employability_score(doc)
        doc.employability_score = score


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


def update_score_from_enrollment(doc, method=None):
    """Triggered on Student Path Enrollment: after_insert / on_update / on_trash."""
    if doc.student:
        recalculate_employability_score(doc.student)

