import json

from stridenex_app.api_stridenex_app.app_utils import sync_billing_account_master

import frappe

from stridenex_app.api_stridenex_app.app_utils import (
    gen_response,
    exception_handel,get_pagination_params,make_cache_key,make_pagination_meta
)
from frappe.exceptions import DuplicateEntryError

CACHE_TTL   = 300 

@frappe.whitelist(allow_guest=True)
def create_mentor():
    try:
        data = frappe.request.get_json()

        email = data.get("email_id")
        mobile = data.get("mobile_no")

        if not email:
            frappe.throw("Email is required")

        if not mobile:
            frappe.throw("Mobile number is required")

        existing_mentor = frappe.db.exists(
            "Mentor",
            {"email_id": email}
        )

        if existing_mentor:
            mentor = frappe.get_doc("Mentor", existing_mentor)

        else:
            mentor = frappe.get_doc({
                "doctype": "Mentor",
                "first_name": data.get("first_name"),
                "last_name": data.get("last_name"),
                "email_id": email,
                "mobile_no": mobile
            })

            mentor.insert(ignore_permissions=True)

        create_mentor_user(mentor)

        if frappe.db.exists("User", email):
            frappe.db.set_value(
                "User",
                email,
                "is_onboarded",
                1
            )

        frappe.db.commit()

        return gen_response(
            status=200,
            message="Mentor onboarding started successfully",
            data={
                "mentor": mentor.name,
                "onboarding_step": 1
            }
        )

    except Exception as e:
        return exception_handel(e)


# ============================================================
# MENTOR — updated
# ============================================================

@frappe.whitelist(allow_guest=True)
def update_mentor(email_id):
    try:
        data = frappe.request.get_json()

        if not data:
            return gen_response(400, "Invalid request data")

        mentor_name = frappe.db.get_value("Mentor", {"email_id": email_id}, "name")
        if not mentor_name:
            return gen_response(404, "Mentor not found")

        mentor = frappe.get_doc("Mentor", mentor_name)
        mentor.flags.ignore_permissions = True

        mentor_skills        = data.pop("skills", [])
        domains              = data.pop("domains", [])
        mentor_platform_urls = data.pop("mentor_platform_urls", [])

        ignore_fields = [
            "name", "doctype", "owner", "creation", "modified",
            "email_id", "mobile_no", "approved_status",
            "total_sessions", "total_hours", "total_earnings", "avg_rating"
        ]

        for key, value in data.items():
            if key not in ignore_fields:
                mentor.set(key, value)

        # Mentor Skills
        mentor.set("mentor_skills", [])
        for row in mentor_skills:
            mentor.append("mentor_skills", {
                "skill": row.get("skill"),
                "level": row.get("level"),
            })

        # Domains
        mentor.set("domain", [])
        for row in domains:
            mentor.append("domain", {"domain": row.get("domain")})

        # Platform URLs
        mentor.set("mentor_platform_urls", [])
        if isinstance(mentor_platform_urls, list):
            for row in mentor_platform_urls:
                if isinstance(row, dict):
                    mentor.append("mentor_platform_urls", {
                        "platform": row.get("platform"),
                        "url":      row.get("url"),
                    })

        mentor.save(ignore_permissions=True)

        # Onboarding status
        if email_id and frappe.db.exists("User", email_id):
            onboarding_status = 0
            if data.get("country"):
                onboarding_status = 2
            if data.get("type"):
                onboarding_status = 3
            frappe.db.set_value("User", email_id, "is_onboarded", onboarding_status)

        frappe.db.commit()

        # ✅ Sync billing
        create_mentor_supplier(mentor)
        sync_billing_account_master(
            email       = email_id,
            data        = data,
            module_type = "mentor",
        )

        return gen_response(200, "Mentor updated successfully", {"mentor": mentor.name})

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "UPDATE MENTOR ERROR")
        return exception_handel(e)


def create_mentor_supplier(mentor):
    try:
        if not mentor.email_id:
            return
        if frappe.db.exists("Supplier", {"supplier_name": mentor.email_id}):
            return
        supplier_name = frappe.db.get_value(
            "Supplier",
            {"email_id": mentor.email_id},
            "name"
        )

        if supplier_name:
            return supplier_name

        supplier = frappe.new_doc("Supplier")
        supplier.supplier_name = mentor.email_id
        supplier.supplier_group = "All Supplier Groups"
        supplier.supplier_type = "Company"
        supplier.email_id = mentor.email_id
        supplier.gstin = mentor.gstin
        supplier.tax_withholding_category = "Professional Fees - Individual"
        supplier.insert(ignore_permissions=True)
        frappe.db.commit()

        return supplier.name

    except DuplicateEntryError:
        return

    except Exception:
        frappe.log_error(
            frappe.get_traceback(),
            "Create Mentor Supplier Error"
        )
        return None



