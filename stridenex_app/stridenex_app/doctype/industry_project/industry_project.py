# Copyright (c) 2026, QTPL and contributors
# For license information, please see license.txt

# import frappe
from frappe.model.document import Document
import frappe
import time

from frappe.utils import today
from stridenex_app.api_stridenex_app.app_utils import (
    gen_response,
    exception_handel,make_pagination_meta
)
from stridenex_app.api_stridenex_app.cache import cache_response
DEFAULT_PAGE_SIZE = 20

class IndustryProject(Document):
	pass

@frappe.whitelist(allow_guest=False)
def create_project():
    
    start = time.time()
    try:
        # ----------------------------------------------------------
        # PERMISSION CHECK
        # Respects Role Permission Manager configuration
        # ----------------------------------------------------------
        session_user = frappe.session.user

        if not frappe.has_permission(
            "Industry Project",
            ptype="create",
            user=session_user
        ):
            frappe.throw(
                "You do not have permission to create Industry Project.",
                frappe.PermissionError
            )

        data = frappe.request.get_json()

        course_list = data.pop("course", [])
        department_list = data.pop("department", [])
        academic_year_list = data.pop("academic_year", [])

        if "duration" in data and data["duration"] is not None and data["duration"] != "":
            try:
                data["duration"] = int(float(data["duration"]) * 86400)
            except (ValueError, TypeError):
                pass

        project = frappe.get_doc({
            "doctype": "Industry Project",
            **data
        })

        # Course
        for course in course_list:
            project.append("course", {
                "course": course if isinstance(course, str)
                else course.get("course")
            })

        # Department
        for department in department_list:
            project.append("department", {
                "department": department if isinstance(department, str)
                else department.get("department")
            })

        # Academic Year
        for year in academic_year_list:
            year_value = (
                year if isinstance(year, str)
                else year.get("academic_year")
            )

            row = frappe.new_doc("Academic Year Table")
            row.academic_year = year_value

            project.append("academic_year", row)

        # Respects Role Permission Manager
        project.insert()

        frappe.db.commit()

        return gen_response(
            status=200,
            message="Project registered successfully",
            data={"name": project.project_name}
        )

    except Exception as e:
        frappe.log_error(
            frappe.get_traceback(),
            "Create Project Error"
        )
        
        frappe.logger().info(
            f"create_project took {time.time() - start:.2f}s"
        )

        return exception_handel(e)


