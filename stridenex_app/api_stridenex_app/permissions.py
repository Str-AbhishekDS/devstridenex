import frappe


def lms_batch_query(user):

    if "System Manager" in frappe.get_roles(user):
        return ""

    if "Mentor" in frappe.get_roles(user):
        return f"`tabLMS Batch`.mentor = '{user}'"

    return "1=0"


def has_permission(doc, user):

    if "System Manager" in frappe.get_roles(user):
        return True

    if doc.mentor == user:
        return True

    return False