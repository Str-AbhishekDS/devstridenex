# Copyright (c) 2026, QTPL and contributors
# For license information, please see license.txt

# import frappe
from frappe.model.document import Document

import frappe

from frappe.utils import today
from stridenex_app.api_stridenex_app.app_utils import (
    gen_response,
    exception_handel
)

class IndustrySkillDomain(Document):
	pass


@frappe.whitelist(allow_guest=True)
def get_skill_domain(industry=None):
    try:
        filters = {}

        if industry:
            filters["industry"] = industry

        domains = frappe.get_all(
            "Industry Skill Domain",
            filters=filters,
            fields=["*"],
            order_by="creation desc"
        )

        for domain in domains:
            # 👇 Skills child table
            skills = frappe.get_all(
                "Student Skill Table",
                filters={"parent": domain["name"]},
                fields=["skill"]
            )

            # 👇 Roles child table
            roles = frappe.get_all(
                "Industry Designation Table",
                filters={"parent": domain["name"]},
                fields=["designation"]
            )

            # ✅ Assign separately
            domain["skills"] = skills
            domain["roles"] = roles

        return gen_response(
            status=200,
            message="Industry Skill Domain fetched successfully",
            data=domains
        )

    except Exception as e:
        return exception_handel(e)

@frappe.whitelist(allow_guest=True)
def update_skill_domain(name):
    try:
        data = frappe.request.get_json()

        # Fetch existing document
        domain = frappe.get_doc("Industry Skill Domain", name)

        # 🔹 Update main fields (industry, skill_domain, etc.)
        for key, value in data.items():
            if key not in ["skills", "roles"]:
                setattr(domain, key, value)

        # ✅ FIXED: Clear & Rebuild Skills Table
        if "skills" in data:
            domain.set("table_cxek", [])  # 👈 Clear existing
            for skill in data["skills"]:
                if skill.get("skill"):
                    domain.append("table_cxek", {
                        "skill": skill.get("skill")
                    })

        # ✅ FIXED: Clear & Rebuild Roles Table  
        if "roles" in data:
            domain.set("designation", [])  # 👈 Clear existing
            for role in data["roles"]:
                if role.get("designation"):
                    domain.append("designation", {
                        "designation": role.get("designation")
                    })

        domain.save(ignore_permissions=True)
        frappe.db.commit()

        return gen_response(
            status=200,
            message="Industry Skill Domain updated successfully",
            data={"name": domain.name}
        )

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "update_skill_domain_error")
        return exception_handel(e)
    
@frappe.whitelist(allow_guest=True)
def delete_skill_domain(name):
    try:
        if not frappe.db.exists("Industry Skill Domain", name):
            return gen_response(
                status=404,
                message="Industry Skill Domain not found",
                data={}
            )

        frappe.delete_doc("Industry Skill Domain", name, ignore_permissions=True)
        frappe.db.commit()

        return gen_response(
            status=200,
            message="Industry Skill Domain deleted successfully",
            data={"name": name}
        )

    except Exception as e:
        return exception_handel(e)


@frappe.whitelist(allow_guest=True)
def create_skill_domain():
    try:
        data = frappe.request.get_json()
        domain = frappe.new_doc("Industry Skill Domain")

        domain.industry = data.get("industry")
        domain.skill_domain = data.get("skill_domain")
        domain.domain = data.get("domain")              # ✅ ADD THIS
        domain.sub_domain = data.get("sub_domain") 

        # 🔄 TRY THESE ONE BY ONE:
        if "skills" in data:
            for skill in data["skills"]:
                # Option 1 👇
                domain.append("table_cxek", {
                    "skill": skill.get("skill")
                })
                

        if "roles" in data:
            for role in data["roles"]:
                # Option 1 👇
                domain.append("designation", {
                    "designation": role.get("designation")
                })
                

        domain.insert(ignore_permissions=True)
        frappe.db.commit()
        return gen_response(status=200, message="Success", data={"name": domain.name})

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "create_skill_domain")
        return {"status": 500, "message": str(e), "data": []}

        