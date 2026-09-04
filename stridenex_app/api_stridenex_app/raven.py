# raven_api.py
#
# Place inside any installed Frappe app, e.g.:
#   apps/your_app/your_app/api/raven_api.py
#
# Every function is callable at:
#   /api/method/your_app.api.raven_api.<function_name>
#
# All functions require a logged-in session (cookie-based) and use
# ignore_permissions=True internally after their own checks, so regular
# users don't need direct Role Permission Manager access to the Raven
# doctypes (which is what causes the "Insufficient Permission" error when
# calling /api/resource/Raven Channel etc. directly).

import frappe
from frappe import _


def _require_login():
    if frappe.session.user == "Guest":
        frappe.throw(_("You must be logged in"), frappe.PermissionError)


def _is_channel_member(channel_id, user=None):
    user = user or frappe.session.user
    return frappe.db.exists("Raven Channel Member", {"channel_id": channel_id, "user_id": user})


def _is_admin():
    return "System Manager" in frappe.get_roles()


# ===========================================================================
# CHANNELS
# ===========================================================================

import frappe

@frappe.whitelist(allow_guest=True)
def list_channels(channel_type="Public", include_archived=False):
    """
    List channels visible to the current user, with member and message counts.
    channel_type: "Public" | "Private" | "Open" (omit for all)
    """
    # _require_login()

    conditions = []
    values = {}

    if channel_type:
        conditions.append("rc.type = %(channel_type)s")
        values["channel_type"] = channel_type

    if not include_archived:
        conditions.append("rc.is_archived = 0")

    where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    channels = frappe.db.sql(f"""
        SELECT
            rc.name,
            rc.channel_name,
            rc.type,
            rc.channel_description,
            rc.is_archived,
            rc.owner,
            rc.creation,
            rc.modified,
            (
                SELECT COUNT(*)
                FROM `tabRaven Channel Member` rcm
                WHERE rcm.channel_id = rc.name
            ) AS member_count,
            (
                SELECT COUNT(*)
                FROM `tabRaven Message` rm
                WHERE rm.channel_id = rc.name
            ) AS message_count
        FROM `tabRaven Channel` rc
        {where_clause}
        ORDER BY rc.creation DESC
    """, values, as_dict=True)

    return channels


@frappe.whitelist()
def get_channel(channel_id):
    """Get full details of a single channel."""
    _require_login()
    if not frappe.db.exists("Raven Channel", channel_id):
        frappe.throw(_("Channel not found"))
    return frappe.get_doc("Raven Channel", channel_id).as_dict()


@frappe.whitelist()
def create_channel(channel_name, type="Public", channel_description=""):
    """Create a channel. Creator is auto-added as a member."""
    _require_login()

    doc = frappe.get_doc({
        "doctype": "Raven Channel",
        "channel_name": channel_name,
        "type": type,
        "channel_description": channel_description,
    })
    doc.insert(ignore_permissions=True)

    frappe.get_doc({
        "doctype": "Raven Channel Member",
        "channel_id": doc.name,
        "user_id": frappe.session.user,
    }).insert(ignore_permissions=True)

    return doc.as_dict()


@frappe.whitelist()
def update_channel(channel_id, channel_name=None, channel_description=None):
    """Rename or update a channel's description. Members only."""
    _require_login()
    if not _is_channel_member(channel_id) and not _is_admin():
        frappe.throw(_("You are not a member of this channel"), frappe.PermissionError)

    doc = frappe.get_doc("Raven Channel", channel_id)
    if channel_name is not None:
        doc.channel_name = channel_name
    if channel_description is not None:
        doc.channel_description = channel_description
    doc.save(ignore_permissions=True)
    return doc.as_dict()


@frappe.whitelist()
def archive_channel(channel_id):
    """Archive (soft-delete) a channel. Owner or admin only."""
    _require_login()
    doc = frappe.get_doc("Raven Channel", channel_id)

    if doc.owner != frappe.session.user and not _is_admin():
        frappe.throw(_("Only the channel owner or an admin can archive this channel"), frappe.PermissionError)

    doc.is_archived = 1
    doc.save(ignore_permissions=True)
    return {"archived": channel_id}


