"""
Integration test: Skill Auto-Endorsement on Student Application Acceptance

Scenarios tested
----------------
1. Student accepted for a Project → Skill Endorsements created (Industry role).
2. Same student accepted for an Internship from the SAME company →
   Additional endorsements created (NOT blocked — different opportunity).
3. Re-running the same Project application (same opportunity) →
   Duplicate skipped silently (no crash, no extra endorsement).

Run with:
    bench --site devstridenex.quantcloud.in execute \
        stridenex_app.stridenex_app.tests.test_skill_auto_endorse.run_all
"""

import frappe
from frappe.utils import now_datetime


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _cleanup(names, doctype):
    for n in names:
        if frappe.db.exists(doctype, n):
            frappe.delete_doc(doctype, n, force=True, ignore_permissions=True)
    frappe.db.commit()


def _count_endorsements(student_skill, company, source_name):
    return frappe.db.count(
        "Skill Endorsement",
        {
            "student_skill":    student_skill,
            "endorser_role":    "Industry",
            "endorser_company": company,
            "source_name":      source_name,
        }
    )


# ---------------------------------------------------------------------------
# Main test runner
# ---------------------------------------------------------------------------

def run_all():
    frappe.set_user("Administrator")

    print("\n" + "="*60)
    print("  Skill Auto-Endorsement — Integration Tests")
    print("="*60)

    # ------------------------------------------------------------------
    # Pick real existing data from DB for a valid, lightweight test
    # ------------------------------------------------------------------

    # 1. Find any Student
    student = frappe.db.get_value("Student", {}, "name")
    if not student:
        print("SKIP: No Student records found.")
        return

    # 2. Find any Industry
    industry = frappe.db.get_value("Industry list", {}, "name")
    if not industry:
        print("SKIP: No Industry list records found.")
        return

    # 3. Find any Skill
    skill = frappe.db.get_value("Skill", {}, "name")
    if not skill:
        print("SKIP: No Skill records found.")
        return

    # 4. Find any Industry Project with required_skills populated
    project = frappe.db.get_value(
        "Industry Project",
        {"industry": industry},
        "name"
    )

    # 5. Find any Internship with required_skills populated
    internship = frappe.db.get_value(
        "Internship",
        {"industry": industry},
        "name"
    )

    if not project and not internship:
        print(f"SKIP: No Industry Project or Internship found for industry={industry}.")
        return

    print(f"\nUsing: student={student}, industry={industry}, skill={skill}")
    print(f"       project={project}, internship={internship}")

    # ------------------------------------------------------------------
    # Ensure student has the skill in their ledger
    # ------------------------------------------------------------------
    student_skill_name = frappe.db.get_value(
        "Student Skill",
        {"student": student, "skill": skill},
        "name"
    )
    created_student_skill = False
    if not student_skill_name:
        ss = frappe.get_doc({
            "doctype": "Student Skill",
            "student": student,
            "skill": skill,
            "current_level": "Intermediate",
            "self_declared": 1,
            "is_public": 1,
        })
        ss.insert(ignore_permissions=True)
        frappe.db.commit()
        student_skill_name = ss.name
        created_student_skill = True
        print(f"  Created Student Skill: {student_skill_name}")

    # ------------------------------------------------------------------
    # Ensure the opportunity has this skill in required_skills
    # ------------------------------------------------------------------
    def _ensure_required_skill(opp_name, opp_dt, child_dt, skill_field="skill"):
        exists = frappe.db.exists(
            child_dt,
            {"parent": opp_name, "parenttype": opp_dt, skill_field: skill}
        )
        if not exists:
            row = frappe.get_doc({
                "doctype": child_dt,
                "parent": opp_name,
                "parenttype": opp_dt,
                "parentfield": "required_skills",
                skill_field: skill,
            })
            row.insert(ignore_permissions=True)
            frappe.db.commit()
            print(f"  Added required skill '{skill}' to {opp_dt} '{opp_name}'")

    if project:
        _ensure_required_skill(project, "Industry Project", "Student Skill Table")
    if internship:
        _ensure_required_skill(internship, "Internship", "Internship Required Skill")

    # ------------------------------------------------------------------
    # Import the helper directly
    # ------------------------------------------------------------------
    from stridenex_app.stridenex_app.doctype.student_applications.student_applications import (
        _auto_endorse_skills
    )

    # Build a mock app_doc using frappe._dict
    def _make_app(opp_type, opp_field, opp_name_val):
        d = frappe._dict(
            student=student,
            opportunity_type=opp_type,
            industry=industry,
            project=opp_name_val if opp_type == "Project" else None,
            internship=opp_name_val if opp_type == "Internship" else None,
        )
        return d

    results = {}

    # ------------------------------------------------------------------
    # TEST 1: Project acceptance creates endorsements
    # ------------------------------------------------------------------
    if project:
        # Clean any prior test endorsements for this opportunity
        prior = frappe.get_all(
            "Skill Endorsement",
            {"student_skill": student_skill_name, "source_name": project},
            pluck="name"
        )
        for p in prior:
            frappe.delete_doc("Skill Endorsement", p, force=True, ignore_permissions=True)
        frappe.db.commit()

        app_doc = _make_app("Project", "project", project)
        created = _auto_endorse_skills(app_doc)
        count = _count_endorsements(student_skill_name, industry, project)
        results["TEST 1 – Project endorsement"] = (
            "PASS ✅" if count >= 1 else f"FAIL ❌ (count={count}, created={created})"
        )
        print(f"\n  [TEST 1] endorsements created for project: {created}")
    else:
        results["TEST 1 – Project endorsement"] = "SKIP (no project)"

    # ------------------------------------------------------------------
    # TEST 2: Internship acceptance from SAME company adds MORE endorsements
    #         (not blocked by project endorsement)
    # ------------------------------------------------------------------
    if internship:
        prior = frappe.get_all(
            "Skill Endorsement",
            {"student_skill": student_skill_name, "source_name": internship},
            pluck="name"
        )
        for p in prior:
            frappe.delete_doc("Skill Endorsement", p, force=True, ignore_permissions=True)
        frappe.db.commit()

        before_count = frappe.db.count(
            "Skill Endorsement",
            {"student_skill": student_skill_name, "endorser_company": industry}
        )

        app_doc = _make_app("Internship", "internship", internship)
        created = _auto_endorse_skills(app_doc)

        after_count = frappe.db.count(
            "Skill Endorsement",
            {"student_skill": student_skill_name, "endorser_company": industry}
        )

        results["TEST 2 – Internship endorsement (same company)"] = (
            "PASS ✅" if after_count > before_count
            else f"FAIL ❌ (before={before_count}, after={after_count}, created={created})"
        )
        print(f"  [TEST 2] endorsements created for internship: {created}")
    else:
        results["TEST 2 – Internship endorsement (same company)"] = "SKIP (no internship)"

    # ------------------------------------------------------------------
    # TEST 3: Re-running same Project → duplicate skipped, count unchanged
    # ------------------------------------------------------------------
    if project:
        count_before = _count_endorsements(student_skill_name, industry, project)
        app_doc = _make_app("Project", "project", project)
        created = _auto_endorse_skills(app_doc)  # should return []
        count_after = _count_endorsements(student_skill_name, industry, project)
        results["TEST 3 – Duplicate opportunity skipped"] = (
            "PASS ✅" if count_before == count_after and created == []
            else f"FAIL ❌ (before={count_before}, after={count_after}, created={created})"
        )
        print(f"  [TEST 3] re-run duplicate (should be empty): {created}")
    else:
        results["TEST 3 – Duplicate opportunity skipped"] = "SKIP (no project)"

    # ------------------------------------------------------------------
    # Print summary
    # ------------------------------------------------------------------
    print("\n" + "="*60)
    print("  RESULTS")
    print("="*60)
    for test_name, outcome in results.items():
        print(f"  {test_name}: {outcome}")
    print("="*60 + "\n")

    # Cleanup created Student Skill if we created it
    if created_student_skill and frappe.db.exists("Student Skill", student_skill_name):
        # Delete endorsements first
        for e in frappe.get_all("Skill Endorsement", {"student_skill": student_skill_name}, pluck="name"):
            frappe.delete_doc("Skill Endorsement", e, force=True, ignore_permissions=True)
        frappe.delete_doc("Student Skill", student_skill_name, force=True, ignore_permissions=True)
        frappe.db.commit()
