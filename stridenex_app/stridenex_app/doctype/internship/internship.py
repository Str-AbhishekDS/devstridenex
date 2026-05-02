import frappe
from frappe.model.document import Document
from frappe.utils import today
from stridenex_app.api_stridenex_app.app_utils import (
    gen_response,
    exception_handel
)
class Internship(Document):
    def validate(self):
        # Deadline validation
        if self.deadline and self.deadline < today():
            frappe.throw("Deadline cannot be in the past")

    def before_save(self):
        # Auto status handling
        if self.deadline:
            if self.deadline < today():
                self.status = "Closed"
            elif not self.status:
                self.status = "Active"
                
@frappe.whitelist()
def get_match_score(student, internship):

    required_skills = frappe.get_all(
        "Internship skill table",
        filters={"parent": internship},
        pluck="skill"
    )

    student_skills = frappe.get_all(
        "Student Skill Table",
        filters={"student": student},   # ✅ FIXED HERE
        pluck="skill"
    )

    if not required_skills:
        return 100

    matched = list(set(required_skills) & set(student_skills))

    score = (len(matched) / len(required_skills)) * 100

    return round(score)

@frappe.whitelist(allow_guest=True)
def create_internship():
    try:
        data = frappe.request.get_json()

        internship = frappe.get_doc({
            "doctype": "Internship",
            **data
        })

        internship.insert(ignore_permissions=True)
        frappe.db.commit()

        return gen_response(
            status=200,
            message="Internship registered successfully",
            data={"name": internship.title}
        )

    except Exception as e:
        return exception_handel(e)
        
@frappe.whitelist(allow_guest=True)
def get_internship_list(industry=None, student=None):
    try:
        filters = {}

        if industry:
            filters["industry"] = industry

        internships = frappe.get_all(
            "Internship",
            filters=filters,
            fields=["*"],
            order_by="creation desc"
        )

        internship_names = [i["name"] for i in internships]

        # ✅ Skills mapping
        all_skills = frappe.get_all(
            "Internship Required Skill",
            filters={"parent": ["in", internship_names]},
            fields=["parent", "skill"]
        )

        skill_map = {}
        for s in all_skills:
            skill_map.setdefault(s["parent"], []).append({
                "skill": s["skill"]
            })

        # ✅ Application status mapping
        enrollment_map = {}
        if student:
            enrollments = frappe.get_all(
                "Internship Application",
                filters={"student": student},
                fields=["internship", "status"]
            )

            enrollment_map = {
                e["internship"]: e["status"] for e in enrollments
            }

        # ✅ Final response
        for internship in internships:
            internship["skills"] = skill_map.get(internship["name"], [])

            if student:
                internship["applied_status"] = enrollment_map.get(
                    internship["name"], "Not Applied"
                )
            else:
                internship["applied_status"] = "Not Applied"

        return gen_response(
            status=200,
            message="Internship list fetched successfully",
            data=internships
        )

    except Exception as e:
        return exception_handel(e)
    

@frappe.whitelist(allow_guest=True)
def update_internship():
    try:
        data = frappe.request.get_json()

        name = data.get("name")  # ✅ get from body

        if not name:
            return gen_response(
                status=400,
                message="Name is required",
                data=[]
            )

        project = frappe.get_doc("Internship", name)

        for key, value in data.items():
            if key not in ["required_skills", "name"]:
                setattr(project, key, value)

        if "required_skills" in data:
            project.set("required_skills", [])

            for skill in data["required_skills"]:
                project.append("required_skills", {
                    "skill": skill.get("skill")
                })

        project.save(ignore_permissions=True)
        frappe.db.commit()

        return gen_response(
            status=200,
            message="Internship updated successfully",
            data={"name": project.name}
        )

    except Exception as e:
        return exception_handel(e)
    
@frappe.whitelist(allow_guest=True)
def inactive_internship(name):
    try:
        if not frappe.db.exists("Internship", name):
            return gen_response(
                status=404,
                message="Internship not found",
                data=[]
            )

        project = frappe.get_doc("Internship", name)
        project.status = "Closed"   # or "Inactive"
        project.save(ignore_permissions=True)
        frappe.db.commit()

        return gen_response(
            status=200,
            message="Internship marked as deleted",
            data={"name": name}
        )

    except Exception as e:
        return exception_handel(e)