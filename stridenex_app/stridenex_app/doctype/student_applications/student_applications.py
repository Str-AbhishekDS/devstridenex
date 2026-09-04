# Copyright (c) 2026, QTPL and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import now_datetime
from stridenex_app.api_stridenex_app.app_utils import (
    gen_response,
    exception_handel
)


class StudentApplications(Document):

	def on_update(self):
		"""
		When a Project or Internship application status transitions to 'Accepted',
		auto-create Industry Skill Endorsements for every required skill of the
		opportunity that also exists in the student's Student Skill ledger.
		Duplicate endorsements (same industry + student_skill) are silently skipped.
		"""
		if self.opportunity_type not in ("Project", "Internship"):
			return
		if self.status != "Accepted":
			return
		_auto_endorse_skills(self)


DOCTYPE_MAP = {
    "Project": ("Industry Project", "project"),
    "Internship": ("Internship", "internship"),
    "Job": ("Industry Job Profile", "job_profile")
}


@frappe.whitelist(allow_guest=True)
def apply(opportunity_type, opportunity_name, resume=None, notes=None,student=None):

    try:
        # Validate opportunity type
        if opportunity_type not in DOCTYPE_MAP:
            frappe.throw(
                f"Invalid opportunity_type: {opportunity_type}"
            )

        target_doctype, target_fieldname = DOCTYPE_MAP[opportunity_type]

        MAX_APPLICATIONS = 5

        current_count = frappe.db.count(
            "Student Applications",
            filters={
                "student": student,
                "opportunity_type": opportunity_type,
                "status": ["!=", "Withdrawn"]
            }
        )

        if current_count >= MAX_APPLICATIONS:
            frappe.throw(
                f"You have reached the maximum limit of "
                f"{MAX_APPLICATIONS} applications. "
                f"Please withdraw an existing application before "
                f"applying again."
            )

        # ---------------------------------------------------------
        # Check opportunity exists
        # ---------------------------------------------------------
        if not frappe.db.exists(
            target_doctype,
            opportunity_name
        ):
            frappe.throw(
                f"{target_doctype} '{opportunity_name}' not found"
            )

        # ---------------------------------------------------------
        # Get Industry
        # ---------------------------------------------------------
        industry = frappe.db.get_value(
            target_doctype,
            opportunity_name,
            "industry"
        )

        # ---------------------------------------------------------
        # Check duplicate application
        # ---------------------------------------------------------
        existing = frappe.db.exists(
            "Student Applications",
            {
                "student": student,
                "opportunity_type": opportunity_type,
                target_fieldname: opportunity_name
            }
        )

        if existing:
            frappe.throw(
                "You have already applied for this opportunity"
            )

        # ---------------------------------------------------------
        # Create Application
        # ---------------------------------------------------------
        doc = frappe.new_doc("Student Applications")

        doc.student = student
        doc.opportunity_type = opportunity_type

        # Set Project / Internship / Job Profile
        doc.set(
            target_fieldname,
            opportunity_name
        )

        doc.industry = industry
        doc.applied_on = now_datetime()
        doc.status = "Applied"

        if resume:
            doc.resume = resume

        if notes:
            doc.notes = notes

        doc.insert(ignore_permissions=True)
        frappe.db.commit()

        # ---------------------------------------------------------
        # Remaining applications
        # ---------------------------------------------------------
        remaining = MAX_APPLICATIONS - (
            current_count + 1
        )

        return {
            "status": 200,
            "message": "Application submitted successfully",
            "application_id": doc.name,
            "student": student,
            "opportunity_type": opportunity_type,
            "opportunity_name": opportunity_name,
            "industry": industry,
            "status": doc.status,
            "applications_used": current_count + 1,
            "applications_remaining": remaining
        }

    except Exception as e:

        frappe.log_error(
            frappe.get_traceback(),
            "Apply Opportunity API Error"
        )

        return {
            "status": 500,
            "message": str(e)
        }




