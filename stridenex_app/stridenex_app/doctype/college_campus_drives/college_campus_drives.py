# Copyright (c) 2026, QTPL and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import now_datetime, getdate
from stridenex_app.api_stridenex_app.app_utils import (
    
    get_pagination_params,
  
    make_pagination_meta,
)
from frappe import _
from frappe.utils import get_url, format_datetime
from frappe.desk.doctype.notification_log.notification_log import enqueue_create_notification
from stridenex_app.api_stridenex_app.app_utils import (
    gen_response,
    exception_handel,
    
)

CACHE_TTL = 300
DEFAULT_PAGE_SIZE = 20

def resolve_college_name(college):
    if not college:
        return college
    if "@" in college:
        resolved = frappe.db.get_value("College", {"email": college}, "name")
        if resolved:
            return resolved
    return college

class CollegeCampusDrives(Document):
    
    def autoname(self):
        if self.industry_name and self.drive_date:
            drive_date = getdate(self.drive_date)
            base_name = f"{self.industry_name}-{drive_date.strftime('%b %d %Y')}"

            if frappe.db.exists("College Campus Drives", base_name):
                count = 1
                while frappe.db.exists(
                    "College Campus Drives",
                    f"{base_name}-{count}"
                ):
                    count += 1
                self.name = f"{base_name}-{count}"
            else:
                self.name = base_name
                
    def after_insert(self):
        # Skip if the create_drive() API flagged this insert to handle
        # notifications explicitly (post-commit, as Administrator).
        if getattr(self.flags, "skip_notify_on_insert", False):
            return
        self.notify_students()

    def on_submit(self):
        self.notify_students()

    def notify_students(self):
        """Send Frappe system notifications to all matching students of this college."""
        # Prevent duplicate notifications for the same drive
        if frappe.db.exists("Notification Log", {
            "document_type": self.doctype,
            "document_name": self.name
        }):
            frappe.log_error(
                title="College Campus Drive Notification (skipped)",
                message=f"Notification already sent for drive {self.name}. Skipping duplicate."
            )
            return

        student_users = self.get_matching_student_users()
        if not student_users:
            frappe.log_error(
                title="College Campus Drive Notification",
                message=f"No matching student users found for drive {self.name} (College: {self.college})"
            )
            return

        company = self.industry_name or self.industry or "N/A"
        subject = _("New Campus Placement Drive: {0} at {1}").format(self.job_title or "N/A", company)

        details = []
        if self.job_title:
            details.append(f"Job Title: {self.job_title}")
        details.append(f"Company: {company}")
        if self.drive_date:
            details.append(f"Drive Date: {format_datetime(self.drive_date)}")
        if self.registeration_deadline:
            details.append(f"Registration Deadline: {format_datetime(self.registeration_deadline)}")
        if self.package_offered:
            details.append(f"Package Offered: {self.package_offered}")
        if self.criteria:
            details.append(f"Eligibility Criteria: {self.criteria} CGPA")
        if self.backlog is not None:
            details.append(f"Max Backlogs Allowed: {self.backlog}")

        email_content = _("A new campus placement drive has been announced.\n\n{0}").format("\n".join(details))

        # Always use Administrator as the sender so Guest-session API calls
        # never produce invalid notification authors.
        from_user = self.owner if (self.owner and self.owner != "Guest") else "Administrator"

        notification_doc = frappe._dict({
            "type": "Alert",
            "document_type": self.doctype,
            "document_name": self.name,
            "subject": subject,
            "from_user": from_user,
            "email_content": email_content,
        })

        try:
            enqueue_create_notification(student_users, notification_doc)
            frappe.log_error(
                title="College Campus Drive Notification (sent)",
                message=(
                    f"Drive: {self.name} | College: {self.college} | "
                    f"Recipients: {len(student_users)} | Users: {student_users[:10]}"
                )
            )
        except Exception as notify_err:
            frappe.log_error(
                title="College Campus Drive Notification (failed)",
                message=(
                    f"Drive: {self.name} | College: {self.college} | "
                    f"Error: {notify_err}\n{frappe.get_traceback()}"
                )
            )

    def get_matching_student_users(self):
        """Fetch emails of enabled student users belonging to this college."""
        college = resolve_college_name(self.college)
        if not college:
            frappe.log_error(
                title="College Campus Drive Notification",
                message=f"Drive {self.name}: college field is empty after resolve."
            )
            return []

        users = frappe.db.sql_list(
            """
            SELECT DISTINCT u.email
            FROM `tabUser` u
            INNER JOIN `tabHas Role` hr ON hr.parent = u.name
            INNER JOIN `tabStudent` s ON s.email_id = u.email
            WHERE u.enabled = 1
              AND s.college = %s
              AND hr.role IN ('Student', 'Student Base', 'Student Pro', 'Student lite')
            """,
            (college,),
        )
        frappe.log_error(
            title="Campus Drive Student Lookup",
            message=f"Drive: {self.name} | College: '{college}' | Found {len(users)} student users."
        )
        return users

    def send_drive_email(self, student):
        if not student.get("email_id"):
            frappe.log_error(
                title="College Campus Drive Mail",
                message=f"No email found for student {student.get('name')} (Drive: {self.name})"
            )
            return

        record_url = get_url(f"/app/college-campus-drives/{self.name}")

        subject = _("New Placement Drive: {0} - {1}").format(
            self.industry_name or self.industry, self.job_title
        )

        message = f"""
        <div style="margin:0;padding:0;background:#f6f6f8;font-family:'Inter',-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;">
            <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background:#f6f6f8;padding:30px 15px;">
                <tr>
                    <td align="center">

                        <table role="presentation" width="100%" cellspacing="0" cellpadding="0"
                            style="max-width:650px;background:#ffffff;border:1px solid #e2e8f0;border-radius:16px;overflow:hidden;">

                            <!-- Header -->
                            <tr>
                                <td style="background:#0f0fbd;padding:30px;text-align:center;">
                                    <h1 style="margin:0;color:#ffffff;font-size:26px;font-weight:700;">
                                        🚀 New Campus Placement Drive
                                    </h1>
                                    <p style="margin:8px 0 0;color:#dbeafe;font-size:14px;">
                                        Exciting career opportunity waiting for you
                                    </p>
                                </td>
                            </tr>

                            <!-- Body -->
                            <tr>
                                <td style="padding:32px;">

                                    <p style="margin:0 0 20px;color:#1E293B;font-size:16px;line-height:1.8;">
                                        Dear <strong>{student.get('student_name') or 'Student'}</strong>,
                                    </p>

                                    <p style="margin:0 0 24px;color:#1E293B;font-size:15px;line-height:1.8;">
                                        A new campus placement drive has been announced for your college.
                                        Check the details below and register before the deadline.
                                    </p>

                                    <!-- Company Highlight -->
                                    <div style="background:#eef2ff;border-left:4px solid #0f0fbd;padding:18px;border-radius:8px;margin-bottom:24px;">
                                        <p style="margin:0;color:#1E293B;font-size:15px;line-height:1.8;">
                                            <strong>🏢 Company:</strong> {self.industry_name or self.industry}<br>
                                            <strong>💼 Job Title:</strong> {self.job_title}<br>
                                            <strong>💰 Package Offered:</strong> {self.package_offered or 'Not specified'}
                                        </p>
                                    </div>

                                    <!-- Eligibility -->
                                    <div style="background:#f8fafc;border:1px solid #e2e8f0;padding:18px;border-radius:8px;margin-bottom:24px;">
                                        <h3 style="margin:0 0 12px;color:#0f0fbd;font-size:16px;">
                                            Eligibility Criteria
                                        </h3>

                                        <p style="margin:0;color:#1E293B;font-size:14px;line-height:1.9;">
                                            <strong>🎓 Minimum CGPA:</strong> {self.criteria or 'Not specified'}<br>
                                            <strong>📚 Maximum Backlogs Allowed:</strong> {self.backlog}<br>
                                            <strong>📝 Registration Deadline:</strong> {format_datetime(self.registeration_deadline) if self.registeration_deadline else 'N/A'}<br>
                                            <strong>📅 Drive Date:</strong> {format_datetime(self.drive_date) if self.drive_date else 'N/A'}
                                        </p>
                                    </div>

                                    <!-- CTA -->
                                    <div style="text-align:center;margin:30px 0;">
                                        <a href="{record_url}"
                                        style="background:#ff6b00;color:#ffffff;text-decoration:none;
                                                padding:14px 30px;border-radius:8px;
                                                font-size:15px;font-weight:600;display:inline-block;">
                                            Register Now →
                                        </a>
                                    </div>

                                    <!-- Note -->
                                    <div style="background:#fff7ed;border-left:4px solid #ff6b00;padding:16px 18px;border-radius:8px;">
                                        <p style="margin:0;color:#9a3412;font-size:14px;line-height:1.8;">
                                            Don't miss this opportunity. Complete your registration before the deadline to participate in the placement process.
                                        </p>
                                    </div>

                                </td>
                            </tr>

                            <!-- Footer -->
                            <tr>
                                <td style="background:#0F172A;padding:24px;text-align:center;">
                                    <p style="margin:0;color:#ffffff;font-size:15px;font-weight:600;">
                                        StrideNex Placement Cell
                                    </p>

                                    <p style="margin:10px 0 0;color:#94a3b8;font-size:13px;">
                                        Connecting Students with Career Opportunities
                                    </p>

                                    <div style="margin-top:16px;padding-top:16px;border-top:1px solid #334155;">
                                        <p style="margin:0;color:#94a3b8;font-size:12px;">
                                            This notification was sent automatically by StrideNex.
                                        </p>
                                    </div>
                                </td>
                            </tr>

                        </table>

                    </td>
                </tr>
            </table>
        </div>
        """

        frappe.sendmail(
            recipients=[student["email_id"]],
            subject=subject,
            message=message,
            reference_doctype=self.doctype,
            reference_name=self.name,
        )

    def send_drive_notification(self, student_user):
        notification_doc = frappe._dict({
            "type": "Alert",
            "document_type": self.doctype,
            "document_name": self.name,
            "subject": _("New Drive: {0} at {1}").format(self.job_title, self.industry_name or self.industry),
            "from_user": frappe.session.user,
            "email_content": _("Registration deadline: {0}").format(
                format_datetime(self.registeration_deadline) if self.registeration_deadline else "N/A"
            ),
        })
        enqueue_create_notification([student_user], notification_doc)

