# Copyright (c) 2026, QTPL and contributors
# For license information, please see license.txt

# import frappe
from frappe.model.document import Document
from stridenex_app.api_stridenex_app.app_utils import (
    gen_response, 
    exception_handel,make_pagination_meta
    ) 



class OfferTemplate(Document):
	pass



import frappe
from frappe import _


# ------------------------------------------------------------------
# CREATE
# ------------------------------------------------------------------
@frappe.whitelist(allow_guest=True)
def create_offer_template(**kwargs):
    """
    Create a new Offer Template.

    Required: template_name
    Optional: template_code, link_ewqm (Industry), select_egwf (Type: Internship/Project/Job),
              status, is_default, subject, salutation, body, description,
              terms_and_conditions, closing_note, compensation_type, compensation_amount,
              currency, duration, probation_period, letterhead, attachment,
              signatory_name, signatory_designation, signatory_signature,
              effective_from, effective_to

    Example POST body (JSON):
    {
        "template_name": "Software Intern Offer",
        "template_code": "IND-INT-01",
        "link_ewqm": "IT Industry",
        "select_egwf": "Internship",
        "status": "Active",
        "subject": "Internship Offer Letter",
        "salutation": "Dear ",
        "body": "<p>We are pleased to offer you...</p>",
        "compensation_type": "Stipend",
        "compensation_amount": 15000,
        "currency": "INR",
        "duration": "6 Months",
        "effective_from": "2026-08-27",
        "effective_to": "2026-12-31"
    }
    """
    try:
        data = kwargs or frappe.local.form_dict

        if not data.get("template_name"):
            frappe.throw(_("template_name is required"))

        allowed_fields = [
            "template_name", "template_code", "link_ewqm", "select_egwf",
            "status", "is_default", "subject", "salutation", "body",
            "description", "terms_and_conditions", "closing_note",
            "compensation_type", "compensation_amount", "currency",
            "duration", "probation_period", "letterhead", "attachment",
            "signatory_name", "signatory_designation", "signatory_signature",
            "effective_from", "effective_to"
        ]

        doc_data = {"doctype": "Offer Template"}
        for field in allowed_fields:
            if field in data and data[field] not in (None, ""):
                doc_data[field] = data[field]

        doc = frappe.get_doc(doc_data)
        doc.insert(ignore_permissions=True)
        frappe.db.commit()

        return gen_response(
            status=200,
            message="Offer Template created successfully",
            data={"offer_template": doc.as_dict()}
        )

    except Exception as e:
        frappe.db.rollback()
        return exception_handel(e)


# ------------------------------------------------------------------
# GET LIST (with filters + pagination)
# ------------------------------------------------------------------
@frappe.whitelist(allow_guest=True)
def get_offer_templates(
    template_type=None,   # select_egwf: Internship/Project/Job
    industry=None,        # link_ewqm
    status=None,
    is_default=None,
    search=None,
    page=1,
    page_size=20
):
    """
    Get list of Offer Templates with optional filters.

    Example:
    /api/method/.../get_offer_templates?template_type=Internship&status=Active
    /api/method/.../get_offer_templates?industry=IT Industry&search=intern
    """
    try:
        page = int(page)
        page_size = int(page_size)

        filters = {}

        if template_type:
            filters["select_egwf"] = ["in", [t.strip() for t in template_type.split(",") if t.strip()]]
        if industry:
            filters["link_ewqm"] = ["in", [i.strip() for i in industry.split(",") if i.strip()]]
        if status:
            filters["status"] = ["in", [s.strip() for s in status.split(",") if s.strip()]]
        if is_default is not None:
            filters["is_default"] = 1 if str(is_default) in ("1", "true", "True") else 0

        or_filters = None
        if search:
            or_filters = [
                ["template_name", "like", f"%{search}%"],
                ["template_code", "like", f"%{search}%"],
                ["subject", "like", f"%{search}%"],
            ]

        total = frappe.db.count("Offer Template", filters=filters)

        templates = frappe.get_all(
            "Offer Template",
            filters=filters,
            or_filters=or_filters,
            fields=[
                "name", "template_name", "template_code", "link_ewqm",
                "select_egwf", "status", "is_default", "subject",
                "compensation_type", "compensation_amount", "currency",
                "duration", "probation_period", "effective_from",
                "effective_to", "version", "creation"
            ],
            order_by="creation desc",
            limit_start=(page - 1) * page_size,
            limit_page_length=page_size,
        )

        return gen_response(
            status=200,
            message="Offer Templates fetched successfully",
            data={
                "offer_templates": templates,
                "pagination": make_pagination_meta(total, page, page_size)
            }
        )

    except Exception as e:
        return exception_handel(e)


# ------------------------------------------------------------------
# GET SINGLE (full detail by name)
# ------------------------------------------------------------------
@frappe.whitelist(allow_guest=True)
def get_offer_template(name=None):
    """
    Get full details of a single Offer Template by its name (ID).

    Example:
    /api/method/.../get_offer_template?name=OT-0001
    """
    try:
        if not name:
            frappe.throw(_("name is required"))

        if not frappe.db.exists("Offer Template", name):
            return gen_response(
                status=404,
                message="Offer Template not found",
                data={}
            )

        doc = frappe.get_doc("Offer Template", name)

        return gen_response(
            status=200,
            message="Offer Template fetched successfully",
            data={"offer_template": doc.as_dict()}
        )

    except Exception as e:
        return exception_handel(e)


