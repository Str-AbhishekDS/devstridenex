# Copyright (c) 2026, QTPL and contributors
# For license information, please see license.txt

import frappe
import json
import math

from stridenex_app.api_stridenex_app.app_utils import (
    gen_response,
    exception_handel,make_cache_key,make_pagination_meta
)
import frappe
from frappe.model.document import Document
from frappe.utils import getdate, today
CACHE_TTL   = 300 

class Student(Document):
    def validate(self):
    
        self.validate_resume()
        self.validate_social_links()
        self.validate_date_of_birth()

    def validate_date_of_birth(self):
        if self.date_of_birth:
            dob = getdate(self.date_of_birth)
            current_date = getdate(today())
            if dob >= current_date:
                frappe.throw("Date of Birth cannot be today or in the future.")
            
            # Age check: must be at least 15 years old
            age = current_date.year - dob.year - ((current_date.month, current_date.day) < (dob.month, dob.day))
            if age < 15:
                frappe.throw("Student must be at least 15 years old. Please enter a valid Date of Birth.")

    def validate_resume(self):
        if self.resume:
            file_doc = frappe.get_doc("File", {"file_url": self.resume})
            
            if not file_doc.file_name.lower().endswith(".pdf"):
                frappe.throw("Only PDF files are allowed for Resume upload.")


    def validate_social_links(self):
        if self.linkedin and "linkedin.com" not in self.linkedin.lower():
            frappe.throw("Please enter a valid LinkedIn URL.")

        if self.github and "github.com" not in self.github.lower():
            frappe.throw("Please enter a valid GitHub URL.")
            
    def after_insert(self):
        self.create_student_skills()

    def create_student_skills(self):

        if not self.skill:
            return

        for row in self.skill:

            if not row.skill:
                continue

            if not frappe.db.exists(
                "Student Skill",
                {"student": self.name, "skill": row.skill}
            ):

                student_skill = frappe.new_doc("Student Skill")
                student_skill.student = self.name
                student_skill.skill = row.skill
                student_skill.current_level = row.level
                student_skill.self_declared = 1
                student_skill.is_public = 1
                student_skill.first_acquired = frappe.utils.today()

                student_skill.insert(ignore_permissions=True)
                student_skill.save(ignore_permissions = True)
                frappe.db.commit()

    def get_total_student_count():
        return frappe.db.count("Student", {"status": "Active"})


@frappe.whitelist(allow_guest=True)
def get_student_count():
    try:
        count = frappe.db.count("Student")

        return gen_response(
            status=200,
            message="Student count fetched successfully",
            data={"total_students": count}
        )

    except Exception as e:
        return exception_handel(e)

@frappe.whitelist()
def get_student_skills(student):
    """
    Fetch all skills and levels for a student.
    """
    if not frappe.db.exists("Student", student):
        frappe.throw("Student not found")

    student_doc = frappe.get_doc("Student", student)

    skills = []
    for row in student_doc.skill:
        skills.append({
            "skill": row.skill,
            "level": row.level
        })

    return {
        "student": student,
        "skills": skills
    }


@frappe.whitelist()
def get_dashboard_stats(student=None):
    student = student or frappe.db.get_value("Student", {"email_id": frappe.session.user})
    if not student:
        frappe.throw("Student profile not found")

    s = frappe.get_doc("Student", student)

    total_skills = frappe.db.count("Student Skill", {
        "student": student,
        "status": ["!=", "Rejected"]
    })

    return {
        "employability_score": s.employability_score,
        
        "total_skills": total_skills,
        "cgpa": s.cgpa,
        "backlog": s.get("backlog") or 0,
       
        "profile_completeness": get_profile_completeness(s)
    }

def get_profile_completeness(student_doc):
    required_fields = ["first_name", "last_name", "email_id", "mobile_no",
                        "college", "course", "resume", "cgpa", "date_of_birth"]
    filled = sum(1 for f in required_fields if student_doc.get(f))
    return round((filled / len(required_fields)) * 100)
    
DEFAULT_PAGE_SIZE = 20

JUNK_VALUES = {"", "none", "null", "undefined", "nan"}


def _clean(value):
    """Return None if the incoming value is empty/junk, else the stripped value."""
    if value is None:
        return None
    value = str(value).strip()
    return None if value.lower() in JUNK_VALUES else value


