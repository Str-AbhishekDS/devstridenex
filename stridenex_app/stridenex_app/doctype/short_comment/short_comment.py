# Copyright (c) 2026, QTPL and contributors
# For license information, please see license.txt

# import frappe
from frappe.model.document import Document


class ShortComment(Document):
	pass


import frappe

@frappe.whitelist()
def add_comment(short, content, parent_comment=None):
    doc = frappe.get_doc({
        "doctype": "Short Comment",
        "short": short,
        "content": content,
        "parent_comment": parent_comment,
        "comment_by": frappe.session.user
    })
    doc.insert(ignore_permissions=False)
    return doc

@frappe.whitelist()
def toggle_like(comment):
    user = frappe.session.user
    existing = frappe.db.exists("Short Comment Like", {"comment": comment, "liked_by": user})
    if existing:
        frappe.delete_doc("Short Comment Like", existing)
        frappe.db.set_value("Short Comment", comment, "like_count",
            frappe.db.count("Short Comment Like", {"comment": comment}))
        return {"liked": False}
    else:
        frappe.get_doc({
            "doctype": "Short Comment Like",
            "comment": comment,
            "liked_by": user
        }).insert(ignore_permissions=False)
        frappe.db.set_value("Short Comment", comment, "like_count",
            frappe.db.count("Short Comment Like", {"comment": comment}))
        return {"liked": True}

# @frappe.whitelist()
# def get_comments(short):
#     top_level = frappe.get_all("Short Comment",
#         filters={"short": short, "parent_comment": ["is", "not set"]},
#         fields=["name", "content", "comment_by", "creation", "like_count", "is_pinned"],
#         order_by="is_pinned desc, creation desc")

#     for c in top_level:
#         c["replies"] = frappe.get_all("Short Comment",
#             filters={"parent_comment": c["name"]},
#             fields=["name", "content", "comment_by", "creation", "like_count"],
#             order_by="creation asc")
#     return top_level


import frappe


def get_replies(parent_comment):
    replies = frappe.get_all(
        "Short Comment",
        filters={"parent_comment": parent_comment},
        fields=[
            "name",
            "content",
            "comment_by",
            "creation",
            "like_count",
            "is_pinned",
        ],
        order_by="creation asc",
    )

    for reply in replies:
        reply["replies"] = get_replies(reply["name"])

    return replies


@frappe.whitelist()
def get_comments(short):
    comments = frappe.get_all(
        "Short Comment",
        filters={
            "short": short,
            "parent_comment": ["is", "not set"],
        },
        fields=[
            "name",
            "content",
            "comment_by",
            "creation",
            "like_count",
            "is_pinned",
        ],
        order_by="is_pinned desc, creation desc",
    )

    for comment in comments:
        comment["replies"] = get_replies(comment["name"])

    comment_count = frappe.db.count(
        "Short Comment",
        filters={
            "short": short,
            "parent_comment": ["is", "not set"],
        },
    )

    return {
        "comment_count": comment_count,
        "comments": comments,
          }