@frappe.whitelist(allow_guest=True)
def get_applications(
    name=None,
    opportunity_type=None,
    internship=None,
    project=None,
    job_profile=None,
    student=None,
    industry=None
):
    try:
        filters = []
        values = {}

        if name:
            filters.append("sa.name = %(name)s")
            values["name"] = name

        if opportunity_type:
            filters.append("sa.opportunity_type = %(opportunity_type)s")
            values["opportunity_type"] = opportunity_type

        if internship:
            filters.append("sa.internship = %(internship)s")
            values["internship"] = internship

        if project:
            filters.append("sa.project = %(project)s")
            values["project"] = project

        if job_profile:
            filters.append("sa.job_profile = %(job_profile)s")
            values["job_profile"] = job_profile

        if student:
            filters.append("sa.student = %(student)s")
            values["student"] = student

        if industry:
            filters.append("sa.industry = %(industry)s")
            values["industry"] = industry

        where_clause = ""

        if filters:
            where_clause = "WHERE " + " AND ".join(filters)

        applications = frappe.db.sql(
            f"""
            SELECT
                sa.name,
                sa.student,
                sa.opportunity_type,
                sa.project,
                sa.internship,
                sa.job_profile,
                sa.industry,
                sa.status,
                sa.applied_on,
                sa.match_score,

                -- Student fields
                s.first_name,
                s.last_name,
                s.email_id,
                s.mobile_no,
                s.course,
                s.department,
                s.resume

            FROM `tabStudent Applications` sa

            LEFT JOIN `tabStudent` s
                ON s.name = sa.student

            {where_clause}

            ORDER BY sa.creation DESC
            """,
            values,
            as_dict=True
        )

        return {
            "status": 200,
            "message": "Applications fetched successfully",
            "data": applications
        }

    except Exception as e:
        frappe.log_error(
            frappe.get_traceback(),
            "Get Applications API Error"
        )

        return {
            "status": 500,
            "message": str(e),
            "data": []
        }



@frappe.whitelist(allow_guest=True)
def get_applications_count(
    name=None,
    opportunity_type=None,
    internship=None,
    project=None,
    job_profile=None,
    student=None,
    industry=None
):
    try:
        filters = []
        values = {}

        if name:
            filters.append("sa.name = %(name)s")
            values["name"] = name

        if opportunity_type:
            filters.append("sa.opportunity_type = %(opportunity_type)s")
            values["opportunity_type"] = opportunity_type

        if internship:
            filters.append("sa.internship = %(internship)s")
            values["internship"] = internship

        if project:
            filters.append("sa.project = %(project)s")
            values["project"] = project

        if job_profile:
            filters.append("sa.job_profile = %(job_profile)s")
            values["job_profile"] = job_profile

        if student:
            filters.append("sa.student = %(student)s")
            values["student"] = student

        if industry:
            filters.append("sa.industry = %(industry)s")
            values["industry"] = industry

        where_clause = ""

        if filters:
            where_clause = "WHERE " + " AND ".join(filters)

        result = frappe.db.sql(
            f"""
            SELECT
                sa.status,
                COUNT(*) AS count
            FROM `tabStudent Applications` sa

            LEFT JOIN `tabStudent` s
                ON s.name = sa.student

            {where_clause}

            GROUP BY sa.status
            """,
            values,
            as_dict=True
        )

        # All application statuses with default count 0
        data = {
            "Applied": 0,
            "Shortlisted": 0,
            "Tech Interview": 0,
            "HR": 0,
            "Selected": 0,
            "Rejected": 0,
            "Withdrawn": 0,
            "Completed": 0,
            "Accepted": 0
        }

        # Update counts from database
        for row in result:
            if row.status in data:
                data[row.status] = row.count

        return {
            "status": 200,
            "message": "Application count fetched successfully",
            "data": data
        }

    except Exception as e:
        frappe.log_error(
            frappe.get_traceback(),
            "Get Applications Count API Error"
        )

        return {
            "status": 500,
            "message": str(e),
            "data": {}
        }