@frappe.whitelist(allow_guest=True)
def get_student_list(
    search=None,
    college=None,
    current_year=None,
    skills=None,          # "Python,SQL" or '["Python","SQL"]'
    min_match=0,           # e.g. 80 -> only candidates with >=80% skill match
    sort_by="best_match",  # best_match | name | year
    page=1,
    page_size=DEFAULT_PAGE_SIZE,
):
    """
    Response shape (UNCHANGED):
    {
        students: [
            { student_name, college, course, department, stream, match_percentage, skills }
        ],
        pagination: {...}
    }
    """
    try:
        page = int(page)
        page_size = int(page_size)
        min_match = float(min_match or 0)
        limit = page_size
        offset = (page - 1) * page_size

        # ---- FIX: sanitize filter inputs so "None"/"null"/"" strings from the
        # frontend are treated as no-filter, not as literal filter values ----
        search = _clean(search)
        college = _clean(college)
        current_year = _clean(current_year)

        # ---- normalize skills param ----
        skill_list = []
        if skills:
            if isinstance(skills, str):
                try:
                    skill_list = json.loads(skills)
                except (ValueError, TypeError):
                    skill_list = [s.strip() for s in skills.split(",") if s.strip()]
            elif isinstance(skills, list):
                skill_list = skills
        skill_list = [s for s in skill_list if _clean(s)]

        # ---- cache key ----
        cache_key = make_cache_key(
            "student_search",
            search=search or "", college=college or "", current_year=current_year or "",
            skills=",".join(sorted(s.lower() for s in skill_list)), min_match=min_match,
            sort_by=sort_by, page=page, page_size=page_size,
        )
        cached = frappe.cache().get_value(cache_key)
        if cached:
            return cached

        # ---- shared WHERE conditions on tabStudent (built once, reused) ----
        conditions = []
        values = {}
        if college:
            conditions.append("s.college = %(college)s")
            values["college"] = college
        if current_year:
            conditions.append("s.current_year = %(current_year)s")
            values["current_year"] = current_year
        if search:
            conditions.append("s.email_id LIKE %(search)s")
            values["search"] = f"%{search}%"

        where_clause = ("WHERE " + " AND ".join(conditions)) if conditions else ""

        # =========================================================
        # CASE 1: skills selected -> join + score + filter + sort
        #         all done in SQL, only the final page comes back.
        # =========================================================
        if skill_list:
            skill_placeholders = []
            for i, sk in enumerate(skill_list):
                key = f"skill_{i}"
                values[key] = sk
                skill_placeholders.append(f"%({key})s")
            skill_in_clause = ", ".join(skill_placeholders)

            total_selected = len(skill_list)
            min_count = math.ceil((min_match / 100) * total_selected) if min_match else 0
            values["min_count"] = min_count

            order_clause = "ORDER BY matched_count DESC, s.creation DESC"
            if sort_by == "name":
                order_clause = "ORDER BY s.email_id ASC"   # FIX: was "eamil_id" (typo, undefined column -> caused errors)
            elif sort_by == "year":
                order_clause = "ORDER BY s.current_year DESC"

            base_query = f"""
                FROM `tabStudent` s
                INNER JOIN (
                    SELECT parent, COUNT(DISTINCT skill) AS matched_count
                    FROM `tabStudent Skill Table`
                    WHERE skill IN ({skill_in_clause})
                    GROUP BY parent
                    HAVING matched_count >= %(min_count)s
                ) t ON t.parent = s.name
                {where_clause}
            """

            total = frappe.db.sql(f"SELECT COUNT(*) {base_query}", values)[0][0]

            values["limit"] = limit
            values["offset"] = offset
            rows = frappe.db.sql(
                f"""
                SELECT s.*, t.matched_count
                {base_query}
                {order_clause}
                LIMIT %(limit)s OFFSET %(offset)s
                """,
                values,
                as_dict=True,
            )

            students = rows
            for student in students:
                matched = student.pop("matched_count", 0)
                student["match_percentage"] = round((matched / total_selected) * 100)

        # =========================================================
        # CASE 2: no skills selected -> plain fast filtered query
        # =========================================================
        else:
            order_clause = "ORDER BY s.creation DESC"
            if sort_by == "name":
                order_clause = "ORDER BY s.email_id ASC"   # FIX: same typo fixed here
            elif sort_by == "year":
                order_clause = "ORDER BY s.current_year DESC"

            total = frappe.db.sql(
                f"SELECT COUNT(*) FROM `tabStudent` s {where_clause}", values
            )[0][0]

            values["limit"] = limit
            values["offset"] = offset
            students = frappe.db.sql(
                f"""
                SELECT s.*
                FROM `tabStudent` s
                {where_clause}
                {order_clause}
                LIMIT %(limit)s OFFSET %(offset)s
                """,
                values,
                as_dict=True,
            )
            for student in students:
                student["match_percentage"] = None

        # ---- attach skills only for the page we're returning (cheap) ----
        if students:
            parent_names = [s["name"] for s in students]
            all_skills = frappe.get_all(
                "Student Skill Table",
                filters=[["parent", "in", parent_names]],
                fields=["parent", "skill"],
            )
            skills_map = {}
            for sk in all_skills:
                skills_map.setdefault(sk["parent"], []).append({"skill": sk["skill"]})
            for student in students:
                student["skills"] = skills_map.get(student["name"], [])

        # ---- response (UNCHANGED shape) ----
        result = gen_response(
            status=200,
            message="Student list fetched successfully",
            data={
                "students": students,
                "pagination": make_pagination_meta(total, page, page_size),
            },
        )

        frappe.cache().set_value(cache_key, result, expires_in_sec=CACHE_TTL)
        return result

    except Exception as e:
        return exception_handel(e)