@frappe.whitelist(allow_guest=True)
def get_drives_by_college(college, page=1, page_size=DEFAULT_PAGE_SIZE):
    try:
        page, page_size, limit, offset = get_pagination_params(page, page_size)

        if not college:
            return {"status": 400, "message": "College is required"}

        college = resolve_college_name(college)
        filters = {"college": college}
        total   = frappe.db.count("College Campus Drives", filters=filters)

        industries = frappe.get_all(
            "College Campus Drives",
            filters=filters,
            fields=["name"],
            limit=limit,
            start=offset,
        )

        # ── Fetch all drive names in one shot for bulk SQL queries ────────
        drive_names = [item.name for item in industries]

        if not drive_names:
            return {
                "status": 200,
                "message": "College Drives fetched successfully",
                "data": {"campus_drives": [], "pagination": make_pagination_meta(total, page, page_size)},
            }

        placeholders = ", ".join(["%s"] * len(drive_names))

      

        # ── Application counts per drive (shortlisted + placed) ───────────
        app_rows = frappe.db.sql(f"""
            SELECT
                cda.drive                           AS drive,
                COUNT(cda.name)                     AS total_applications,
                SUM(CASE WHEN cda.status = 'Shortlisted' THEN 1 ELSE 0 END) AS shortlisted,
                SUM(CASE WHEN cda.status = 'Selected'    THEN 1 ELSE 0 END) AS placed
            FROM `tabCampus Drive Application` cda
            WHERE cda.drive IN ({placeholders})
            GROUP BY cda.drive
        """, drive_names, as_dict=True)

        # ── Index by drive name for O(1) lookup ───────────────────────────
       
        app_map      = {r.drive: r                   for r in app_rows}

        result = []
        for item in industries:
            doc  = frappe.get_doc("College Campus Drives", item.name)
            apps = app_map.get(doc.name, {})

            data = {
                "name":                   doc.name,
                "industry_name":          doc.industry_name,
                "registeration_deadline": doc.registeration_deadline,
                "drive_date":             doc.drive_date,
                "package_offered":        doc.package_offered,
                "backlog":                doc.backlog,
                "criteria":               doc.criteria,
                "role":                   doc.role,
                "job_title":              doc.job_title,

                # ── NEW counts ────────────────────────────────────────────
            
                "total_applications":     apps.get("total_applications", 0),
                "shortlisted":            apps.get("shortlisted", 0),
                "placed":                 apps.get("placed", 0),

                "designation": [
                    {"name": row.name, "designation": row.designation}
                    for row in doc.designation
                ],
                "branches": [
                    {"branch_name": row.branch_name}
                    for row in doc.branches
                ],
                "required_skill": [
                    {"skill": row.skill}
                    for row in doc.required_skill
                ],
            }
            result.append(data)

        return {
            "status": 200,
            "message": "College Drives fetched successfully",
            "data": {
                "campus_drives": result,
                "pagination": make_pagination_meta(total, page, page_size),
            },
        }

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Get Drives Error")
        return {"status": 500, "message": str(e)}
    