@frappe.whitelist()
def delete_channel(channel_id):
    """Permanently delete a channel and its messages/members. Owner or admin only."""
    _require_login()
    doc = frappe.get_doc("Raven Channel", channel_id)

    if doc.owner != frappe.session.user and not _is_admin():
        frappe.throw(_("Only the channel owner or an admin can delete this channel"), frappe.PermissionError)

    frappe.db.delete("Raven Message", {"channel_id": channel_id})
    frappe.db.delete("Raven Channel Member", {"channel_id": channel_id})
    doc.delete(ignore_permissions=True)
    return {"deleted": channel_id}


# ===========================================================================
# MESSAGES
# ===========================================================================

# @frappe.whitelist(allow_guest=True)
# def list_messages(channel_id,channel_category, limit=50, start=0, order="asc"):
#     """List messages in a channel."""
#     # _require_login()
#     return frappe.get_all(
#         "Raven Message",
#         filters={"channel_id": channel_id},
#         fields=[
#     "name",
#     "channel_id",
#     "text",
#     "owner",
#     "message_type",
#     "creation",
#     "is_edited",
#     "is_reply",
#     "linked_message",
#     "replied_message_details",
# ],
#         order_by=f"creation {order}",
#         limit_page_length=limit,
#         limit_start=start,
#     )
@frappe.whitelist(allow_guest=True)
def list_messages(channel_id, channel_category=None, limit=50, start=0, order="asc"):
    """List messages in a channel."""

    if not channel_id:
        frappe.throw("Channel ID is required.")

    # limit = cint(limit)
    # start = cint(start)

    # Prevent SQL injection
    order = (order or "asc").lower()
    if order not in ["asc", "desc"]:
        order = "asc"

    filters = {
        "channel_id": channel_id
    }

    # If you want to filter by channel category as well
    if channel_category:
        filters["channel_category"] = channel_category

    return frappe.get_all(
        "Raven Message",
        filters=filters,
        fields=[
            "name",
            "channel_id",
            "text",
            "owner",
            "message_type",
            "creation",
            "is_edited",
            "is_reply",
            "linked_message",
            "replied_message_details",
            "channel_category"
        ],
        order_by=f"creation {order}",
        limit_page_length=limit,
        limit_start=start,
    )

@frappe.whitelist()
def get_message(message_id):
    _require_login()
    return frappe.get_doc("Raven Message", message_id).as_dict()


@frappe.whitelist()
def send_message():
    """Send a message to a channel."""
    _require_login()

    channel_id = frappe.form_dict.get("channel_id")
    text = frappe.form_dict.get("text")
    reply_to_message = frappe.form_dict.get("reply_to_message")
    file = frappe.form_dict.get("file")
    message_type = frappe.form_dict.get("message_type") or "Text"

    if not channel_id:
        frappe.throw(_("Channel ID is required"))

    if not text:
        frappe.throw(_("Message text is required"))

    if not frappe.db.exists("Raven Channel", channel_id):
        frappe.throw(_("Channel not found"))

    doc = frappe.get_doc({
        "doctype": "Raven Message",
        "channel_id": channel_id,
        "text": text,
        "message_type": message_type,
        "file": file,   # <-- comma added here
        **({"reply_to_message": reply_to_message} if reply_to_message else {}),
    })

    doc.insert(ignore_permissions=True)
    return doc.as_dict()


@frappe.whitelist()
def edit_message(message_id, text):
    """Edit a message. Author or admin only."""
    _require_login()
    doc = frappe.get_doc("Raven Message", message_id)

    if doc.owner != frappe.session.user and not _is_admin():
        frappe.throw(_("You can only edit your own messages"), frappe.PermissionError)

    doc.text = text
    doc.is_edited = 1
    doc.save(ignore_permissions=True)
    return doc.as_dict()


@frappe.whitelist()
def delete_message(message_id):
    """Delete a message. Author or admin only."""
    _require_login()
    doc = frappe.get_doc("Raven Message", message_id)

    if doc.owner != frappe.session.user and not _is_admin():
        frappe.throw(_("You can only delete your own messages"), frappe.PermissionError)

    doc.delete(ignore_permissions=True)
    return {"deleted": message_id}

