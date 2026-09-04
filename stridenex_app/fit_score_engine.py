"""
fit_score_engine.py
===================
On-demand Fit Score Engine for StrideNex.

Given an opportunity (Job, Internship, or Project) and a Student, this engine
computes a 0–100 "Fit Score" that tells the industry how well the student's
verified skills match what the opportunity demands.

The score is NEVER stored — it is purely calculated at query time.

Scoring Dimensions
------------------
1. Skill Coverage (50 pts)
   – What % of required skills does the student have (Verified OR Pending)?
   – Verified skill   = full point
   – Pending skill    = half point
   – Unmatched skill  = 0

2. Skill Depth Bonus (20 pts)
   – For each matched required skill, a level bonus is awarded based on the
     student's declared skill level (Beginner=1, Intermediate=2, Advanced=3, Expert=4)
     normalised to the max expert value across all matched skills.

3. Endorsement & Verification Quality (20 pts)
   – AI Verified skill    : +3 pts each (capped at 10)
   – Industry Endorsed    : +4 pts each (capped at 10)
   – Mentor Endorsed      : +2 pts each (capped at 6)
   – Sub-total capped at 20

4. Breadth Bonus (10 pts)
   – Bonus for breadth of student's overall skill set beyond the required list.
   – min(extra_verified_skills * 2, 10)
"""

import frappe
from frappe.utils import flt

# ------------------------------------------------------------------
# CONSTANTS
# ------------------------------------------------------------------
MAX_COVERAGE_PTS  = 50
MAX_DEPTH_PTS     = 20
MAX_QUALITY_PTS   = 20
MAX_BREADTH_PTS   = 10

LEVEL_WEIGHT = {
    "Beginner":     1,
    "Intermediate": 2,
    "Advanced":     3,
    "Expert":       4,
}

SUPPORTED_TYPES = {"Job", "Internship", "Project"}


# ==================================================================
# PUBLIC ENTRY POINT
# ==================================================================

@frappe.whitelist(allow_guest=False)
def get_fit_score(opportunity_type: str, opportunity_name: str, student: str) -> dict:
    """
    Whitelisted API — callable via /api/method/stridenex_app.fit_score_engine.get_fit_score

    Parameters
    ----------
    opportunity_type : str   "Job" | "Internship" | "Project"
    opportunity_name : str   The document name (primary key) of the opportunity
    student          : str   Student document name or email

    Returns
    -------
    dict with:
        fit_score        : int   0-100
        breakdown        : dict  per-dimension scores
        required_skills  : list  skills the opportunity demands
        matched_skills   : list  student skills that matched
        missing_skills   : list  skills the student lacks
        student          : str
        opportunity_type : str
        opportunity_name : str
    """
    # ---- validate inputs ----------------------------------------
    if opportunity_type not in SUPPORTED_TYPES:
        frappe.throw(
            f"opportunity_type must be one of: {', '.join(SUPPORTED_TYPES)}",
            frappe.ValidationError,
        )

    # Resolve student from email if needed
    student = _resolve_student(student)
    if not student:
        frappe.throw("Student not found.", frappe.DoesNotExistError)

    # ---- fetch required skills from the opportunity ------------
    required_skills = _get_required_skills(opportunity_type, opportunity_name)

    if not required_skills:
        return _empty_result(student, opportunity_type, opportunity_name,
                             reason="No required skills defined for this opportunity.")

    # ---- fetch student skills ----------------------------------
    student_skill_map = _get_student_skill_map(student)

    # ---- compute each dimension --------------------------------
    coverage_pts, depth_pts, matched, missing = _score_coverage_and_depth(
        required_skills, student_skill_map
    )

    quality_pts = _score_quality(matched, student_skill_map)

    breadth_pts = _score_breadth(required_skills, student_skill_map)

    # ---- aggregate -----------------------------------------
    raw_score = coverage_pts + depth_pts + quality_pts + breadth_pts
    fit_score = min(round(raw_score), 100)

    return {
        "fit_score":        fit_score,
        "student":          student,
        "opportunity_type": opportunity_type,
        "opportunity_name": opportunity_name,
        "breakdown": {
            "skill_coverage":  round(coverage_pts, 2),
            "skill_depth":     round(depth_pts, 2),
            "quality_score":   round(quality_pts, 2),
            "breadth_bonus":   round(breadth_pts, 2),
        },
        "required_skills":  required_skills,
        "matched_skills":   matched,
        "missing_skills":   missing,
        "total_student_skills": len(student_skill_map),
    }


# ==================================================================
# BATCH API  — score all applicants for a given opportunity
# ==================================================================