@frappe.whitelist(allow_guest=True)
def get_campus_drive_list(
    college=None,
    student=None,
    required_skill=None,
    backlog=None,
    criteria=None
):
    try:
        # ----------------------------------------------------------
        # PERMISSION CHECK
        # ----------------------------------------------------------
        # session_user = frappe.session.user
        # if not frappe.has_permission(
        #     "College Campus Drives",
        #     ptype="read",
        #     user=session_user
        # ):
        #     frappe.throw(
        #         "You do not have permission to access College Campus Drives.",
        #         frappe.PermissionError
        #     )

        filters = {}

        if college:
            college = resolve_college_name(college)
            filters["college"] = college

        

        drive_names = None

        # Required skill filter (child table: Student Skill Table)
        if required_skill:
            names = frappe.get_all(
                "Student Skill Table",
                filters={"skill": required_skill},
                pluck="parent"
            )
            drive_names = set(names)

        # Apply child-table filter to parent query
        if drive_names is not None:
            if drive_names:
                filters["name"] = ["in", list(drive_names)]
            else:
                return gen_response(
                    status=200,
                    message="No campus drives found",
                    data=[]
                )

        drives = frappe.get_all(
            "College Campus Drives",
            filters=filters,
            fields=[
                "name", "creation", "owner", "job_title", "college",
                "industry_name", "industry", "registeration_deadline",
                "drive_date", "package_offered", "backlog", "criteria"
            ],
            order_by="creation desc"
        )

        drive_names_list = [d["name"] for d in drives]

        # ✅ Required skills mapping
        all_skills = frappe.get_all(
            "Student Skill Table",
            filters={"parent": ["in", drive_names_list]},
            fields=["parent", "skill"]
        )
        skill_map = {}
        for s in all_skills:
            skill_map.setdefault(s["parent"], []).append({"skill": s["skill"]})

        
        # ✅ Application status mapping (Campus Drive Application)
        ALL_STATUSES = ["Applied", "Shortlisted", "Selected", "Rejected"]
        status_counts = {"Not Applied": 0}
        status_counts.update({status: 0 for status in ALL_STATUSES})

        enrollment_map = {}

        if student:
            applications = frappe.get_all(
                "Campus Drive Application",
                filters={"student": student},
                fields=[
                    "name", "drive", "college", "application_date",
                    "status", "package_lpa", "offer_letter",
                    "selection_id", "remarks"
                ],
                order_by="application_date desc"
            )

            for app in applications:
                if not app.drive:
                    continue

                enrollment_map[app.drive] = {
                    "application_name": app.name,
                    "status": app.status,
                    "application_date": app.application_date,
                    "package_lpa": app.package_lpa,
                    "offer_letter": app.offer_letter,
                    "selection_id": app.selection_id,
                    "remarks": app.remarks
                }

        # ✅ Fetch student CGPA once if criteria filter is requested
        student_cgpa = None
        if criteria and student:
            student_cgpa = frappe.db.get_value("Student", student, "cgpa")
            try:
                student_cgpa = float(student_cgpa) if student_cgpa not in (None, "") else None
            except (TypeError, ValueError):
                student_cgpa = None
        elif criteria and not student:
            try:
                student_cgpa = float(criteria)
            except (TypeError, ValueError):
                student_cgpa = None

        # ✅ Fetch student backlog count once if backlog filter is requested
        student_backlog = None
        if backlog is not None and student:
            student_backlog = frappe.db.get_value("Student", student, "backlog")
            try:
                student_backlog = int(student_backlog) if student_backlog not in (None, "") else 0
            except (TypeError, ValueError):
                student_backlog = 0
        elif backlog is not None and not student:
            try:
                student_backlog = int(backlog)
            except (TypeError, ValueError):
                student_backlog = None

        result = []
        now = now_datetime()

        for drive in drives:
            # ---- Eligibility filter: backlog ----
            if student_backlog is not None:
                try:
                    drive_backlog_allowed = int(drive.get("backlog") or 0)
                except (TypeError, ValueError):
                    drive_backlog_allowed = 0
                if drive_backlog_allowed < student_backlog:
                    continue  # student's backlog count exceeds what this drive allows

            # ---- Eligibility filter: criteria (CGPA) ----
            if student_cgpa is not None:
                raw_criteria = drive.get("criteria")
                try:
                    drive_min_cgpa = float(raw_criteria) if raw_criteria not in (None, "") else None
                except (TypeError, ValueError):
                    drive_min_cgpa = None

                if drive_min_cgpa is not None and student_cgpa < drive_min_cgpa:
                    continue  # student doesn't meet minimum CGPA for this drive

            drive["required_skill"] = skill_map.get(drive["name"], [])

            if student:
                application_info = enrollment_map.get(drive["name"])
                if application_info:
                    current_status = application_info["status"] or "Applied"
                    drive["applied_status"] = current_status
                    drive["application_details"] = application_info
                else:
                    current_status = "Not Applied"
                    drive["applied_status"] = current_status
                    drive["application_details"] = None
            else:
                current_status = "Not Applied"
                drive["applied_status"] = current_status
                drive["application_details"] = None

            # ---- Filter: Expired / Past drives ----
            # Show only drives where registration deadline (or drive date) is in the future,
            # OR if the student has already applied to it (so they can track status).
            has_expired = False
            if drive.get("registeration_deadline"):
                if frappe.utils.get_datetime(drive.get("registeration_deadline")) < now:
                    has_expired = True
            if drive.get("drive_date"):
                if frappe.utils.get_datetime(drive.get("drive_date")) < now:
                    has_expired = True

            is_applied = current_status in ["Applied", "Shortlisted", "Selected", "Rejected"]

            if has_expired and not is_applied:
                continue

            drive["status"] = "Closed" if has_expired else "Registrations Open"

            status_counts[current_status] = status_counts.get(current_status, 0) + 1
            result.append(drive)

        return gen_response(
            status=200,
            message="Campus drive list fetched successfully",
            data={
                "drives": result,
                "statistics": {
                    "total_drives": len(result),
                    "status_counts": status_counts
                }
            }
        )
    except Exception as e:
        return exception_handel(e)
    
