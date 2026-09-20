# Copyright (c) 2026, QTPL and contributors
# For license information, please see license.txt

# import frappe
from frappe.model.document import Document


class SuccessStory(Document):
	pass


import frappe
from frappe import _


# ---------------------------------------------------------
# GET API — Fetch Success Stories
# ---------------------------------------------------------
@frappe.whitelist(allow_guest=True)
def get_success_stories(featured=None, category=None, status="Published", limit=10, page=1):
    try:
        limit = int(limit)
        page = int(page)
        start = (page - 1) * limit

        filters = {"status": status}

        if featured is not None:
            filters["is_featured"] = 1 if str(featured).lower() in ["1", "true"] else 0

        if category:
            filters["outcome_category"] = category

        total = frappe.db.count("Success Story", filters=filters)

        stories = frappe.get_all(
            "Success Story",
            filters=filters,
            fields=[
                "name as id",
                "student",
                "student.first_name as first_name",
                "student.last_name as last_name",
                "college",
                "outcome_category",
                "outcome_title",
                "outcome_metric",
                "testimonial",
                "avatar_initials",
                "avatar_color",
                "avatar_image",
                "is_featured",
                "display_order",
                "published_date"
            ],
            order_by="display_order asc, published_date desc",
            start=start,
            page_length=limit
        )

        for story in stories:
            first = story.pop("first_name", None) or ""
            last = story.pop("last_name", None) or ""
            full_name = f"{first} {last}".strip()
            if full_name:
                story["student"] = full_name


        return {
            "success": True,
            "total": total,
            "page": page,
            "data": stories
        }

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Get Success Stories Failed")
        frappe.local.response["http_status_code"] = 500
        return {
            "success": False,
            "error": str(e)
        }


# ---------------------------------------------------------
# POST API — Create Success Story
# ---------------------------------------------------------
@frappe.whitelist(allow_guest=True)
def create_success_story(**kwargs):
    """
    POST /api/method/stridenex_app.api.success_story.create_success_story
    Body: student, outcome_title, testimonial, outcome_metric,
          outcome_category, avatar_initials, avatar_color, is_featured, status
    """
    try:
        required_fields = ["student", "outcome_title", "testimonial"]
        missing = [f for f in required_fields if not kwargs.get(f)]

        if missing:
            frappe.local.response["http_status_code"] = 400
            return {
                "success": False,
                "error": f"Missing required fields: {', '.join(missing)}"
            }

        doc = frappe.get_doc({
            "doctype": "Success Story",
            "student": kwargs.get("student"),
            "outcome_category": kwargs.get("outcome_category"),
            "outcome_title": kwargs.get("outcome_title"),
            "outcome_metric": kwargs.get("outcome_metric"),
            "testimonial": kwargs.get("testimonial"),
            "display_order": kwargs.get("display_order"),
            "status": kwargs.get("status", "Draft"),
        })

        doc.insert(ignore_permissions=True)
        frappe.db.commit()

        frappe.local.response["http_status_code"] = 201
        return {
            "success": True,
            "message": "Success story created",
            "data": {
                "id": doc.name,
                "student": doc.student,
                "status": doc.status,
                "creation": doc.creation
            }
        }

    except frappe.exceptions.ValidationError as ve:
        frappe.local.response["http_status_code"] = 400
        return {
            "success": False,
            "error": str(ve)
        }

    except Exception as e:
        frappe.db.rollback()
        frappe.log_error(frappe.get_traceback(), "Create Success Story Failed")
        frappe.local.response["http_status_code"] = 500
        return {
            "success": False,
            "error": str(e)
        }