@frappe.whitelist(allow_guest=False)
def get_fit_scores_for_opportunity(opportunity_type: str, opportunity_name: str) -> dict:
    """
    Returns fit scores for EVERY student who has applied for the given opportunity.
    Useful for the industry dashboard to rank applicants.

    Returns
    -------
    dict with:
        opportunity_type : str
        opportunity_name : str
        required_skills  : list
        applicants       : list[dict]   sorted by fit_score desc
            Each entry: {student, student_name, fit_score, breakdown,
                         matched_skills, missing_skills}
    """
    if opportunity_type not in SUPPORTED_TYPES:
        frappe.throw(
            f"opportunity_type must be one of: {', '.join(SUPPORTED_TYPES)}",
            frappe.ValidationError,
        )

    required_skills = _get_required_skills(opportunity_type, opportunity_name)
    applicants      = _get_applicants(opportunity_type, opportunity_name)

    results = []
    for applicant in applicants:
        student_name = applicant["student"]
        student_label = applicant.get("student_label") or student_name

        student_skill_map = _get_student_skill_map(student_name)

        coverage_pts, depth_pts, matched, missing = _score_coverage_and_depth(
            required_skills, student_skill_map
        )
        quality_pts = _score_quality(matched, student_skill_map)
        breadth_pts = _score_breadth(required_skills, student_skill_map)

        raw_score = coverage_pts + depth_pts + quality_pts + breadth_pts
        fit_score = min(round(raw_score), 100)

        results.append({
            "student":       student_name,
            "student_name":  student_label,
            "application":   applicant.get("name"),
            "applied_on":    applicant.get("applied_on"),
            "status":        applicant.get("status"),
            "fit_score":     fit_score,
            "breakdown": {
                "skill_coverage": round(coverage_pts, 2),
                "skill_depth":    round(depth_pts, 2),
                "quality_score":  round(quality_pts, 2),
                "breadth_bonus":  round(breadth_pts, 2),
            },
            "matched_skills": matched,
            "missing_skills": missing,
        })

    # Sort applicants by fit_score descending
    results.sort(key=lambda x: x["fit_score"], reverse=True)

    return {
        "opportunity_type": opportunity_type,
        "opportunity_name": opportunity_name,
        "required_skills":  required_skills,
        "total_applicants": len(results),
        "applicants":       results,
    }


# ==================================================================
# PRIVATE HELPERS
# ==================================================================

def _resolve_student(student: str) -> str | None:
    """Resolve an email to a student name if needed."""
    if not student:
        return None
    if "@" in student:
        resolved = frappe.db.get_value("Student", {"email_id": student}, "name")
        return resolved
    # Validate that the student exists
    if frappe.db.exists("Student", student):
        return student
    return None


def _get_required_skills(opportunity_type: str, opportunity_name: str) -> list[str]:
    """
    Returns a list of Skill document names required by the given opportunity.

    DocType mapping
    ---------------
    Job         -> Industry Job Profile  (child table: skills_required -> Student Skill Table, field: skill)
    Internship  -> Internship            (child table: required_skills -> Internship Required Skill, field: skill)
    Project     -> Industry Project      (child table: required_skills -> Student Skill Table, field: skill)
    """
    if opportunity_type == "Job":
        rows = frappe.get_all(
            "Student Skill Table",
            filters={
                "parent":      opportunity_name,
                "parenttype":  "Industry Job Profile",
                "parentfield": "skills_required",
            },
            fields=["skill"],
        )

    elif opportunity_type == "Internship":
        rows = frappe.get_all(
            "Internship Required Skill",
            filters={
                "parent":      opportunity_name,
                "parenttype":  "Internship",
                "parentfield": "required_skills",
            },
            fields=["skill"],
        )

    elif opportunity_type == "Project":
        rows = frappe.get_all(
            "Student Skill Table",
            filters={
                "parent":      opportunity_name,
                "parenttype":  "Industry Project",
                "parentfield": "required_skills",
            },
            fields=["skill"],
        )

    else:
        return []

    # Deduplicate and drop blanks
    return sorted(list({r["skill"] for r in rows if r.get("skill")}))


def _get_student_skill_map(student: str) -> dict:
    """
    Fetches all non-rejected Student Skill records for the student.

    Returns a dict keyed by Skill name:
    {
        skill_name: {
            "status":            "Verified" | "Pending",
            "current_level":     "Beginner" | ... | "Expert",
            "ai_verified":       0 | 1,
            "endorsement_count": int,
            "industry_endorsements": int,
            "mentor_endorsements":   int,
        }
    }
    """
    skills = frappe.get_all(
        "Student Skill",
        filters={
            "student": student,
            "status":  ["!=", "Rejected"],
        },
        fields=[
            "name",
            "skill",
            "status",
            "current_level",
            "ai_verified",
            "endorsement_count",
        ],
    )

    skill_map = {}
    for s in skills:
        # Get endorsement breakdown
        industry_end = frappe.db.count(
            "Skill Endorsement",
            filters={"student_skill": s["name"], "endorser_role": "Industry"},
        )
        mentor_end = frappe.db.count(
            "Skill Endorsement",
            filters={"student_skill": s["name"], "endorser_role": "Mentor"},
        )

        skill_map[s["skill"]] = {
            "status":                s["status"],
            "current_level":         s["current_level"] or "Beginner",
            "ai_verified":           int(s["ai_verified"] or 0),
            "endorsement_count":     int(s["endorsement_count"] or 0),
            "industry_endorsements": industry_end,
            "mentor_endorsements":   mentor_end,
        }

    return skill_map


