# Copyright (c) 2026, QTPL and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import now_datetime


class CollegeCampusDrives(Document):
    pass


@frappe.whitelist(allow_guest=True)
def get_drives_by_college(college):
    try:
        if not college:
            return {"status": 400, "message": "College is required"}

        result = []

        # ✅ Step 1: Fetch drives based on college
        industries = frappe.get_all(
            "College Campus Drives",
            filters={"college": college},
            fields=["name"]
        )

        # ✅ Step 2: Fetch full details
        for item in industries:
            doc = frappe.get_doc("College Campus Drives", item.name)

            data = {
                "name": doc.name,
                "industry":doc.industry,
                "registeration_deadline":doc.registeration_deadline,
                "drive_date":doc.drive_date,
                "package_offered":doc.package_offered,
                "backlog":doc.backlog,
                "criteria":doc.criteria,
                "role":doc.role,
                

                "designation": [
                    {
                        "name": row.name,
                        "designation": row.designation
                    }
                    for row in doc.designation
                ],

                "department": [
                    {
                        "name": row.department
                    }
                    for row in doc.department
                ]
            }

            result.append(data)

        return {
            "status": 200,
            "message": "College Drives fetched successfully",
            "data": result
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

        # ✅ Parent fields
        doc.college = data.get("college")
        doc.industry = data.get("industry")
        doc.registeration_deadline = data.get("registeration_deadline")
        doc.drive_date = data.get("drive_date")
        doc.package_offered = data.get("package_offered")
        doc.backlog = data.get("backlog")
        doc.criteria = data.get("criteria")
        doc.role = data.get("role")

        # ✅ Child Table: Designation
        for d in data.get("designation", []):
            doc.append("designation", {
                "designation": d.get("designation")
            })

        # ✅ Child Table: Department
        for d in data.get("department", []):
            doc.append("department", {
                "department": d.get("name")
            })

        doc.insert(ignore_permissions=True)
        frappe.db.commit()

        return {
            "status": 200,
            "message": "Drive created successfully",
            "name": doc.name
        }

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Create Drive Error")
        return {"status": 500, "message": str(e)}

@frappe.whitelist(allow_guest=True)
def update_drive(name):
    try:
        data = frappe.request.get_json()

        if not name:
            return {"status": 400, "message": "Drive name is required"}

        doc = frappe.get_doc("College Campus Drives", name)

        # ✅ Update parent fields
        doc.college = data.get("college", doc.college)
        doc.industry = data.get("industry", doc.industry)
        doc.registeration_deadline = data.get("registeration_deadline", doc.registeration_deadline)
        doc.drive_date = data.get("drive_date", doc.drive_date)
        doc.package_offered = data.get("package_offered", doc.package_offered)
        doc.backlog = data.get("backlog", doc.backlog)
        doc.criteria = data.get("criteria", doc.criteria)
        doc.role = data.get("role", doc.role)

        # ✅ Clear & Update Designation
        if "designation" in data:
            doc.set("designation", [])
            for d in data.get("designation", []):
                doc.append("designation", {
                    "designation": d.get("designation")
                })

        # ✅ Clear & Update Department
        if "department" in data:
            doc.set("department", [])
            for d in data.get("department", []):
                doc.append("department", {
                    "department": d.get("name")
                })

        doc.save(ignore_permissions=True)
        frappe.db.commit()

        return {
            "status": 200,
            "message": "Drive updated successfully"
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
            "message": "Drive deleted successfully"
        }

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Delete Drive Error")
        return {"status": 500, "message": str(e)}

@frappe.whitelist(allow_guest=True)
def get_drive_count(college=None):
    try:
        filters = {}

        # ✅ Optional filter
        if college:
            filters["college"] = college

        count = frappe.db.count("College Campus Drives", filters)

        return {
            "status": 200,
            "message": "Drive count fetched successfully",
            "count": count
        }

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Drive Count Error")
        return {"status": 500, "message": str(e)}
    
@frappe.whitelist(allow_guest=True)
def open_registration_count(college=None):
    try:
        filters = {
            # ✅ registration still open
            "registeration_deadline": (">=", now_datetime())
        }

        # ✅ Optional filter
        if college:
            filters["college"] = college
        count = frappe.db.count("College Campus Drives", filters)

        return {
            "status": 200,
            "message": "Open registration count fetched successfully",
            "count": count
        }

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Open Registration Count Error")
        return {"status": 500, "message": str(e)}
    
@frappe.whitelist(allow_guest=True)
def get_drive_count_by_name(name=None, status=None):
    try:
        filters = {}

        # ✅ Filter by name
        if name:
            filters["name"] = name

        # ✅ Filter by multiple statuses (comma-separated)
        if status:
            status_list = status.split(",")  # e.g. Applied,Shortlisted,Tech Interview
            filters["status"] = ["in", status_list]

        count = frappe.db.count("College Campus Drives", filters)

        return {
            "status": 200,
            "message": "Drive count fetched successfully",
            "count": count
        }

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Drive Count Error")
        return {"status": 500, "message": str(e)}
    
@frappe.whitelist(allow_guest=True)
def get_drive_list(name=None, status=None):
    try:
        filters = {}

        # ✅ Filter by name
        if name:
            filters["name"] = name

        # ✅ Filter by multiple statuses
        if status:
            status_list = status.split(",")
            filters["status"] = ["in", status_list]

        data = frappe.get_all(
            "College Campus Drives",
            filters=filters,
            fields=["name", "status", "creation", "owner"],
            order_by="creation desc"
        )

        return {
            "status": 200,
            "message": "Drive list fetched successfully",
            "data": data
        }

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Drive List Error")
        return {"status": 500, "message": str(e)}