@frappe.whitelist(allow_guest=True)
@cache_response(ttl=180) 
def get_project_list(
    industry=None,
    student=None,
    status="Active",
    course=None,
    department=None,
    current_year=None,
    page=1,
    page_size=DEFAULT_PAGE_SIZE,
    search=None
):
    try:
        page = int(page)
        page_size = int(page_size)

        filters = {}
        if industry:
            filters["industry"] = industry
        if status:
            filters["status"] = status

        project_names = None

        if course:
            names = frappe.get_all("Course Table", filters={"course": course}, pluck="parent")
            project_names = set(names) if project_names is None else project_names & set(names)

        if department:
            names = frappe.get_all("Department Table", filters={"department": department}, pluck="parent")
            project_names = set(names) if project_names is None else project_names & set(names)

        if project_names is not None:
            if not project_names:
                return gen_response(status=200, message="No projects found", data={"projects": []})
            filters["name"] = ["in", list(project_names)]

        or_filters = None
        if search:
            or_filters = [
                ["name", "like", f"%{search}%"],
                ["project_name", "like", f"%{search}%"],
                ["industry", "like", f"%{search}%"],
            ]

        # count with the SAME filters (fixes bug #4)
        total = frappe.db.count("Industry Project", filters=filters)  
        # NOTE: db.count doesn't support or_filters directly — see note below

        projects = frappe.get_all(
            "Industry Project",
            filters=filters,
            or_filters=or_filters,
            fields=[
                "name", "project_name", "description", "project_code",
                "duration", "start_date", "end_date", "status",
                "eligibility", "industry", "application_deadline"
            ],
            order_by="creation desc",
            limit_start=(page - 1) * page_size,   # <-- FIX: actually paginate
            limit_page_length=page_size,          # <-- FIX
        )

        if not projects:
            return gen_response(
                status=200,
                message="Project list fetched successfully",
                data={"projects": [], "statistics": {}, "pagination": make_pagination_meta(total, page, page_size)}
            )

        project_ids = [p["name"] for p in projects]

        # ---- BATCH fetch skills for ALL projects in ONE query ----
        all_skills = frappe.get_all(
            "Student Skill Table",
            filters={"parent": ["in", project_ids]},
            fields=["parent", "skill"]
        )
        skills_map = {}
        for s in all_skills:
            skills_map.setdefault(s["parent"], []).append({"skill": s["skill"]})

        # ---- BATCH fetch course/department/academic_year for ALL projects ----
        all_courses = frappe.get_all(
            "Course Table", filters={"parent": ["in", project_ids]}, fields=["parent", "course"]
        )
        all_depts = frappe.get_all(
            "Department Table", filters={"parent": ["in", project_ids]}, fields=["parent", "department"]
        )
        all_years = frappe.get_all(
            "Academic Year Table", filters={"parent": ["in", project_ids]}, fields=["parent", "academic_year"]
        )

        course_map, dept_map, year_map = {}, {}, {}
        for c in all_courses:
            course_map.setdefault(c["parent"], []).append(c["course"])
        for d in all_depts:
            dept_map.setdefault(d["parent"], []).append(d["department"])
        for y in all_years:
            year_map.setdefault(y["parent"], []).append(y["academic_year"])

        # ---- Student application data (unchanged logic, just kept as is) ----
        enrollment_map = {}
        total_applied = total_completed = total_awarded = 0

        if student:
            applications = frappe.get_all(
                "Student Applications",
                filters={"student": student},
                fields=["name", "opportunity_type", "project", "internship",
                        "job_profile", "industry", "status", "applied_on", "match_score"],
                order_by="applied_on desc"
            )

            project_applications = [a for a in applications if a.opportunity_type == "Project" and a.project]

            for app in project_applications:
                enrollment_map[app.project] = {
                    "application_name": app.name,
                    "status": app.status,
                    "applied_on": app.applied_on,
                    "match_score": app.match_score
                }

            total_applied = len(project_applications)
            total_completed = len([a for a in project_applications if a.status == "Completed"])
            total_awarded = len([a for a in project_applications if a.status == "Accepted"])

        # ---- Assemble response using maps (NO per-row queries) ----
        for project in projects:
            name = project["name"]
            project["skills"] = skills_map.get(name, [])
            project["course"] = course_map.get(name, [])
            project["department"] = dept_map.get(name, [])
            project["academic_year"] = year_map.get(name, [])

            if student:
                info = enrollment_map.get(name)
                project["applied_status"] = info["status"] if info else "Not Applied"
            else:
                project["applied_status"] = None

            if project.get("duration"):
                try:
                    project["duration"] = int(project["duration"]) // 86400
                except (ValueError, TypeError):
                    pass

        return gen_response(
            status=200,
            message="Project list fetched successfully",
            data={
                "projects": projects,
                "statistics": {
                    "total_projects": total,
                    "total_applied": total_applied,
                    "total_completed": total_completed,
                    "total_awarded": total_awarded
                },
                "pagination": make_pagination_meta(total, page, page_size),
            }
        )

    except Exception as e:
        return exception_handel(e)



# @frappe.whitelist(allow_guest=True)

# def get_project_list(
#     industry=None,
#     student=None,
#     status="Active",
#     course=None,
#     department=None,
#     current_year=None,
#     page=1,
#     page_size=DEFAULT_PAGE_SIZE,
#     search=None
# ):
#     try:
#         # ----------------------------------------------------------
#         # PERMISSION CHECK
#         # Respects Role Permission Manager configuration
#         # ----------------------------------------------------------
#         # session_user = frappe.session.user

#         # if not frappe.has_permission(
#         #     "Industry Project",
#         #     ptype="read",
#         #     user=session_user
#         # ):
#         #     frappe.throw(
#         #         "You do not have permission to access Industry Project.",
#         #         frappe.PermissionError
#         #     )

#         filters = {}

#         if industry:
#             filters["industry"] = industry
#         if status:
#             filters["status"] = status
#         project_names = None

#         # Course filter
#         if course:
#             names = frappe.get_all(
#                 "Course Table",
#                 filters={"course": course},
#                 pluck="parent"
#             )
#             project_names = set(names) if project_names is None else project_names & set(names)

#         # Department filter
#         if department:
#             names = frappe.get_all(
#                 "Department Table",
#                 filters={"department": department},
#                 pluck="parent"
#             )
#             project_names = set(names) if project_names is None else project_names & set(names)

#         if project_names is not None:
#             if not project_names:
#                 return gen_response(
#                     status=200,
#                     message="No projects found",
#                     data={"projects": []}
#                 )
#             filters["name"] = ["in", list(project_names)]