@frappe.whitelist(allow_guest=True)
def create_drive():
    try:
        data = frappe.request.get_json()
        if not data:
            return {"status": 400, "message": "Request body is required"}

        doc = frappe.new_doc("College Campus Drives")
        doc.college = resolve_college_name(data.get("college"))
        doc.industry_name = data.get("industry_name")
        doc.registeration_deadline = data.get("registeration_deadline")
        doc.drive_date = data.get("drive_date")
        doc.package_offered = data.get("package_offered")
        doc.backlog = data.get("backlog")
        doc.criteria = data.get("criteria")
        doc.role = data.get("role")
        doc.job_title = data.get("job_title")

        for d in data.get("designation", []):
            doc.append("designation", {
                "designation": d.get("designation")
            })

        # Branches
        doc.set("branches", [])
        for row in data.get("branches", []):
            if isinstance(row, dict):
                doc.append("branches", {
                    "branch_name": row.get("branch_name")
                })

        # Required Skills
        doc.set("required_skill", [])
        for row in data.get("required_skill", []):
            if isinstance(row, dict):
                doc.append("required_skill", {
                    "skill": row.get("skill")
                })

        # insert() fires after_insert which also calls notify_students.
        # We pass flags so after_insert can detect this API path and skip
        # the notification — we'll call it explicitly after commit instead.
        doc.flags.skip_notify_on_insert = True
        doc.insert(ignore_permissions=True)

        # ── Commit FIRST so the document is visible to background workers ──
        frappe.db.commit()

        # ── Now dispatch notifications as Administrator (not Guest) ──────
        try:
            notify_drive_students(doc.name)
        except Exception as notify_err:
            # Log but don't fail the API response
            frappe.log_error(
                title="create_drive: notification dispatch failed",
                message=f"Drive: {doc.name} | Error: {notify_err}\n{frappe.get_traceback()}"
            )

        return {
            "status": 200,
            "message": "Drive created successfully",
            "name": doc.name,
        }

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "create_drive Error")
        return {"status": 500, "message": str(e)}


