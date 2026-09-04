import frappe
from stridenex_app.api_stridenex_app.app_utils import (
    gen_response, 
    generate_key, 
    exception_handel
    ) 


# @frappe.whitelist(allow_guest=True)
# def get_master_data(doctype=None, filters=None, fields=None):

#     if not doctype:
#         return gen_response(400, "DocType is required", {"success": False})

#     try:
#         if not filters:
#             filters = {}

#         if not fields:
#             fields = ["name"]

#         data = frappe.get_all(doctype, filters=filters, fields=fields)

#         if data:
#             return gen_response(200, f"{doctype} list retrieved successfully", data)
#         else:
#             return gen_response(404, "No data found", [])

#     except Exception as e:
#         return gen_response(500, str(e), {"success": False})


# @frappe.whitelist(allow_guest=True)
# def get_master_data(doctype=None, filters=None, fields=None, page=1, page_size=20):
#     if not doctype:
#         return gen_response(400, "DocType is required", {"success": False})
#     try:
#         if not filters:
#             filters = {}
#         if not fields:
#             fields = ["name"]

#         # Parse filters if passed as JSON string (common when called via GET/query params)
#         if isinstance(filters, str):
#             filters = frappe.parse_json(filters)
#         if isinstance(fields, str):
#             fields = frappe.parse_json(fields)

#         # Ensure page & page_size are valid integers
#         try:
#             page = int(page)
#             page_size = int(page_size)
#         except (ValueError, TypeError):
#             page = 1
#             page_size = 20

#         if page < 1:
#             page = 1
#         if page_size < 1:
#             page_size = 20

#         limit_start = (page - 1) * page_size

#         # Total count for pagination metadata (ignores limit/offset)
#         total_count = frappe.db.count(doctype, filters=filters)

#         data = frappe.get_all(
#             doctype,
#             filters=filters,
#             fields=fields,
#             limit_start=limit_start,
#             limit_page_length=page_size,
#         )

#         if data:
#             return gen_response(200, f"{doctype} list retrieved successfully", {
#                 "data": data,
#                 "pagination": {
#                     "page": page,
#                     "page_size": page_size,
#                     "total_count": total_count,
#                     "total_pages": (total_count + page_size - 1) // page_size,
#                     "has_next": limit_start + page_size < total_count,
#                     "has_prev": page > 1,
#                 }
#             })
#         else:
#             return gen_response(404, "No data found", {
#                 "data": [],
#                 "pagination": {
#                     "page": page,
#                     "page_size": page_size,
#                     "total_count": total_count,
#                     "total_pages": (total_count + page_size - 1) // page_size,
#                     "has_next": False,
#                     "has_prev": page > 1,
#                 }
#             })
#     except Exception as e:
#         return gen_response(500, str(e), {"success": False})