@frappe.whitelist(allow_guest=True)
def export_students(search=None, college=None, current_year=None, skills=None, min_match=0, sort_by="best_match"):
    """
    Same filtering/scoring logic as get_student_list but returns the FULL
    result set (no pagination) for CSV/Excel export.
    """
    try:
        full = get_student_list(
            search=search, college=college, current_year=current_year,
            skills=skills, min_match=min_match, sort_by=sort_by,
            page=1, page_size=10**9,   # effectively "all"
        )
        return full
    except Exception as e:
        return exception_handel(e)




@frappe.whitelist(allow_guest=True)
def create_skill():
    try:
        data = frappe.request.get_json()

        doc = frappe.get_doc({
            "doctype": "Skill",
            "skill_name": data.get("skill_name")
        })

        doc.insert(ignore_permissions=True)
        frappe.db.commit()

        return {
            "status": "success",
            "message": "Skill created successfully",
            "data": doc.name
        }

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Create Skill Error")
        return {
            "status": "error",
            "message": str(e)
        }
    

import frappe
from frappe.utils import getdate, nowdate, add_days, cint

MINUTES_PER_LESSON = 20  # tune this, or replace with a real duration lookup


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _resolve_member(student=None):
    """
    Resolve the LMS `member` (a User docname/email) for a given Student
    record or the logged-in user. Returns the email/User-name string.
    """
    if student:
        email = frappe.db.get_value("Student", student, "email_id")
        if email:
            return email
        # allow passing the email/User name directly
        if frappe.db.exists("User", student):
            return student
        frappe.throw(frappe._("Student not found: {0}").format(student))

    # default to the logged-in user
    if frappe.db.exists("Student", {"email_id": frappe.session.user}):
        return frappe.session.user
    frappe.throw(frappe._("No Student record linked to the current user."))


def _activity_level(lessons, problems, study_minutes):
    """Bucket a day's activity into a 0-4 heatmap intensity, low -> high."""
    score = lessons + problems + (study_minutes / 30.0)
    if score <= 0:
        return 0
    if score < 2:
        return 1
    if score < 4:
        return 2
    if score < 7:
        return 3
    return 4


def _estimate_minutes(lessons_completed):
    """See ASSUMPTION note at top of file."""
    return lessons_completed * MINUTES_PER_LESSON


# ---------------------------------------------------------------------------
# main endpoint
# ---------------------------------------------------------------------------