def notify_drive_students(drive_name):
    """
    Standalone post-commit notification dispatcher.
    Runs as Administrator so system notifications are always valid.
    Called explicitly after db.commit() in create_drive() to ensure
    the document is fully persisted before background workers read it.
    """
    if not drive_name:
        return

    # Switch to Administrator context so 'from_user' is never 'Guest'
    original_user = frappe.session.user
    frappe.set_user("Administrator")
    try:
        doc = frappe.get_doc("College Campus Drives", drive_name)
        doc.notify_students()
    finally:
        frappe.set_user(original_user)

@frappe.whitelist(allow_guest=True)
def update_drive(name):
    try:
        data = frappe.request.get_json()

        if not name:
            return {"status": 400, "message": "Drive name is required"}

        doc = frappe.get_doc("College Campus Drives", name)

        doc.college = resolve_college_name(data.get("college", doc.college))
        doc.industry_name = data.get("industry_name", doc.industry_name)
        doc.registeration_deadline = data.get("registeration_deadline", doc.registeration_deadline)
        doc.drive_date = data.get("drive_date", doc.drive_date)
        doc.package_offered = data.get("package_offered", doc.package_offered)
        doc.backlog = data.get("backlog", doc.backlog)
        doc.criteria = data.get("criteria", doc.criteria)
        doc.job_title = data.get("job_title", doc.job_title)

        if "designation" in data:
            doc.set("designation", [])
            for d in data.get("designation", []):
                doc.append("designation", {
                    "designation": d.get("designation")
                })

        if "branches" in data:
            doc.set("branches", [])
            for d in data.get("branches", []):  # FIXED: was data.get("department", [])
                doc.append("branches", {        # FIXED: was doc.append("department", ...)
                    "branch_name": d.get("branch_name")  # FIXED: was d.get("name")
                })

        if "required_skill" in data:            # FIXED: was missing entirely
            doc.set("required_skill", [])
            for d in data.get("required_skill", []):
                doc.append("required_skill", {
                    "skill": d.get("skill")
                })

        doc.save(ignore_permissions=True)
        frappe.db.commit()

        return {
            "status": 200,
            "message": "Drive updated successfully",
        }

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Update Drive Error")
        return {"status": 500, "message": str(e)}

@frappe.whitelist(allow_guest=True)
def delete_drive(name):
    try:
        if not name:
            return {"status": 400, "message": "Drive name is required"}

        frappe.delete_doc("College Campus Drives", name, ignore_permissions=True)
        frappe.db.commit()

        return {
            "status": 200,
            "message": "Drive deleted successfully",
        }

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Delete Drive Error")
        return {"status": 500, "message": str(e)}


@frappe.whitelist(allow_guest=True)
def get_drive_count(college=None):
    try:
        if college:
            college = resolve_college_name(college)
        # Base filters
        base_filters = {}
        if college:
            base_filters["college"] = college

        # 1. Total drives under college
        total_drives = frappe.db.count("College Campus Drives", base_filters)

        # 2. Upcoming drives (registration deadline not passed)
        upcoming_filters = {
            "registeration_deadline": (">=", now_datetime())
        }
        if college:
            upcoming_filters["college"] = college
        upcoming_drives = frappe.db.count("College Campus Drives", upcoming_filters)

        # 3. Total registered (applied) students across all drives under college
        if college:
            registered = frappe.db.sql("""
                SELECT COUNT(*)
                FROM `tabCampus Drive Application` cda
                INNER JOIN `tabCollege Campus Drives` d
                    ON d.name = cda.drive
                WHERE d.college = %s
            """, (college,))[0][0]
        else:
            registered = frappe.db.count("Campus Drive Application", {})

        # 4. Placed (Selected) students across all drives under college
        if college:
            placed = frappe.db.sql("""
                SELECT COUNT(*)
                FROM `tabCampus Drive Application` cda
                INNER JOIN `tabCollege Campus Drives` d
                    ON d.name = cda.drive
                WHERE d.college = %s
                AND cda.status = 'Selected'
            """, (college,))[0][0]
        else:
            placed = frappe.db.count("Campus Drive Application", {"status": "Selected"})

        return {
            "status": 200,
            "message": "Drive count fetched successfully",
            "data": {
                "total_drives": total_drives,
                "upcoming_drives": upcoming_drives,
                "total_registered": registered,
                "total_placed": placed
            }
        }

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Drive Count Error")
        return {"status": 500, "message": str(e)}




@frappe.whitelist(allow_guest=True)
def get_drive_count_by_name(name=None, status=None):
    try:
        filters = {}

        if name:
            filters["name"] = name

        if status:
            status_list = [s.strip() for s in status.split(",")]
            filters["status"] = ["in", status_list]

        # TODO: confirm the correct doctype — likely "Campus Drive Application" or similar
        count = frappe.db.count("College Campus Drives", filters)

        return {
            "status": 200,
            "message": "Drive count fetched successfully",
            "count": count,
        }

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Drive Count Error")
        return {"status": 500, "message": str(e)}