@frappe.whitelist(allow_guest=True)
def get_all_dropdown_data(opportunity_type=None, industry=None):
    """
    Return dropdown data based on opportunity type and industry.
    """

    try:
        if not opportunity_type:
            return {
                "status": 400,
                "message": "Opportunity type is required",
                "data": []
            }

        if not industry:
            return {
                "status": 400,
                "message": "Industry is required",
                "data": []
            }

        filters = {
            "industry": industry
        }

        if opportunity_type == "Internship":

            data = frappe.get_all(
                "Internship",
                filters=filters,
                fields=[
                    "name",
                    "title"
                ],
                order_by="creation desc"
            )

        elif opportunity_type == "Project":

            data = frappe.get_all(
                "Industry Project",
                filters=filters,
                fields=[
                    "name",
                    "project_name"
                ],
                order_by="creation desc"
            )

        elif opportunity_type == "Job":

            data = frappe.get_all(
                "Industry Job Profile",
                filters=filters,
                fields=[
                    "name",
                    "job_title"
                ],
                order_by="creation desc"
            )

        else:
            return {
                "status": 400,
                "message": "Invalid opportunity type. Allowed values: Project, Internship, Job",
                "data": []
            }

        return {
            "status": 200,
            "message": "Dropdown data fetched successfully",
            "data": data
        }

    except Exception as e:
        frappe.log_error(
            frappe.get_traceback(),
            "Get All Dropdown Data API Error"
        )

        return {
            "status": 500,
            "message": str(e),
            "data": []
        }



@frappe.whitelist(allow_guest=True)
def update_application_status(name, status):
    try:
        # session_user = frappe.session.user

        # Check permission
        # if not frappe.has_permission(
        #     "Student Applications",
        #     ptype="write",
        #     user=session_user
        # ):
        #     frappe.throw(
        #         "You do not have permission to update Student Applications.",
        #         frappe.PermissionError
        #     )

        # Validate application name
        if not name:
            return gen_response(
                status=400,
                message="Application name is required",
                data={"success": False}
            )

        # Validate status
        if not status:
            return gen_response(
                status=400,
                message="Status is required",
                data={"success": False}
            )

        # Check application exists
        if not frappe.db.exists("Student Applications", name):
            return gen_response(
                status=404,
                message="Student Applications not found",
                data={"success": False}
            )

        # Get application
        doc = frappe.get_doc("Student Applications", name)

        # Update status
        doc.status = status
        doc.save(ignore_permissions=True)
        frappe.db.commit()

        # ----------------------------------------------------------------
        # Auto-endorse skills when a Project / Internship is Accepted
        # ----------------------------------------------------------------
        endorsements_created = []
        if (
            status == "Accepted"
            and doc.opportunity_type in ("Project", "Internship")
        ):
            endorsements_created = _auto_endorse_skills(doc)

        return gen_response(
            status=200,
            message="Application status updated successfully",
            data={
                "success": True,
                "name": doc.name,
                "status": doc.status,
                "endorsements_created": endorsements_created
            }
        )

    except Exception as e:
        frappe.log_error(
            frappe.get_traceback(),
            "update_application_status"
        )

        return exception_handel(e)


# -----------------------------------------------------------------------
# Private helpers
# -----------------------------------------------------------------------

