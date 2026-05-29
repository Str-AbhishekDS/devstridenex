# import frappe

# def lms_batch_query_conditions(user=None):
#     """
#     Restrict LMS Batch visibility:
#     - System Manager / LMS Manager / Administrator → see all
#     - Mentor → see only batches where they are the instructor
#     """
#     if not user:
#         user = frappe.session.user

#     roles = frappe.get_roles(user)
#     if "System Manager" in roles or "LMS Manager" in roles or user == "Administrator":
#         return ""

#     # Mentor doctype uses email_id as its name (autoname: field:email_id)
#     # So Mentor.name == user's email == frappe.session.user
#     mentor_exists = frappe.db.exists("Mentor", {"email_id": user})
#     if not mentor_exists:
#         return ""

#     # LMS Batch Instructor child table: instructor field links to User
#     return """
#         `tabLMS Batch`.name IN (
#             SELECT parent FROM `tabLMS Batch Instructor`
#             WHERE instructor = {user}
#         )
#     """.format(user=frappe.db.escape(user))
    
    
# def has_permission(doc, user=None, permission_type=None):

#     user = user or frappe.session.user

#     if "System Manager" in frappe.get_roles(user):
#         return True

#     if doc.mentor == user:
#         return True

#     return False