#         or_filters = None
#         if search:
#             or_filters = [
#                 ["name", "like", f"%{search}%"],
#                 ["project_name", "like", f"%{search}%"],
#                 ["industry", "like", f"%{search}%"],
#             ]
#         total = frappe.db.count("Industry Project", filters=filters)

#         projects = frappe.get_all(
#             "Industry Project",
#             filters=filters,
#             or_filters=or_filters,
#             fields=[
#                 "name",
#                 "project_name",
#                 "description",
#                 "project_code",
#                 "duration",
#                 "start_date",
#                 "end_date",
#                 "status",
#                 "eligibility",
#                 "industry",
#                 "application_deadline"
#             ],
#             order_by="creation desc"
#         )

#         # ----------------------------------------------------------
#         # STUDENT APPLICATIONS (unified doctype)
#         # ----------------------------------------------------------
#         enrollment_map = {}
#         applications = []

#         # ✅ initialize regardless of `student` so stats never raise NameError
#         total_applied = 0
#         total_completed = 0
#         total_awarded = 0

#         if student:
#             applications = frappe.get_all(
#                 "Student Applications",
#                 filters={"student": student},
#                 fields=[
#                     "name",
#                     "opportunity_type",
#                     "project",
#                     "internship",
#                     "job_profile",
#                     "industry",
#                     "status",
#                     "applied_on",
#                     "match_score"
#                 ],
#                 order_by="applied_on desc"
#             )

#             for app in applications:
#                 if app.opportunity_type != "Project" or not app.project:
#                     continue

#                 # ✅ status taken exactly as stored on Student Applications, no override
#                 enrollment_map[app.project] = {
#                     "application_name": app.name,
#                     "status": app.status,
#                     "applied_on": app.applied_on,
#                     "match_score": app.match_score
#                 }

#             project_applications = [
#                 a for a in applications
#                 if a.opportunity_type == "Project"
#             ]

#             total_applied = len(project_applications)

#             total_completed = len([
#                 a for a in project_applications
#                 if a["status"] == "Completed"
#             ])

#             total_awarded = len([
#                 a for a in project_applications
#                 if a["status"] == "Accepted"
#             ])

#         for project in projects:

#             skills = frappe.get_all(
#                 "Student Skill Table",
#                 filters={"parent": project["name"]},
#                 fields=["skill"]
#             )

#             project["skills"] = skills

#             doc = frappe.get_doc(
#                 "Industry Project",
#                 project["name"]
#             )

#             project["course"] = [
#                 r.course for r in doc.course
#             ]

#             project["department"] = [
#                 r.department for r in doc.department
#             ]

#             project["academic_year"] = [
#                 r.academic_year for r in doc.academic_year
#             ]

#             if student:
#                 application_info = enrollment_map.get(project["name"])
#                 if application_info:
#                     project["applied_status"] = application_info["status"]
#                 else:
#                     project["applied_status"] = "Not Applied"
#             else:
#                 project["applied_status"] = None

#             if project.get("duration"):
#                 try:
#                     project["duration"] = int(project["duration"]) // 86400
#                 except (ValueError, TypeError):
#                     pass

#         return gen_response(
#             status=200,
#             message="Project list fetched successfully",
#             data={
#                 "projects": projects,
#                 "statistics": {
#                     "total_projects": total,
#                     "total_applied": total_applied,
#                     "total_completed": total_completed,
#                     "total_awarded": total_awarded
#                 },
#                 "pagination": make_pagination_meta(
#                     total,
#                     page,
#                     page_size
#                 ),
#             }
#         )

#     except Exception as e:
#         return exception_handel(e)

@frappe.whitelist(allow_guest=False)
def get_project_by_id(project_name):
    try:
        # ----------------------------------------------------------
        # PERMISSION CHECK
        # Respects Role Permission Manager configuration
        # ----------------------------------------------------------
        session_user = frappe.session.user

        if not frappe.has_permission(
            "Industry Project",
            ptype="read",
            user=session_user
        ):
            frappe.throw(
                "You do not have permission to access Industry Project.",
                frappe.PermissionError
            )

        project = frappe.get_doc(
            "Industry Project",
            project_name
        )

        project_data = project.as_dict()
        if project_data.get("duration"):
            try:
                project_data["duration"] = int(project_data["duration"]) // 86400
            except (ValueError, TypeError):
                pass

        return gen_response(
            status=200,
            message="Project fetched successfully",
            data=project_data
        )

    except Exception as e:
        return exception_handel(e)
    