# ------------------------------------------------------------------
# UPDATE OFFER TEMPLATE
# ------------------------------------------------------------------
@frappe.whitelist(allow_guest=True)
def update_offer_template(name=None, **kwargs):
    """
    Update an existing Offer Template.

    Required:
        name

    Optional:
        template_name, template_code, link_ewqm, select_egwf,
        status, is_default, subject, salutation, body, description,
        terms_and_conditions, closing_note, compensation_type,
        compensation_amount, currency, duration, probation_period,
        letterhead, attachment, signatory_name,
        signatory_designation, signatory_signature,
        effective_from, effective_to

    Example:
    /api/method/.../update_offer_template?name=OT-0001

    JSON:
    {
        "template_name": "Updated Software Intern Offer",
        "status": "Active",
        "compensation_amount": 18000,
        "duration": "6 Months"
    }
    """

    try:
        # ----------------------------------------------------------
        # Validate name
        # ----------------------------------------------------------
        if not name:
            frappe.throw(_("name is required"))

        # ----------------------------------------------------------
        # Check document exists
        # ----------------------------------------------------------
        if not frappe.db.exists("Offer Template", name):
            return gen_response(
                status=404,
                message="Offer Template not found",
                data={}
            )

        # ----------------------------------------------------------
        # Get existing document
        # ----------------------------------------------------------
        doc = frappe.get_doc("Offer Template", name)

        # ----------------------------------------------------------
        # Get request data
        # ----------------------------------------------------------
        data = kwargs or frappe.local.form_dict

        # ----------------------------------------------------------
        # Allowed fields
        # ----------------------------------------------------------
        allowed_fields = [
            "template_name",
            "template_code",
            "link_ewqm",
            "select_egwf",
            "status",
            "is_default",
            "subject",
            "salutation",
            "body",
            "description",
            "terms_and_conditions",
            "closing_note",
            "compensation_type",
            "compensation_amount",
            "currency",
            "duration",
            "probation_period",
            "letterhead",
            "attachment",
            "signatory_name",
            "signatory_designation",
            "signatory_signature",
            "effective_from",
            "effective_to"
        ]

        # ----------------------------------------------------------
        # Duplicate template code check
        # ----------------------------------------------------------
        if data.get("template_code"):

            existing = frappe.db.exists(
                "Offer Template",
                {
                    "template_code": data.get("template_code"),
                    "name": ["!=", name]
                }
            )

            if existing:
                return gen_response(
                    status=409,
                    message="Template code already exists",
                    data={
                        "existing_template": existing
                    }
                )

        # ----------------------------------------------------------
        # Update fields
        # ----------------------------------------------------------
        updated_fields = []

        for field in allowed_fields:

            if field in data:
                value = data.get(field)

                # Allow 0 and False values
                if value is not None:
                    setattr(doc, field, value)
                    updated_fields.append(field)

        # ----------------------------------------------------------
        # Validate template name
        # ----------------------------------------------------------
        if not doc.template_name:
            frappe.throw(_("template_name is required"))

        # ----------------------------------------------------------
        # Save document
        # ----------------------------------------------------------
        doc.save(ignore_permissions=True)

        frappe.db.commit()

        # ----------------------------------------------------------
        # Response
        # ----------------------------------------------------------
        return gen_response(
            status=200,
            message="Offer Template updated successfully",
            data={
                "offer_template": doc.as_dict(),
                "updated_fields": updated_fields
            }
        )

    except Exception as e:
        frappe.db.rollback()
        return exception_handel(e)


# ------------------------------------------------------------------
# DELETE OFFER TEMPLATE
# ------------------------------------------------------------------
@frappe.whitelist(allow_guest=True)
def delete_offer_template(name=None):
    """
    Delete an Offer Template by name.

    Example:
    /api/method/.../delete_offer_template?name=OT-0001
    """

    try:
        # ----------------------------------------------------------
        # Validate name
        # ----------------------------------------------------------
        if not name:
            frappe.throw(_("name is required"))

        # ----------------------------------------------------------
        # Check if document exists
        # ----------------------------------------------------------
        if not frappe.db.exists("Offer Template", name):
            return gen_response(
                status=404,
                message="Offer Template not found",
                data={}
            )

        # ----------------------------------------------------------
        # Get document
        # ----------------------------------------------------------
        doc = frappe.get_doc("Offer Template", name)

        # ----------------------------------------------------------
        # Delete document
        # ----------------------------------------------------------
        frappe.delete_doc(
            "Offer Template",
            name,
            ignore_permissions=True,
            force=True
        )

        frappe.db.commit()

        # ----------------------------------------------------------
        # Response
        # ----------------------------------------------------------
        return gen_response(
            status=200,
            message="Offer Template deleted successfully",
            data={
                "deleted_offer_template": {
                    "name": name,
                    "template_name": doc.template_name,
                    "template_code": doc.template_code
                }
            }
        )

    except Exception as e:
        frappe.db.rollback()
        return exception_handel(e)

