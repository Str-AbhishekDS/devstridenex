"""
Diagnostic + Fix script for endorsement issue.
"""
import frappe
import traceback

STUDENT = "sstridenex@gmail.com"
SS_NAME = "sstridenex@gmail.com-Github"


def _sep(label=""):
    print("\n" + "-"*60)
    if label:
        print(f"  {label}")
    print("-"*60)


def diagnose():
    frappe.set_user("Administrator")
    print("\n" + "="*60)
    print("  ENDORSEMENT DIAGNOSTIC")
    print("="*60)

    # 1. Student Skill record
    _sep("1. Student Skill record")
    ss = frappe.db.get_value(
        "Student Skill", SS_NAME,
        ["name", "student", "skill", "current_level", "status", "endorsement_count"],
        as_dict=True
    )
    if not ss:
        print(f"  ERROR: Student Skill '{SS_NAME}' NOT FOUND!")
        return
    print(f"  {ss}")

    # 2. All endorsements
    _sep("2. All Skill Endorsements")
    for e in frappe.get_all("Skill Endorsement", {"student_skill": SS_NAME},
            ["name","endorser_role","endorser_company","source_doctype","source_name","endorsed_at"]):
        print(f"  {e}")

    # 3. All student applications
    _sep("3. All Student Applications")
    apps = frappe.get_all("Student Applications", {"student": STUDENT},
        ["name","opportunity_type","project","internship","industry","status"],
        order_by="creation desc")
    for a in apps:
        print(f"  {a}")

    # 4. Accepted internship apps
    accepted = [a for a in apps if a.opportunity_type == "Internship" and a.status == "Accepted"]
    _sep(f"4. Accepted Internship apps (count={len(accepted)})")
    for a in accepted:
        req = frappe.get_all("Internship Required Skill",
            {"parent": a.internship, "parenttype": "Internship"}, ["skill"])
        print(f"\n  App: {a.name}  internship={a.internship}  industry={a.industry}")
        print(f"  Required skills: {[r['skill'] for r in req]}")
        req_ids = {r["skill"] for r in req if r.get("skill")}
        matched = frappe.get_all("Student Skill",
            {"student": STUDENT, "skill": ["in", list(req_ids)]},
            ["name","skill","current_level"]) if req_ids else []
        print(f"  Student skill matches: {matched}")

    _sep("5. Student's full skill ledger")
    for s in frappe.get_all("Student Skill", {"student": STUDENT}, ["name","skill","current_level"]):
        print(f"  {s}")

    print("\n" + "="*60)
    print("  CONCLUSION")
    print("="*60)
    print("  Endorsements are created only when the internship's required_skills")
    print("  overlap with the student's Student Skill ledger entries.")
    print("  If there is NO overlap -> no endorsement (code is working correctly).")
    print("\n  To create an internship endorsement for 'Github', the internship")
    print("  must list 'Github' in its required_skills.")
    print("="*60 + "\n")


def add_github_to_internship_and_test():
    """
    Adds 'Github' to the required_skills of the accepted CodeWorks internship,
    then simulates the endorsement flow.
    """
    frappe.set_user("Administrator")

    INTERNSHIP = "CodeWorks Inc- Machine Learning Engineer"
    SKILL      = "Github"

    print(f"\nAdding '{SKILL}' to required_skills of '{INTERNSHIP}'...")

    # Check if already exists
    exists = frappe.db.exists(
        "Internship Required Skill",
        {"parent": INTERNSHIP, "parenttype": "Internship", "skill": SKILL}
    )
    if exists:
        print(f"  Already exists — skipping insert.")
    else:
        row = frappe.get_doc({
            "doctype": "Internship Required Skill",
            "parent": INTERNSHIP,
            "parenttype": "Internship",
            "parentfield": "required_skills",
            "skill": SKILL,
        })
        row.insert(ignore_permissions=True)
        frappe.db.commit()
        print(f"  Added '{SKILL}' to '{INTERNSHIP}' required_skills.")

    # Now simulate endorsement
    from stridenex_app.stridenex_app.doctype.student_applications.student_applications import (
        _auto_endorse_skills
    )

    app_doc = frappe._dict(
        student=STUDENT,
        opportunity_type="Internship",
        industry="CodeWorks Inc",
        project=None,
        internship=INTERNSHIP,
    )

    print(f"\nSimulating _auto_endorse_skills...")
    try:
        result = _auto_endorse_skills(app_doc)
        if result:
            print(f"  SUCCESS: {len(result)} endorsement(s) created:")
            for r in result:
                print(f"    {r}")
        else:
            print("  Returned empty — checking why...")
            req = frappe.get_all("Internship Required Skill",
                {"parent": INTERNSHIP, "parenttype": "Internship"}, ["skill"])
            print(f"  Required skills now: {[r['skill'] for r in req]}")
            matched = frappe.get_all("Student Skill",
                {"student": STUDENT, "skill": ["in", [r["skill"] for r in req]]},
                ["name","skill"])
            print(f"  Student skill matches: {matched}")
    except Exception as exc:
        print(f"  EXCEPTION: {exc}")
        print(traceback.format_exc())

    # Verify DB
    count = frappe.db.count("Skill Endorsement",
        {"student_skill": SS_NAME, "endorser_company": "CodeWorks Inc",
         "source_name": INTERNSHIP})
    print(f"\n  DB count for internship endorsement: {count}")
    print("  Done.\n")