def _auto_endorse_skills(app_doc):
    """
    For an Accepted Project / Internship application, fetch the required
    skills from the linked opportunity, intersect with the student's
    Student Skill ledger, and create one Skill Endorsement
    (endorser_role='Industry') per matching skill.

    Duplicate endorsements (same endorser_company + student_skill) are
    caught and skipped silently.

    Returns a list of dicts describing the created endorsements.
    """

    student          = app_doc.student
    opportunity_type = app_doc.opportunity_type
    industry         = app_doc.industry   # name in 'Industry list'

    # ------------------------------------------------------------------
    # 1. Map opportunity type -> child-table doctype + field names
    # ------------------------------------------------------------------
    if opportunity_type == "Project":
        opp_name    = app_doc.project
        opp_dt      = "Industry Project"
        skill_child = "Student Skill Table"      # child table for Project
        has_level   = True
    elif opportunity_type == "Internship":
        opp_name    = app_doc.internship
        opp_dt      = "Internship"
        skill_child = "Internship Required Skill"  # child table for Internship
        has_level   = False
    else:
        return []

    if not opp_name:
        return []

    # ------------------------------------------------------------------
    # 2. Read required skills from the opportunity
    # ------------------------------------------------------------------
    fields = ["skill", "level"] if has_level else ["skill"]

    required_skills = frappe.get_all(
        skill_child,
        filters={"parent": opp_name, "parenttype": opp_dt},
        fields=fields,
        ignore_ifnull=True,
    )

    if not required_skills:
        return []

    required_skill_ids = {
        row["skill"] for row in required_skills if row.get("skill")
    }

    # Build skill -> required level map (Project only)
    required_level_map = {}
    if has_level:
        for row in required_skills:
            if row.get("skill") and row.get("level"):
                required_level_map[row["skill"]] = row["level"]

    # ------------------------------------------------------------------
    # 3. Fetch student's existing Student Skill records for matching skills
    # ------------------------------------------------------------------
    student_skills = frappe.get_all(
        "Student Skill",
        filters={
            "student": student,
            "skill":   ["in", list(required_skill_ids)],
        },
        fields=["name", "skill", "current_level"],
    )

    if not student_skills:
        return []

    # ------------------------------------------------------------------
    # 4. Resolve endorsed_by user — fall back to Administrator
    # ------------------------------------------------------------------
    endorsed_by = (
        frappe.db.get_value("Industry list", industry, "email")
        or "Administrator"
    )

    # ------------------------------------------------------------------
    # 5. Create one Skill Endorsement per matched student skill
    # ------------------------------------------------------------------
    created = []

    for ss in student_skills:
        skill_name = ss["skill"]

        # Prefer the required level from the opportunity;
        # fall back to the student's current claimed level.
        endorsed_level = (
            required_level_map.get(skill_name)
            or ss.get("current_level")
            or "Beginner"
        )

        try:
            endorsement = frappe.get_doc({
                "doctype":          "Skill Endorsement",
                "student_skill":    ss["name"],
                "endorsed_level":   endorsed_level,
                "endorsed_by":      endorsed_by,
                "endorser_role":    "Industry",
                "endorser_company": industry,
                "endorsed_at":      now_datetime(),
                # Track which opportunity generated this endorsement.
                # The duplicate-check in SkillEndorsement._prevent_duplicate
                # uses (student_skill + endorser_company + source_name), so
                # the same company can endorse the same skill once per
                # opportunity (Project, Internship, etc.).
                "source_doctype":   opp_dt,
                "source_name":      opp_name,
                "comment": (
                    f"Auto-endorsed on acceptance of "
                    f"{opportunity_type} '{opp_name}'."
                ),
            })
            endorsement.insert(ignore_permissions=True)
            frappe.db.commit()

            created.append({
                "skill":          skill_name,
                "student_skill":  ss["name"],
                "endorsement":    endorsement.name,
                "endorsed_level": endorsed_level,
            })

        except frappe.DuplicateEntryError:
            # Same company already endorsed this skill for this exact
            # opportunity — skip silently and continue with next skill.
            frappe.db.rollback()

        except Exception:
            frappe.log_error(
                frappe.get_traceback(),
                f"Auto-Endorse Skill Error — student={student} skill={skill_name}"
            )
            frappe.db.rollback()

    return created