@frappe.whitelist()
def create_mentor_user(mentor=None):

    if not mentor:
        frappe.throw("Mentor data is required")

    if isinstance(mentor, str):
        mentor = frappe.parse_json(mentor)

    email = mentor.get("email_id")
    mobile = mentor.get("mobile_no")

    if not email:
        frappe.throw("Email is required")

    if frappe.db.exists("User", email):

        user = frappe.get_doc("User", email)

        existing_roles = [r.role for r in user.roles]

        if "Mentor" not in existing_roles:
            user.append("roles", {"role": "Mentor"})

        if "Instructor" not in existing_roles:
            user.append("roles", {"role": "Instructor"})

        user.save(ignore_permissions=True)

    else:

        user = frappe.get_doc({
            "doctype": "User",
            "email": email,
            "first_name": mentor.get("first_name"),
            "last_name": mentor.get("last_name"),
            "mobile_no": mobile,
            "enabled": 1,
            "send_welcome_email": 0,
            "roles": [
                {
                    "role": "Mentor"
                },
                {
                    "role": "Instructor"
                }
            ]
        })

        user.insert(ignore_permissions=True)

    mentor_doc = frappe.get_doc(
        "Mentor",
        {"email_id": email}
    )

    mentor_doc.user = email

    mentor_doc.save(ignore_permissions=True)

    return {
        "status": "success",
        "mentor": mentor_doc.name,
        "user": email
    }


@frappe.whitelist(allow_guest=True)
def get_mentor_by_email(email_id):

    try:

        if not email_id:

            return {
                "status": 400,
                "message": "Email is required"
            }


        mentor_name = frappe.db.get_value(
            "Mentor",
            {"email_id": email_id},
            "name"
        )

        if not mentor_name:

            return {
                "status": 404,
                "message": "No mentor found"
            }


        doc = frappe.get_doc(
            "Mentor",
            mentor_name
        )


        data = {

            "name": doc.name,

            "first_name": doc.first_name,
            "last_name": doc.last_name,

            "email_id": doc.email_id,
            "mobile_no": doc.mobile_no,

            "type": doc.type,

            "country": doc.country,
            "state": doc.state,
            "district": doc.district,
            "tahsil": doc.tahsil,
            "city": doc.city,

            "travelling_possible": doc.travelling_possible,

            "profile_description": doc.profile_description,

            "bank_name": doc.bank_name,
            "account_number": doc.account_number,
            "ifsc_code": doc.ifsc_code,

            "approved_status": doc.approved_status,
            "is_active": doc.is_active,

            "total_sessions": doc.total_sessions,
            "total_hours": doc.total_hours,
            "total_earnings": doc.total_earnings,
            "avg_rating": doc.avg_rating,
            "role":doc.role,
            "experience":doc.experience,

            # "terms_accepted": doc.terms_accepted,


            # "skills": [

            #     {
            #         "name": row.name,
            #         "skill": row.skill,
            #         "level": row.level
            #     }

            #     for row in doc.skills
            # ],


            # "domains": [

            #     {
            #         "name": row.name,
            #         "domain": row.domain
            #     }

            #     for row in doc.domains
            # ],

            "mentor_platform_urls": [

                {
                    "name": row.name,
                    "platform": row.platform,
                    "url": row.url
                }

                for row in doc.mentor_platform_urls
            ],
            "mentor_verification": [

                {
                    "verification": row.verification,
                    "status": row.status,
                   
                }

                for row in doc.mentor_verification
            ]
        }

        return {
            "status": 200,
            "message": "Mentor fetched successfully",
            "data": data
        }

    except Exception as e:

        frappe.log_error(
            frappe.get_traceback(),
            "GET MENTOR ERROR"
        )

        return {
            "status": 500,
            "message": str(e)
        }



DEFAULT_PAGE_SIZE = 20