@frappe.whitelist()
def get_placement_stats(college=None):
    try:
        if college:
            college = resolve_college_name(college)
        base = "AND d.college = %s" if college else ""
        base_vals = [college] if college else []

        # ── 1. Placement Rate ─────────────────────────────────────────────
        total_students = frappe.db.sql(f"""
            SELECT COUNT(*) FROM `tabStudent` s
            WHERE 1=1 {"AND s.college = %s" if college else ""}
        """, base_vals)[0][0]

        placed_students = frappe.db.sql(f"""
            SELECT COUNT(DISTINCT cda.student)
            FROM `tabCampus Drive Application` cda
            INNER JOIN `tabCollege Campus Drives` d ON d.name = cda.drive
            WHERE cda.status = 'Selected' {base}
        """, base_vals)[0][0]

        placement_rate = round((placed_students / total_students * 100), 1) if total_students else 0

        # ── 2. Average CTC ────────────────────────────────────────────────
        avg_ctc = frappe.db.sql(f"""
            SELECT ROUND(AVG(cda.package_lpa), 1)
            FROM `tabCampus Drive Application` cda
            INNER JOIN `tabCollege Campus Drives` d ON d.name = cda.drive
            WHERE cda.status = 'Selected'
            AND cda.package_lpa IS NOT NULL
            AND cda.package_lpa > 0
            {base}
        """, base_vals)[0][0] or 0

        # ── 3. Highest CTC ────────────────────────────────────────────────
        highest_ctc = frappe.db.sql(f"""
            SELECT ROUND(MAX(cda.package_lpa), 1)
            FROM `tabCampus Drive Application` cda
            INNER JOIN `tabCollege Campus Drives` d ON d.name = cda.drive
            WHERE cda.status = 'Selected'
            AND cda.package_lpa IS NOT NULL
            {base}
        """, base_vals)[0][0] or 0

        # ── 4. Companies Visited ──────────────────────────────────────────
        companies_visited = frappe.db.sql(f"""
            SELECT COUNT(DISTINCT d.industry_name)
            FROM `tabCollege Campus Drives` d
            WHERE 1=1 {"AND d.college = %s" if college else ""}
        """, base_vals)[0][0]

        total_applications = frappe.db.sql(f"""
            SELECT COUNT(cda.name)
            FROM `tabCampus Drive Application` cda
            INNER JOIN `tabCollege Campus Drives` d ON d.name = cda.drive
            WHERE 1=1 {base}
        """, base_vals)[0][0]

        # ── 7. Shortlisted ────────────────────────────────────────────────
        shortlisted = frappe.db.sql(f"""
            SELECT COUNT(cda.name)
            FROM `tabCampus Drive Application` cda
            INNER JOIN `tabCollege Campus Drives` d ON d.name = cda.drive
            WHERE cda.status = 'Shortlisted' {base}
        """, base_vals)[0][0]

        placed_students = frappe.db.sql(f"""
            SELECT COUNT(DISTINCT cda.student)
            FROM `tabCampus Drive Application` cda
            INNER JOIN `tabCollege Campus Drives` d ON d.name = cda.drive
            WHERE cda.status = 'Selected' {base}
        """, base_vals)[0][0]

        

        return {
            "status": 200,
            "data": {
                "placement_rate": placement_rate,
                "average_ctc": avg_ctc,
                "highest_ctc": highest_ctc,
                "companies_visited": companies_visited,
                "total_applications": total_applications,
                "shortlisted":        shortlisted,
                "placed":             placed_students,
                
            }
        }

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "get_placement_stats Error")
        return {"status": 500, "message": str(e)}
    
@frappe.whitelist(allow_guest=True)
def get_branch_wise_performance(college=None):
        try:
            if college:
                college = resolve_college_name(college)
            base = "AND d.college = %s" if college else ""
            base_vals = [college] if college else []
        # ── 5. Department-wise Placement (Top 6) ──────────────────────────
            dept_data = frappe.db.sql(f"""
                SELECT
                    s.department                        AS department,
                    COUNT(DISTINCT s.name)              AS total_students,
                    COUNT(DISTINCT CASE
                        WHEN cda.status = 'Selected' THEN cda.student
                    END)                                AS placed_students,
                    ROUND(
                        COUNT(DISTINCT CASE WHEN cda.status = 'Selected' THEN cda.student END)
                        * 100.0 / NULLIF(COUNT(DISTINCT s.name), 0), 1
                    )                                   AS placement_rate
                FROM `tabStudent` s
                LEFT JOIN `tabCampus Drive Application` cda
                    ON cda.student = s.name
                LEFT JOIN `tabCollege Campus Drives` d
                    ON d.name = cda.drive
                WHERE s.department IS NOT NULL
                {"AND s.college = %s" if college else ""}
                GROUP BY s.department
                ORDER BY placement_rate DESC
                LIMIT 6
            """, base_vals, as_dict=True)
            return {
                "status": 200,
                "data":dept_data
            }
        except Exception as e:
            frappe.log_error(frappe.get_traceback(), "get_placement_stats Error")
            return {"status": 500, "message": str(e)}