@frappe.whitelist()
def get_learning_activity(student=None, weeks=7):
    """
    Returns the heatmap grid (oldest -> newest, 7-day rows) plus the three
    stat tiles: total Lessons, total Problems, total Study Time.

    Response shape:
    {
      "weeks": [
        {"week_start": "2026-06-14", "days": [
            {"date": "2026-06-14", "level": 2, "lessons": 1,
             "problems": 3, "study_minutes": 20}, ...
        ]}, ...
      ],
      "totals": {"lessons": 42, "problems": 87, "study_hours": 68.0}
    }
    """
    weeks = cint(weeks) or 7
    member = _resolve_member(student)

    end_date = getdate(nowdate())
    start_date = add_days(end_date, -(weeks * 7 - 1))

    # --- lessons completed per day, from LMS Course Progress ---------------
    lesson_rows = frappe.db.sql(
        """
        select date(creation) as day, count(*) as lessons
        from `tabLMS Course Progress`
        where member = %(member)s
          and status = 'Complete'
          and date(creation) between %(start)s and %(end)s
        group by date(creation)
        """,
        {"member": member, "start": start_date, "end": end_date},
        as_dict=True,
    )
    lessons_by_day = {str(r.day): cint(r.lessons) for r in lesson_rows}

    # --- problems (correctly answered quiz questions) per day --------------
    problem_rows = frappe.db.sql(
        """
        select date(sub.creation) as day, count(*) as problems
        from `tabLMS Quiz Submission` sub
        inner join `tabLMS Quiz Result` res
            on res.parent = sub.name and res.parenttype = 'LMS Quiz Submission'
        where sub.member = %(member)s
          and res.is_correct = 1
          and date(sub.creation) between %(start)s and %(end)s
        group by date(sub.creation)
        """,
        {"member": member, "start": start_date, "end": end_date},
        as_dict=True,
    )
    problems_by_day = {str(r.day): cint(r.problems) for r in problem_rows}

    # --- assemble day-by-day, then chunk into weeks -------------------------
    days = []
    cursor = start_date
    while cursor <= end_date:
        key = str(cursor)
        lessons = lessons_by_day.get(key, 0)
        problems = problems_by_day.get(key, 0)
        minutes = _estimate_minutes(lessons)
        days.append({
            "date": key,
            "level": _activity_level(lessons, problems, minutes),
            "lessons": lessons,
            "problems": problems,
            "study_minutes": minutes,
        })
        cursor = add_days(cursor, 1)

    grid = []
    for i in range(0, len(days), 7):
        chunk = days[i:i + 7]
        if chunk:
            grid.append({"week_start": chunk[0]["date"], "days": chunk})

    total_lessons = sum(d["lessons"] for d in days)
    total_problems = sum(d["problems"] for d in days)
    total_minutes = sum(d["study_minutes"] for d in days)

    return {
        "weeks": grid,
        "totals": {
            "lessons": total_lessons,
            "problems": total_problems,
            "study_hours": round(total_minutes / 60.0, 1),
        },
    }


import frappe
from frappe.utils import add_days, today, getdate