@frappe.whitelist(allow_guest=False)
def update_project(name):
    try:
        # ----------------------------------------------------------
        # PERMISSION CHECK
        # Respects Role Permission Manager configuration
        # ----------------------------------------------------------
        session_user = frappe.session.user

        if not frappe.has_permission(
            "Industry Project",
            ptype="write",
            user=session_user
        ):
            frappe.throw(
                "You do not have permission to update Industry Project.",
                frappe.PermissionError
            )

        data = frappe.request.get_json()

        if "duration" in data and data["duration"] is not None and data["duration"] != "":
            try:
                data["duration"] = int(float(data["duration"]) * 86400)
            except (ValueError, TypeError):
                pass

        project = frappe.get_doc(
            "Industry Project",
            name
        )

        course_list = data.pop("course", None)
        department_list = data.pop("department", None)
        academic_year_list = data.pop("academic_year", None)
        required_skills = data.pop("required_skills", None)

        for key, value in data.items():
            setattr(project, key, value)

        # Course
        if course_list is not None:
            project.set("course", [])

            for course in course_list:
                project.append("course", {
                    "course": (
                        course if isinstance(course, str)
                        else course.get("course")
                    )
                })

        # Department
        if department_list is not None:
            project.set("department", [])

            for department in department_list:
                project.append("department", {
                    "department": (
                        department if isinstance(department, str)
                        else department.get("department")
                    )
                })

        # Academic Year
        if academic_year_list is not None:
            project.set("academic_year", [])

            for year in academic_year_list:
                year_value = (
                    year if isinstance(year, str)
                    else year.get("academic_year")
                )

                row = frappe.new_doc("Academic Year Table")
                row.academic_year = year_value

                project.append("academic_year", row)

        # Required Skills
        if required_skills is not None:
            project.set("required_skills", [])

            for skill in required_skills:
                project.append("required_skills", {
                    "skill": (
                        skill if isinstance(skill, str)
                        else skill.get("skill")
                    )
                })

        # Respects Role Permission Manager
        project.save()

        frappe.db.commit()

        return gen_response(
            status=200,
            message="Project updated successfully",
            data={"name": project.project_name}
        )

    except Exception as e:
        frappe.log_error(
            frappe.get_traceback(),
            "Update Project Error"
        )

        return exception_handel(e)
    
    
@frappe.whitelist(allow_guest=False)
def inactive_project(project_name):
    try:
        # ----------------------------------------------------------
        # PERMISSION CHECK
        # Respects Role Permission Manager configuration
        # # ----------------------------------------------------------
        session_user = frappe.session.user

        if not frappe.has_permission(
            "Industry Project",
            ptype="write",
            user=session_user
        ):
            frappe.throw(
                "You do not have permission to update Industry Project.",
                frappe.PermissionError
            )

        if not frappe.db.exists(
            "Industry Project",
            project_name
        ):
            return gen_response(
                status=404,
                message="Project not found",
                data=[]
            )

        project = frappe.get_doc(
            "Industry Project",
            project_name
        )

        project.status = "Disable"   # or "Inactive"

        # Respects Role Permission Manager
        project.save()

        frappe.db.commit()

        return gen_response(
            status=200,
            message="Project marked as deleted",
            data={"name": project.name}
        )

    except Exception as e:
        return exception_handel(e)




@frappe.whitelist(allow_guest=True)
def get_all_channels():
    try:
        channels = frappe.get_all(
            "Raven Channel",   # Replace with the actual DocType name if different
            fields=[
                "name",
                "channel_name",
                "type",
                "creation",
                "owner"
            ],
            order_by="creation desc"
        )

        return {
            "status": 200,
            "message": "Channels fetched successfully.",
            "data": channels
        }

    except Exception:
        frappe.log_error(frappe.get_traceback(), "Get All Channels")
        return {
            "status": 500,
            "message": "Something went wrong.",
            "data": []
        }


import frappe

@frappe.whitelist(allow_guest=True)
def get_channel_members(channel):
    try:
        if not channel:
            return {
                "status": 400,
                "message": "Channel is required",
                "data": []
            }

        members = frappe.get_all(
            "Raven Channel Member",   # Replace with the correct DocType if different
            filters={
                "channel": channel
            },
            fields=[
                "name",
                "user",
                "role",
                "creation"
            ],
            order_by="creation asc"
        )

        return {
            "status": 200,
            "message": "Members fetched successfully",
            "data": members
        }

    except Exception:
        frappe.log_error(frappe.get_traceback(), "Get Channel Members")
        raise