# ── 1. PLACEMENT FUNNEL ───────────────────────────────────────────────────────
@frappe.whitelist(allow_guest=True)
def get_placement_funnel(college=None, year=None):
    try:
        if college:
            college = resolve_college_name(college)
        base_student = []
        base_app = []
        student_where = []
        app_where = []

        if college:
            student_where.append("s.college = %s")
            base_student.append(college)
            app_where.append("d.college = %s")
            base_app.append(college)

        if year:
            student_where.append("s.academic_year = %s")
            base_student.append(year)

        sw = ("WHERE " + " AND ".join(student_where)) if student_where else ""
        aw = ("WHERE " + " AND ".join(app_where)) if app_where else ""

        # 1. Final year students
        final_year_students = frappe.db.sql(f"""
            SELECT COUNT(*)
            FROM `tabStudent` s
            {sw}
        """, base_student)[0][0]

        # 2. Eligible students (employability score >= 60 i.e cgpa >= 6.0)
        eligible_where = student_where + ["s.cgpa >= 6.0"]
        eligible_vals  = base_student + []
        ew = "WHERE " + " AND ".join(eligible_where)
        eligible = frappe.db.sql(f"""
            SELECT COUNT(*)
            FROM `tabStudent` s
            {ew}
        """, eligible_vals)[0][0]

        # 3. Applications sent (all applications)
        applications_sent = frappe.db.sql(f"""
            SELECT COUNT(*)
            FROM `tabCampus Drive Application` cda
            INNER JOIN `tabCollege Campus Drives` d ON d.name = cda.drive
            {aw}
        """, base_app)[0][0]

        # 4. Shortlisted
        shortlisted_where = app_where + ["cda.status = 'Shortlisted'"]
        shortlisted_vals  = base_app + []
        shw = ("WHERE " + " AND ".join(shortlisted_where)) if shortlisted_where else "WHERE cda.status = 'Shortlisted'"
        shortlisted = frappe.db.sql(f"""
            SELECT COUNT(*)
            FROM `tabCampus Drive Application` cda
            INNER JOIN `tabCollege Campus Drives` d ON d.name = cda.drive
            {shw}
        """, shortlisted_vals)[0][0]

        # 5. Interviews done
        interviews_where = app_where + ["cda.status = 'Interview'"]
        interviews_vals  = base_app + []
        iw = ("WHERE " + " AND ".join(interviews_where)) if interviews_where else "WHERE cda.status = 'Interview'"
        interviews_done = frappe.db.sql(f"""
            SELECT COUNT(*)
            FROM `tabCampus Drive Application` cda
            INNER JOIN `tabCollege Campus Drives` d ON d.name = cda.drive
            {iw}
        """, interviews_vals)[0][0]

        # 6. Offers received (Selected)
        offers_where = app_where + ["cda.status = 'Selected'"]
        offers_vals  = base_app + []
        ow = ("WHERE " + " AND ".join(offers_where)) if offers_where else "WHERE cda.status = 'Selected'"
        offers_received = frappe.db.sql(f"""
            SELECT COUNT(*)
            FROM `tabCampus Drive Application` cda
            INNER JOIN `tabCollege Campus Drives` d ON d.name = cda.drive
            {ow}
        """, offers_vals)[0][0]

        # 7. Accepted offers (Joined)
        accepted_where = app_where + ["cda.status = 'Joined'"]
        accepted_vals  = base_app + []
        acw = ("WHERE " + " AND ".join(accepted_where)) if accepted_where else "WHERE cda.status = 'Joined'"
        accepted_offers = frappe.db.sql(f"""
            SELECT COUNT(*)
            FROM `tabCampus Drive Application` cda
            INNER JOIN `tabCollege Campus Drives` d ON d.name = cda.drive
            {acw}
        """, accepted_vals)[0][0]

        return {
            "status": 200,
            "data": {
                "funnel": [
                    {"label": "Final Year Students",    "count": final_year_students, "color": "#111827"},
                    {"label": "Eligible (Score ≥60)",   "count": eligible,            "color": "#1d4ed8"},
                    {"label": "Applications Sent",      "count": applications_sent,   "color": "#2563eb"},
                    {"label": "Shortlisted",            "count": shortlisted,         "color": "#f97316"},
                    # {"label": "Interviews Done",        "count": interviews_done,     "color": "#eab308"},
                    {"label": "Offers Received",        "count": offers_received,     "color": "#22c55e"},
                    {"label": "Accepted Offers",        "count": accepted_offers,     "color": "#16a34a"},
                ]
            }
        }

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "get_placement_funnel Error")
        return {"status": 500, "message": str(e)}


# ── 2. TOP RECRUITERS ─────────────────────────────────────────────────────────
@frappe.whitelist()
def get_top_recruiters(college=None, limit=5):
    try:
        if college:
            college = resolve_college_name(college)
        conditions = ["cda.status = 'Selected'"]
        values = []

        if college:
            conditions.append("d.college = %s")
            values.append(college)

        where_clause = "WHERE " + " AND ".join(conditions)
        values.append(int(limit))

        data = frappe.db.sql(f"""
            SELECT
                d.industry_name         AS company,
                COUNT(cda.name)         AS total_offers
            FROM `tabCampus Drive Application` cda
            INNER JOIN `tabCollege Campus Drives` d ON d.name = cda.drive
            {where_clause}
            GROUP BY d.industry_name
            ORDER BY total_offers DESC
            LIMIT %s
        """, values, as_dict=True)

        return {
            "status": 200,
            "data": data
        }

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "get_top_recruiters Error")
        return {"status": 500, "message": str(e)}


