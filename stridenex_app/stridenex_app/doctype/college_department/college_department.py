# Copyright (c) 2026, QTPL and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class CollegeDepartment(Document):
	pass


COURSE_ALIASES = {
    "b.e./b.tech": ["B.E./B.Tech", "BE/B.Tech", "B.E", "BTech", "BE", "B.E.", "B.Tech"],
    "be/b.tech": ["B.E./B.Tech", "BE/B.Tech", "B.E", "BTech", "BE", "B.E.", "B.Tech"],
    "b.e": ["B.E./B.Tech", "BE/B.Tech", "B.E", "BTech", "BE", "B.E.", "B.Tech"],
    "btech": ["B.E./B.Tech", "BE/B.Tech", "B.E", "BTech", "BE", "B.E.", "B.Tech"],
    "be": ["B.E./B.Tech", "BE/B.Tech", "B.E", "BTech", "BE", "B.E.", "B.Tech"],

    "m.e./m.tech": ["M.E./M.Tech", "ME/M.Tech", "M.E", "MTech", "ME", "M.E.", "M.Tech"],
    "me/m.tech": ["M.E./M.Tech", "ME/M.Tech", "M.E", "MTech", "ME", "M.E.", "M.Tech"],
    "m.e": ["M.E./M.Tech", "ME/M.Tech", "M.E", "MTech", "ME", "M.E.", "M.Tech"],
    "mtech": ["M.E./M.Tech", "ME/M.Tech", "M.E", "MTech", "ME", "M.E.", "M.Tech"],
    "me": ["M.E./M.Tech", "ME/M.Tech", "M.E", "MTech", "ME", "M.E.", "M.Tech"],

    "b.a.": ["B.A.", "BA", "B.A"],
    "ba": ["B.A.", "BA", "B.A"],

    "m.a.": ["M.A.", "MA", "M.A"],
    "ma": ["M.A.", "MA", "M.A"],

    "b.sc.": ["B.Sc.", "BSc", "B.Sc"],
    "bsc": ["B.Sc.", "BSc", "B.Sc"],

    "m.sc.": ["M.Sc.", "MSc", "M.Sc"],
    "msc": ["M.Sc.", "MSc", "M.Sc"],

    "b.com": ["B.Com", "BCom", "B.Com."],
    "bcom": ["B.Com", "BCom", "B.Com."],

    "m.com": ["M.Com", "MCom", "M.Com."],
    "mcom": ["M.Com", "MCom", "M.Com."],

    "bca": ["BCA", "B.C.A.", "B.C.A"],
    "mca": ["MCA", "M.C.A.", "M.C.A"],

    "b.pham": ["B.Pham", "B.Pharm", "BPharm", "B.Pharmacy"],
    "b.pharm": ["B.Pham", "B.Pharm", "BPharm", "B.Pharmacy"],
    "bpharm": ["B.Pham", "B.Pharm", "BPharm", "B.Pharmacy"],
}


@frappe.whitelist(allow_guest=True)
def get_departments_by_course(courses=None):
    try:
        if not courses:
            courses = frappe.form_dict.get("courses")

        if not courses and frappe.request and hasattr(frappe.request, "get_data") and frappe.request.get_data():
            try:
                json_data = frappe.request.get_json()
                if isinstance(json_data, dict):
                    courses = json_data.get("courses")
            except Exception:
                pass

        if not courses:
            return {
                "status": 400,
                "message": "Courses parameter is required",
                "data": []
            }

        # Handle list vs comma-separated string vs JSON string
        if isinstance(courses, str):
            if courses.startswith("[") and courses.endswith("]"):
                try:
                    courses = frappe.parse_json(courses)
                except Exception:
                    courses = [c.strip() for c in courses.split(",") if c.strip()]
            else:
                courses = [c.strip() for c in courses.split(",") if c.strip()]

        if not isinstance(courses, list):
            courses = [str(courses)]

        # Build expanded list of course names including aliases
        expanded_courses = set()
        for c in courses:
            c_str = str(c).strip()
            if not c_str:
                continue
            expanded_courses.add(c_str)

            c_lower = c_str.lower()
            if c_lower in COURSE_ALIASES:
                for alias in COURSE_ALIASES[c_lower]:
                    expanded_courses.add(alias)

            # Also handle variations like stripping dots
            c_no_dots = c_str.replace(".", "")
            expanded_courses.add(c_no_dots)

        search_courses = list(expanded_courses)

        # -----------------------------
        # Get Parent Departments
        # -----------------------------
        department_names = frappe.get_all(
            "Course Table",
            filters={
                "course": ["in", search_courses],
                "parenttype": "College Department"
            },
            pluck="parent"
        )

        # If still not found, attempt case-insensitive/LIKE matching for each course keyword
        if not department_names:
            or_filters = []
            for sc in search_courses:
                if len(sc) >= 2:
                    or_filters.append(["course", "like", f"%{sc}%"])

            if or_filters:
                department_names = frappe.get_all(
                    "Course Table",
                    filters={"parenttype": "College Department"},
                    or_filters=or_filters,
                    pluck="parent"
                )

        if not department_names:
            return {
                "status": 200,
                "message": "No departments found",
                "data": []
            }

        # Unique department names
        department_names = list(set(department_names))

        departments = frappe.get_all(
            "College Department",
            filters={
                "name": ["in", department_names]
            },
            fields=["name", "department_name"]
        )

        return {
            "status": 200,
            "message": "Departments fetched successfully",
            "data": departments
        }

    except frappe.PermissionError as e:
        return {
            "status": 403,
            "message": str(e),
            "data": []
        }

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Get Departments Error")
        return {
            "status": 400,
            "message": str(e),
            "data": []
        }