@frappe.whitelist(allow_guest=True)
def get_mentor_list(college=None, page=1, search=None, page_size=DEFAULT_PAGE_SIZE):
    try:
        page, page_size, limit, offset = get_pagination_params(page, page_size)

        # ── Base filters (AND conditions) ───────────────────────────────────
        filters = {}
        if college:
            filters["college"] = college

        # ── OR-based search filters using correct fieldnames ───────────────
        if search:
            search_term = f"%{search.strip()}%"
            or_filters = [
                ["Mentor", "first_name", "like", search_term],
                ["Mentor", "last_name", "like", search_term],
                ["Mentor", "email_id", "like", search_term],
                ["Mentor", "city", "like", search_term],
                ["Mentor", "state", "like", search_term],
            ]
        else:
            or_filters = None

        # ── Cache key unique to every (college, search, page, page_size) ───
        cache_key = make_cache_key(
            "mentor_list",
            college=college,
            search=search,
            page=page,
            page_size=page_size,
        )

        cached = frappe.cache().get_value(cache_key)
        if cached:
            return cached

        # ── Total count ──────────────────────────────────────────────────────
        total = len(
            frappe.get_all(
                "Mentor",
                filters=filters,
                or_filters=or_filters,
                pluck="name",
            )
        )

        # ── Paginated fetch ─────────────────────────────────────────────────
        mentors = frappe.get_all(
            "Mentor",
            filters=filters,
            or_filters=or_filters,
            fields=["*"],
            order_by="creation desc",
            limit=limit,
            start=offset,
        )

        result = gen_response(
            status=200,
            message="Mentor list fetched successfully",
            data={
                "Mentor": mentors,
                "pagination": make_pagination_meta(total, page, page_size),
            },
        )

        frappe.cache().set_value(cache_key, result, expires_in_sec=CACHE_TTL)
        return result

    except Exception as e:
        return exception_handel(e)


# ============================================================
# DOMAIN REQUEST APIs
# ============================================================

@frappe.whitelist(allow_guest=True)
def request_new_domain(domain_name, mentor_email=None):
    """
    Mentor-facing API to submit a new domain request.

    Validations:
      1. Empty / whitespace domain_name
      2. Domain already exists in Domain master
      3. Duplicate pending request for the same domain_name

    Returns:
      {"success": True/False, "message": "..."}
    """
    try:
        # 1. Empty check
        domain_name = (domain_name or "").strip()
        if not domain_name:
            return {"success": False, "message": "Domain name is required"}

        # 2. Duplicate check in Domain master
        if frappe.db.exists("Domain", {"domain": domain_name}):
            return {"success": False, "message": "Domain already exists"}

        # 3. Duplicate pending request check
        existing_request = frappe.db.exists(
            "Domain Request",
            {"domain_name": domain_name, "status": "Pending"},
        )
        if existing_request:
            return {
                "success": False,
                "message": "Domain request already submitted and awaiting approval",
            }

        # Resolve mentor from email if not explicitly passed
        mentor_name = None
        if mentor_email:
            mentor_name = frappe.db.get_value("Mentor", {"email_id": mentor_email}, "name")
        elif frappe.session.user != "Guest":
            mentor_name = frappe.db.get_value(
                "Mentor", {"email_id": frappe.session.user}, "name"
            )

        # 4. Create Domain Request
        doc = frappe.get_doc(
            {
                "doctype": "Domain Request",
                "domain_name": domain_name,
                "mentor": mentor_name,
                "mentor_email": mentor_email or (frappe.session.user if frappe.session.user != "Guest" else None),
                "requested_by": frappe.session.user,
                "status": "Pending",
            }
        )
        doc.insert(ignore_permissions=True)
        frappe.db.commit()

        return {
            "success": True,
            "message": "Domain request submitted successfully",
            "data": {"domain_request": doc.name},
        }

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "REQUEST NEW DOMAIN ERROR")
        return {"success": False, "message": str(e)}


@frappe.whitelist()
def approve_domain_request(name):
    """
    Admin API to approve a Domain Request.

    On approval:
      - Updates status to Approved
      - Stamps approved_by and approved_on
      - Auto-creates the Domain master record (handled by DomainRequest.on_update)

    Returns:
      {"success": True/False, "message": "..."}
    """
    try:
        doc = frappe.get_doc("Domain Request", name)

        if doc.status != "Pending":
            return {
                "success": False,
                "message": f"Cannot approve a request that is already '{doc.status}'",
            }

        doc.status = "Approved"
        doc.save(ignore_permissions=True)
        frappe.db.commit()

        return {
            "success": True,
            "message": f"Domain '{doc.domain_name}' has been approved and added to the Domain master",
        }

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "APPROVE DOMAIN REQUEST ERROR")
        return {"success": False, "message": str(e)}


@frappe.whitelist()
def reject_domain_request(name, reason=None):
    """
    Admin API to reject a Domain Request.

    On rejection:
      - Updates status to Rejected
      - Stores rejection_reason

    No Domain master record is created.

    Returns:
      {"success": True/False, "message": "..."}
    """
    try:
        doc = frappe.get_doc("Domain Request", name)

        if doc.status != "Pending":
            return {
                "success": False,
                "message": f"Cannot reject a request that is already '{doc.status}'",
            }

        doc.status = "Rejected"
        if reason:
            doc.rejection_reason = reason.strip()

        doc.save(ignore_permissions=True)
        frappe.db.commit()

        return {
            "success": True,
            "message": f"Domain request for '{doc.domain_name}' has been rejected",
        }

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "REJECT DOMAIN REQUEST ERROR")
        return {"success": False, "message": str(e)}