# ── 3. SALARY BANDS ───────────────────────────────────────────────────────────
@frappe.whitelist()
def get_salary_bands(college=None):
    try:
        if college:
            college = resolve_college_name(college)
        conditions = ["cda.status = 'Selected'", "cda.package_lpa IS NOT NULL", "cda.package_lpa > 0"]
        values = []

        if college:
            conditions.append("d.college = %s")
            values.append(college)

        where_clause = "WHERE " + " AND ".join(conditions)

        result = frappe.db.sql(f"""
            SELECT
                SUM(CASE WHEN cda.package_lpa < 4              THEN 1 ELSE 0 END) AS band_lt4,
                SUM(CASE WHEN cda.package_lpa BETWEEN 4 AND 8  THEN 1 ELSE 0 END) AS band_4_8,
                SUM(CASE WHEN cda.package_lpa BETWEEN 8 AND 15 THEN 1 ELSE 0 END) AS band_8_15,
                SUM(CASE WHEN cda.package_lpa > 15             THEN 1 ELSE 0 END) AS band_gt15,
                COUNT(*)                                                            AS total,
                ROUND(AVG(cda.package_lpa), 1)                                     AS average_ctc
            FROM `tabCampus Drive Application` cda
            INNER JOIN `tabCollege Campus Drives` d ON d.name = cda.drive
            {where_clause}
        """, values, as_dict=True)[0]

        total = result.total or 1  # avoid division by zero

        def pct(val):
            return round((val or 0) / total * 100, 1)

        return {
            "status": 200,
            "data": {
                "average_ctc": result.average_ctc or 0,
                "bands": [
                    {"label": "<4 LPA",   "count": result.band_lt4,  "percent": pct(result.band_lt4),  "color": "#ef4444"},
                    {"label": "4–8 LPA",  "count": result.band_4_8,  "percent": pct(result.band_4_8),  "color": "#f97316"},
                    {"label": "8–15 LPA", "count": result.band_8_15, "percent": pct(result.band_8_15), "color": "#22c55e"},
                    {"label": "15+ LPA",  "count": result.band_gt15, "percent": pct(result.band_gt15), "color": "#3b82f6"},
                ]
            }
        }

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "get_salary_bands Error")
        return {"status": 500, "message": str(e)}


@frappe.whitelist(allow_guest=True)
def get_low_employability_students(college=None, threshold=50, limit=20, offset=0):
    try:
        if college:
            college = resolve_college_name(college)
        threshold = float(threshold)
        limit = int(limit)
        offset = int(offset)

        conditions = []
        values = []
        if college:
            conditions.append("s.college = %s")
            values.append(college)

        where_clause = ("WHERE " + " AND ".join(conditions)) if conditions else ""

        # Fetch students with the stored employability_score from Student doctype
        students = frappe.db.sql(f"""
            SELECT
                s.name,
                s.first_name,
                s.last_name,
                s.email_id,
                s.mobile_no,
                s.college,
                s.department,
                s.course,
                s.academic_year,
                s.cgpa,
                COALESCE(s.employability_score, 0) AS employability_score
            FROM `tabStudent` s
            {where_clause}
        """, values, as_dict=True)

        result = []
        for s in students:
            employability_score = float(s.employability_score or 0)

            if employability_score < threshold:
                result.append({
                    "name":                s.name,
                    "student_name":        f"{s.first_name} {s.last_name}",
                    "email":               s.email_id,
                    "mobile_no":           s.mobile_no,
                    "college":             s.college,
                    "department":          s.department,
                    "course":              s.course,
                    "academic_year":       s.academic_year,
                    "cgpa":                float(s.cgpa or 0),
                    "employability_score": employability_score
                })

        result.sort(key=lambda x: x["employability_score"])
        paginated = result[offset: offset + limit]

        # Enhance paginated students with detailed scores/counts
        for p in paginated:
            cgpa = p["cgpa"]
            cgpa_score = (cgpa / 10.0) * 100
            p["cgpa_score"] = round(cgpa_score, 2)
            
            es = p["employability_score"]
            skills_score = (es - 0.3 * cgpa_score) / 0.7
            p["avg_skill_score"] = max(0.0, round(skills_score, 2))
            
            p["total_skills"] = frappe.db.count("Student Skill", {
                "student": p["name"],
                "status": ["!=", "Rejected"]
            })

        return {
            "status": 200,
            "data": {
                "students":      paginated,
                "total":         len(result),
                "threshold":     threshold,
                "limit":         limit,
                "offset":        offset,
                "score_formula": "30% CGPA (normalized to 100) + 70% Skill Fulfillment"
            }
        }

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "get_low_employability_students Error")
        return {"status": 500, "message": str(e)}

import frappe
from frappe.utils import now_datetime


@frappe.whitelist(allow_guest=True)
def apply_campus_drive(student, drive, remarks=None):
    if not student:
        frappe.throw("Student is required")

    if not drive:
        frappe.throw("Campus Drive is required")

    if not frappe.db.exists("Student", student):
        frappe.throw("Student not found", frappe.DoesNotExistError)

    if not frappe.db.exists("College Campus Drives", drive):
        frappe.throw("Campus Drive not found", frappe.DoesNotExistError)

    drive_doc = frappe.get_doc("College Campus Drives", drive)

    # block applying after the registration deadline has passed
    if drive_doc.registeration_deadline and now_datetime() > drive_doc.registeration_deadline:
        frappe.throw("Registration deadline for this drive has passed")

    # prevent duplicate applications by the same student to the same drive
    existing = frappe.db.exists(
        "Campus Drive Application",
        {"student": student, "drive": drive, "docstatus": ["!=", 2]}
    )
    if existing:
        frappe.throw(f"You have already applied to this drive (Application: {existing})")

    application = frappe.get_doc({
        "doctype": "Campus Drive Application",
        "student": student,
        "drive": drive,
        "application_date": frappe.utils.nowdate(),
        "status": "Applied",
        "remarks": remarks,
    })

    application.insert(ignore_permissions=True)
    frappe.db.commit()

    return {
        "message": "Application submitted successfully",
        "application_id": application.name,
        "status": application.status,
        "college": application.college,  # auto-fetched from drive.college
    }