@frappe.whitelist()
def get_replies(message_id):
    """Get all replies to a particular message."""
    _require_login()

    if not frappe.db.exists("Raven Message", message_id):
        frappe.throw(_("Message not found"))

    replies = frappe.get_all(
        "Raven Message",
        filters={"is_reply": message_id},
        fields=[
            "name",
            "channel_id",
            "text",
            "message_type",
            "owner",
            "creation",
            "modified",
            "is_edited",
            "is_reply"
           
        ],
        order_by="creation asc",
    )

    return {
        "message_id": message_id,
        "reply_count": len(replies),
        "replies": replies,
    }
@frappe.whitelist()
def upload_and_send_file(channel_id, file_url, message_type="File"):
    """
    Attach an already-uploaded file to a message.
    Upload the file first via Frappe's core /api/method/upload_file,
    then pass the returned file_url here.
    """
    _require_login()
    doc = frappe.get_doc({
        "doctype": "Raven Message",
        "channel_id": channel_id,
        "message_type": message_type,
        "file": file_url,
    })
    doc.insert(ignore_permissions=True)
    return doc.as_dict()


# ===========================================================================
# MEMBERS
# ===========================================================================

@frappe.whitelist()
def list_members(channel_id):
    """List members of a channel."""
    _require_login()
    return frappe.get_all(
        "Raven Channel Member",
        filters={"channel_id": channel_id},
        fields=["name", "user_id", "channel_id", "creation"],
    )


@frappe.whitelist()
def add_member(channel_id, user_id):
    """Add a user to a channel. Existing members or admin only."""
    _require_login()
    if not _is_channel_member(channel_id) and not _is_admin():
        frappe.throw(_("Only existing members can add new members"), frappe.PermissionError)

    if frappe.db.exists("Raven Channel Member", {"channel_id": channel_id, "user_id": user_id}):
        return {"already_member": True}

    doc = frappe.get_doc({
        "doctype": "Raven Channel Member",
        "channel_id": channel_id,
        "user_id": user_id,
    })
    doc.insert(ignore_permissions=True)
    return doc.as_dict()


@frappe.whitelist()
def remove_member(channel_id, user_id):
    """Remove a member. Self-removal (leave) or admin only."""
    _require_login()

    if user_id != frappe.session.user and not _is_admin():
        frappe.throw(_("You can only remove yourself unless you're an admin"), frappe.PermissionError)

    member = frappe.db.get_value(
        "Raven Channel Member", {"channel_id": channel_id, "user_id": user_id}, "name"
    )
    if not member:
        frappe.throw(_("User is not a member of this channel"))

    frappe.delete_doc("Raven Channel Member", member, ignore_permissions=True)
    return {"removed": user_id, "channel_id": channel_id}


@frappe.whitelist(allow_guest=True)
def join_channel(channel_id):
    """Current user joins a Public/Open channel directly."""
    # _require_login()
    channel = frappe.get_doc("Raven Channel", channel_id)

    if channel.type == "Private" and not _is_admin():
        frappe.throw(_("This is a private channel — you need an invite"), frappe.PermissionError)

    if frappe.db.exists("Raven Channel Member", {"channel_id": channel_id, "user_id": frappe.session.user}):
        return {"already_member": True}

    doc = frappe.get_doc({
        "doctype": "Raven Channel Member",
        "channel_id": channel_id,
        "user_id": frappe.session.user,
    })
    doc.insert(ignore_permissions=True)
    return doc.as_dict()


@frappe.whitelist()
def leave_channel(channel_id):
    """Current user leaves a channel."""
    return remove_member(channel_id, frappe.session.user)


# ===========================================================================
# USERS (for member pickers, @mentions, etc.)
# ===========================================================================

@frappe.whitelist()
def list_users(search=None, limit=20):
    """List enabled users, optionally filtered by name/email search."""
    _require_login()
    filters = {"enabled": 1}
    if search:
        filters["full_name"] = ["like", f"%{search}%"]

    return frappe.get_all(
        "User",
        filters=filters,
        fields=["name", "full_name", "user_image"],
        limit_page_length=limit,
    )

@frappe.whitelist(allow_guest=True)
def get_category_list(parent_category=None):
    filters = {"is_active": 1}

    # if parent_category:
    #     filters["parent_category"] = parent_category

    categories = frappe.get_all(
        "Channel Category",
        filters=filters,
        fields=["name", "parent_category", "category_name", "description", "icon", "color", "display_order"],
        order_by="display_order asc"
    )
    return categories