@frappe.whitelist(allow_guest=True)
def get_master_data(doctype=None, filters=None, fields=None, page=1, page_size=20, search=""):
    if not doctype:
        return gen_response(400, "DocType is required", {"success": False})

    try:
        if not filters:
            filters = {}

        if not fields:
            fields = ["name"]

        # Parse filters if passed as JSON string
        if isinstance(filters, str):
            filters = frappe.parse_json(filters)

        # Parse fields if passed as JSON string
        if isinstance(fields, str):
            fields = frappe.parse_json(fields)

        # Ensure page & page_size are valid integers
        try:
            page = int(page)
            page_size = int(page_size)
        except (ValueError, TypeError):
            page = 1
            page_size = 20

        if page < 1:
            page = 1

        if page_size < 1:
            page_size = 20

        limit_start = (page - 1) * page_size

        # Search handling
        or_filters = []

        if search:
            for field in fields:
                or_filters.append({
                    field: ["like", f"%{search}%"]
                })

        # Total count
        # Total count
        if or_filters:
            conditions = []
            values = {}

            # Build OR condition manually
            for idx, condition in enumerate(or_filters):
                for field, value in condition.items():
                    conditions.append(f"`tab{doctype}`.`{field}` LIKE %(search_{idx})s")
                    values[f"search_{idx}"] = value[1]

            where_clause = " OR ".join(conditions)

            if filters:
                filter_conditions = []
                if isinstance(filters, dict):
                    for key, value in filters.items():
                        filter_conditions.append(f"`tab{doctype}`.`{key}` = %({key})s")
                        values[key] = value
                elif isinstance(filters, list):
                    for idx, cond in enumerate(filters):
                        if isinstance(cond, (list, tuple)) and len(cond) >= 3:
                            field, op, val = cond[0], cond[1], cond[2]
                            if op in ("=", "!=", "<", ">", "<=", ">=", "like", "not like", "LIKE", "NOT LIKE"):
                                param_name = f"filter_{field}_{idx}"
                                filter_conditions.append(f"`tab{doctype}`.`{field}` {op} %({param_name})s")
                                values[param_name] = val

                where_clause = " AND ".join(filter_conditions) + " AND (" + where_clause + ")"

            total_count = frappe.db.sql(
                f"""
                SELECT COUNT(name)
                FROM `tab{doctype}`
                WHERE {where_clause}
                """,
                values
            )[0][0]

        else:
            total_count = frappe.db.count(
                doctype,
                filters=filters
            )

        # Fetch data
        # For College Program Details, `academic_years` is NOT a column in that table —
        # it is sourced from the Courses master at enrichment time below.
        # Remove it from the query fields to prevent "Unknown column" SQL errors,
        # and ensure `course` is always fetched so the enrichment lookup can work.
        query_fields = list(fields)
        if doctype == "College Program Details":
            query_fields = [f for f in query_fields if f != "academic_years"]
            if "course" not in query_fields:
                query_fields.append("course")

        data = frappe.get_all(
            doctype,
            filters=filters,
            or_filters=or_filters if or_filters else None,
            fields=query_fields,
            limit_start=limit_start,
            limit_page_length=page_size,
        )

        if data and doctype == "College Program Details":
            # Map numeric year count → Select label used by the Student doctype
            # Student.academic_year options: First Year, Second Year, Third Year, Forth Year
            _YEAR_LABEL_MAP = {
                "1": "First Year",
                "2": "Second Year",
                "3": "Third Year",
                "4": "Forth Year",
            }

            def _to_year_label(value):
                """Convert numeric academic_years (e.g. 4) to label (e.g. 'Forth Year')."""
                if value is None:
                    return None
                s = str(value).strip()
                # Already a label (e.g. "Forth Year") — return as-is
                if s in _YEAR_LABEL_MAP.values():
                    return s
                # Numeric string — map to label
                return _YEAR_LABEL_MAP.get(s, s)

            # Extract course filter
            course_val = None
            if isinstance(filters, list):
                for f in filters:
                    if isinstance(f, (list, tuple)) and len(f) >= 3 and f[0] == "course":
                        course_val = f[2]
                        break
            elif isinstance(filters, dict):
                course_val = filters.get("course")

            # Look up academic_years from Courses master based on selected course
            course_academic_years = None
            if course_val:
                course_academic_years = frappe.db.get_value("Courses", course_val, "academic_years")
                if not course_academic_years:
                    course_academic_years = frappe.db.get_value("Courses", {"course_name": course_val}, "academic_years")

            # Secondary fallback: College Department
            dept_names = [d.get("department") for d in data if d.get("department")]
            dept_map = {}
            if dept_names:
                depts = frappe.get_all(
                    "College Department",
                    filters={"name": ["in", dept_names]},
                    fields=["name", "academic_years"]
                )
                dept_map = {d["name"]: d.get("academic_years") for d in depts if d.get("academic_years")}

            for item in data:
                item_course = item.get("course") or course_val
                ay = course_academic_years
                if not ay and item_course:
                    ay = frappe.db.get_value("Courses", item_course, "academic_years") or frappe.db.get_value("Courses", {"course_name": item_course}, "academic_years")
                if not ay:
                    ay = dept_map.get(item.get("department"))
                if not ay:
                    ay = "3"
                # Always return a valid Select-field label, not a raw number
                item["academic_years"] = _to_year_label(ay)

        if data:
            return gen_response(
                200,
                f"{doctype} list retrieved successfully",
                {
                    "data": data,
                    "pagination": {
                        "page": page,
                        "page_size": page_size,
                        "total_count": total_count,
                        "total_pages": (total_count + page_size - 1) // page_size,
                        "has_next": limit_start + page_size < total_count,
                        "has_prev": page > 1,
                    }
                }
            )
        else:
            return gen_response(
                404,
                "No data found",
                {
                    "data": [],
                    "pagination": {
                        "page": page,
                        "page_size": page_size,
                        "total_count": total_count,
                        "total_pages": (total_count + page_size - 1) // page_size,
                        "has_next": False,
                        "has_prev": page > 1,
                    }
                }
            )

    except Exception as e:
        frappe.log_error(
            frappe.get_traceback(),
            "Get Master Data API Error"
        )
        return gen_response(500, str(e), {"success": False})


import frappe
from frappe import _
import frappe
from frappe import _


@frappe.whitelist(allow_guest=True)
def get_courses_by_type(course_type=None, stream=None, course=None):
    """
    Get list of Courses filtered by course_type(s), stream(s), and/or course name(s).
    All params accept single or comma-separated values. course_type is required.

    Example:
    /api/method/stridenex_app.stridenex_app.doctype.courses.courses.get_courses_by_type?course_type=PG,UG
    /api/method/.../get_courses_by_type?course_type=PG,UG&stream=Computer Application,Arts
    /api/method/.../get_courses_by_type?course_type=PG,UG&stream=Computer Application&course=BCA,MCA
    """
    try:
        # if not course_type:
        #     frappe.throw(_("course_type is required"))

        course_types = [c.strip() for c in course_type.split(",") if c.strip()]

        filters = {"course_type": ["in", course_types]}

        if stream:
            stream_list = [s.strip() for s in stream.split(",") if s.strip()]
            filters["stream"] = ["in", stream_list]

        if course:
            course_list = [c.strip() for c in course.split(",") if c.strip()]
            filters["course_name"] = ["in", course_list]

        courses = frappe.get_all(
            "Courses",
            filters=filters,
            fields=["name", "course_name", "course_type", "stream"],
            order_by="course_name asc"
        )

        return gen_response(
            status=200,
            message="Courses fetched successfully",
            data={"courses": courses}
        )

    except Exception as e:
        return exception_handel(e)