@frappe.whitelist(allow_guest=True)
def get_todays_opportunity_alerts():
    try:
        student_email = frappe.form_dict.get("student")
        course = frappe.form_dict.get("course")
        department = frappe.form_dict.get("department")
        current_year = frappe.form_dict.get("current_year")

        if student_email and frappe.db.exists("Student", student_email):
            student_doc = frappe.get_doc("Student", student_email)
            if not course:
                course = student_doc.course
            if not department:
                department = student_doc.department
            if not current_year:
                current_year = student_doc.current_year

        new_from_date = add_days(today(), -5)      # "new posting" window
        deadline_to_date = add_days(today(), 7)    # "deadline approaching" window
        deadline_from_date = today()

        # -------- doctype config: name, deadline field, extra display fields --------
        doctype_config = [
            {
                "doctype": "Internship",
                "deadline_field": "application_deadline",
                "title_field": "title",
                "status_field": "status",
                "open_statuses": ["Active"],
            },
            {
                "doctype": "Industry Project",
                "deadline_field": "application_deadline",
                "title_field": "project_name",
                "status_field": "status",
                "open_statuses": ["Active"],
            },
            {
                "doctype": "Industry Job Profile",
                "deadline_field": "last_date",
                "title_field": "job_title",
                "status_field": "status",
                "open_statuses": ["Open"],
            },
        ]

        new_postings = []
        deadline_alerts = []

        for cfg in doctype_config:
            # ---------------- New postings (last 5 days) ----------------
            new_records = frappe.get_all(
                cfg["doctype"],
                filters={
                    "creation": [">=", new_from_date],
                },
                fields=["name", cfg["title_field"], "creation"],
                order_by="creation desc",
            )

            if new_records:
                new_names = [r["name"] for r in new_records]
                matched_new_names = set(_filter_opportunities_for_student(
                    doctype=cfg["doctype"],
                    names=new_names,
                    course=course,
                    department=department,
                    current_year=current_year,
                ))
                for r in new_records:
                    if r["name"] in matched_new_names:
                        new_postings.append({
                            "type": cfg["doctype"],
                            "name": r["name"],
                            "title": r.get(cfg["title_field"]),
                            "date": r["creation"].strftime("%Y-%m-%d"),
                            "alert": "New opportunity posted"
                        })

            # ---------------- Deadline within next 7 days ----------------
            deadline_filters = {
                cfg["deadline_field"]: ["between", [deadline_from_date, deadline_to_date]],
            }
            if cfg.get("status_field") and cfg.get("open_statuses"):
                deadline_filters[cfg["status_field"]] = ["in", cfg["open_statuses"]]

            deadline_records = frappe.get_all(
                cfg["doctype"],
                filters=deadline_filters,
                fields=["name", cfg["title_field"], cfg["deadline_field"]],
                order_by=f"{cfg['deadline_field']} asc",
            )

            if deadline_records:
                deadline_names = [r["name"] for r in deadline_records]
                matched_deadline_names = set(_filter_opportunities_for_student(
                    doctype=cfg["doctype"],
                    names=deadline_names,
                    course=course,
                    department=department,
                    current_year=current_year,
                ))
                for r in deadline_records:
                    if r["name"] in matched_deadline_names:
                        deadline_date = r.get(cfg["deadline_field"])
                        days_left = (getdate(deadline_date) - getdate(today())).days
                        deadline_alerts.append({
                            "type": cfg["doctype"],
                            "name": r["name"],
                            "title": r.get(cfg["title_field"]),
                            "deadline": deadline_date.strftime("%Y-%m-%d") if deadline_date else None,
                            "days_left": days_left,
                            "alert": f"Deadline in {days_left} day(s)" if days_left > 0 else "Deadline is today"
                        })

        return gen_response(
            status=200,
            message="Opportunity alerts fetched successfully",
            data={
                "student": student_email,
                "new_postings": new_postings,
                "deadline_alerts": deadline_alerts,
                "total_new_postings": len(new_postings),
                "total_deadline_alerts": len(deadline_alerts),
            }
        )

    except Exception as e:
        return exception_handel(e)


def _filter_opportunities_for_student(doctype, names, course, department, current_year):
    """
    Filters a list of opportunity names to only those that match the student's
    course, department, or academic year, or are open to all.
    """
    if not names:
        return []

    # Map each parent to its restricted courses, departments, academic_years
    course_map = {}
    for r in frappe.get_all("Course Table", filters={"parenttype": doctype, "parent": ["in", names]}, fields=["parent", "course"]):
        course_map.setdefault(r["parent"], set()).add(r["course"])

    dept_map = {}
    for r in frappe.get_all("Department Table", filters={"parenttype": doctype, "parent": ["in", names]}, fields=["parent", "department"]):
        dept_map.setdefault(r["parent"], set()).add(r["department"])

    year_map = {}
    for r in frappe.get_all("Academic Year Table", filters={"parenttype": doctype, "parent": ["in", names]}, fields=["parent", "academic_year"]):
        year_map.setdefault(r["parent"], set()).add(r["academic_year"])

    matched_names = []
    for name in names:
        has_course_restriction = name in course_map
        has_dept_restriction = name in dept_map
        has_year_restriction = name in year_map

        # Open to all if there are no restrictions at all
        if not (has_course_restriction or has_dept_restriction or has_year_restriction):
            matched_names.append(name)
            continue

        # Match course
        if course and has_course_restriction and course in course_map[name]:
            matched_names.append(name)
            continue

        # Match department
        if department and has_dept_restriction and department in dept_map[name]:
            matched_names.append(name)
            continue

        # Match academic year
        if current_year and has_year_restriction and current_year in year_map[name]:
            matched_names.append(name)
            continue

    return matched_names