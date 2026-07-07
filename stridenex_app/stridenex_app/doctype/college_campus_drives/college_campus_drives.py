# Copyright (c) 2026, QTPL and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import now_datetime, getdate
from stridenex_app.api_stridenex_app.app_utils import (
    
    get_pagination_params,
  
    make_pagination_meta,
)

CACHE_TTL = 300
DEFAULT_PAGE_SIZE = 20


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


@frappe.whitelist(allow_guest=True)
def get_drives_by_college(college, page=1, page_size=DEFAULT_PAGE_SIZE):
    try:
        page, page_size, limit, offset = get_pagination_params(page, page_size)

        if not college:
            return {"status": 400, "message": "College is required"}

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
def create_drive():
    try:
        data = frappe.request.get_json()
        if not data:
            return {"status": 400, "message": "Request body is required"}

        doc = frappe.new_doc("College Campus Drives")
        doc.college = data.get("college")
        doc.industry_name = data.get("industry_name")
        doc.registeration_deadline = data.get("registeration_deadline")
        doc.drive_date = data.get("drive_date")
        doc.package_offered = data.get("package_offered")
        doc.backlog = data.get("backlog")
        doc.criteria = data.get("criteria")
        doc.role = data.get("role")
        doc.job_title=data.get("job_title")
       

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


        doc.insert(ignore_permissions=True)
        frappe.db.commit()

        return {
            "status": 200,
            "message": "Drive created successfully",
            "name": doc.name,
        }

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "create_drive Error")
        return {"status": 500, "message": str(e)}

@frappe.whitelist(allow_guest=True)
def update_drive(name):
    try:
        data = frappe.request.get_json()

        if not name:
            return {"status": 400, "message": "Drive name is required"}

        doc = frappe.get_doc("College Campus Drives", name)

        doc.college = data.get("college", doc.college)
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
        threshold = float(threshold)
        limit = int(limit)
        offset = int(offset)

        conditions = []
        values = []
        if college:
            conditions.append("s.college = %s")
            values.append(college)

        where_clause = ("WHERE " + " AND ".join(conditions)) if conditions else ""

        # Fetch students
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
                s.cgpa
            FROM `tabStudent` s
            {where_clause}
        """, values, as_dict=True)

        # Fetch skills — field is `level` (confirmed from DESCRIBE)
        skill_rows = frappe.db.sql("""
            SELECT
                parent,
                skill,
                level
            FROM `tabStudent Skill Table`
            WHERE parenttype = 'Student'
        """, as_dict=True)

        level_scores = {
            "Beginner":     25,
            "Intermediate": 50,
            "Advanced":     75,
            "Expert":       100
        }

        # Build skill map: { student_name: [score1, score2, ...] }
        skill_map = {}
        for row in skill_rows:
            score = level_scores.get(row.level, 50)  # default 50 if blank
            if row.parent not in skill_map:
                skill_map[row.parent] = []
            skill_map[row.parent].append(score)

        result = []
        for s in students:
            cgpa = float(s.cgpa or 0)
            cgpa_normalized = (cgpa / 10.0) * 100  # CGPA out of 10

            skill_scores = skill_map.get(s.name, [])
            avg_skill_score = (sum(skill_scores) / len(skill_scores)) if skill_scores else 0

            # Formula: 60% CGPA + 40% Avg Skill Score
            employability_score = round((0.6 * cgpa_normalized) + (0.4 * avg_skill_score), 2)

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
                    "cgpa":                cgpa,
                    "cgpa_score":          round(cgpa_normalized, 2),
                    "avg_skill_score":     round(avg_skill_score, 2),
                    "total_skills":        len(skill_scores),
                    "employability_score": employability_score
                })

        result.sort(key=lambda x: x["employability_score"])
        paginated = result[offset: offset + limit]

        return {
            "status": 200,
            "data": {
                "students":      paginated,
                "total":         len(result),
                "threshold":     threshold,
                "limit":         limit,
                "offset":        offset,
                "score_formula": "60% CGPA (out of 10 normalized to 100) + 40% Avg Skill Score"
            }
        }

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "get_low_employability_students Error")
        return {"status": 500, "message": str(e)}