def _score_coverage_and_depth(
    required_skills: list[str],
    student_skill_map: dict,
) -> tuple[float, float, list[str], list[str]]:
    """
    Compute:
      - coverage_pts (0–50): based on how many required skills are present
      - depth_pts    (0–20): level bonus for matched skills
      - matched      : list of required skills the student has
      - missing      : list of required skills the student lacks
    """
    if not required_skills:
        return 0.0, 0.0, [], []

    matched = []
    missing = []
    coverage_raw = 0.0  # accumulates 0, 0.5, or 1.0 per skill
    depth_raw    = 0.0  # accumulates level weight per matched skill

    for skill in required_skills:
        if skill in student_skill_map:
            info = student_skill_map[skill]
            matched.append(skill)
            # Verified = full, Pending = half
            if info["status"] == "Verified":
                coverage_raw += 1.0
            else:
                coverage_raw += 0.5

            # Depth: level weight normalised to max (Expert=4)
            depth_raw += LEVEL_WEIGHT.get(info["current_level"], 1)
        else:
            missing.append(skill)

    n = len(required_skills)

    # Coverage: (matched_weight / n) * MAX_COVERAGE_PTS
    coverage_pts = (coverage_raw / n) * MAX_COVERAGE_PTS

    # Depth: (avg_level_weight / 4) * MAX_DEPTH_PTS
    if matched:
        avg_level = depth_raw / len(matched)
        depth_pts = (avg_level / 4.0) * MAX_DEPTH_PTS
    else:
        depth_pts = 0.0

    return coverage_pts, depth_pts, matched, missing


def _score_quality(
    matched_skills: list[str],
    student_skill_map: dict,
) -> float:
    """
    Compute endorsement & AI verification quality score (0–20).

    - AI verified  : +3 per skill, capped at 10
    - Industry end : +4 per endorsement, capped at 10
    - Mentor end   : +2 per endorsement, capped at 6
    Sub-total capped at MAX_QUALITY_PTS (20)
    """
    if not matched_skills:
        return 0.0

    ai_pts       = 0.0
    industry_pts = 0.0
    mentor_pts   = 0.0

    for skill in matched_skills:
        info = student_skill_map.get(skill, {})
        if info.get("ai_verified"):
            ai_pts       += 3
        industry_pts += info.get("industry_endorsements", 0) * 4
        mentor_pts   += info.get("mentor_endorsements",   0) * 2

    ai_pts       = min(ai_pts,       10)
    industry_pts = min(industry_pts, 10)
    mentor_pts   = min(mentor_pts,    6)

    return min(ai_pts + industry_pts + mentor_pts, MAX_QUALITY_PTS)


def _score_breadth(
    required_skills: list[str],
    student_skill_map: dict,
) -> float:
    """
    Bonus for having additional verified skills beyond the required set.
    +2 per extra verified skill, capped at MAX_BREADTH_PTS (10).
    """
    required_set = set(required_skills)
    extra_verified = sum(
        1 for skill, info in student_skill_map.items()
        if skill not in required_set and info.get("status") == "Verified"
    )
    return min(extra_verified * 2, MAX_BREADTH_PTS)


def _get_applicants(opportunity_type: str, opportunity_name: str) -> list[dict]:
    """
    Returns a list of {name, student, applied_on, status} dicts for all
    applicants to the given opportunity.
    """
    if opportunity_type == "Job":
        rows = frappe.get_all(
            "Student Job Applications",
            filters={"job_profile": opportunity_name},
            fields=["name", "student", "application_date as applied_on", "status"],
        )
        # Enrich with student display name
        for r in rows:
            r["student_label"] = frappe.db.get_value(
                "Student", r["student"], "first_name"
            ) or r["student"]
        return rows

    elif opportunity_type == "Internship":
        rows = frappe.get_all(
            "Internship Application",
            filters={"internship": opportunity_name},
            fields=["name", "student", "applied_on", "status"],
        )
        for r in rows:
            r["student_label"] = frappe.db.get_value(
                "Student", r["student"], "first_name"
            ) or r["student"]
        return rows

    elif opportunity_type == "Project":
        rows = frappe.get_all(
            "Student Project Enrollment",
            filters={"project": opportunity_name},
            fields=["name", "student", "applied_on", "status"],
        )
        for r in rows:
            r["student_label"] = frappe.db.get_value(
                "Student", r["student"], "first_name"
            ) or r["student"]
        return rows

    return []


def _empty_result(student, opportunity_type, opportunity_name, reason=""):
    return {
        "fit_score":        0,
        "student":          student,
        "opportunity_type": opportunity_type,
        "opportunity_name": opportunity_name,
        "breakdown": {
            "skill_coverage": 0,
            "skill_depth":    0,
            "quality_score":  0,
            "breadth_bonus":  0,
        },
        "required_skills":       [],
        "matched_skills":        [],
        "missing_skills":        [],
        "total_student_skills":  0,
        "note":                  reason,
    }
