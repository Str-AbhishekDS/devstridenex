# Copyright (c) 2026, QTPL and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.exceptions import DuplicateEntryError


class Community(Document):
	pass


@frappe.whitelist(allow_guest=True)
def create_community():
    try:
        data = frappe.request.get_json()

        if not data:
            return {
                "success": False,
                "message": "Request body is required"
            }

        community_name = data.get("community_name")
        description = data.get("description")
        community_type = data.get("community_type", "Public")
        user_type = data.get("user_type")
        community_owner = data.get("community_owner")

        if not community_name:
            return {
                "success": False,
                "message": "Community name is required"
            }

        if community_type not in ["Public", "Private"]:
            return {
                "success": False,
                "message": "Community type must be Public or Private"
            }

        # Check duplicate
        if frappe.db.exists(
            "Community",
            {"community_name": community_name}
        ):
            return {
                "success": False,
                "message": "Community already exists"
            }

        # Create Community
        community = frappe.get_doc({
            "doctype": "Community",
            "community_name": community_name,
            "description": description,
            "community_type": community_type,
            "community_owner": community_owner,
            "user_type": user_type,
            "status": "Active",
            "created_on": frappe.utils.now_datetime()
        })

        community.insert(ignore_permissions=True)

        # Add creator as Admin
        member = frappe.get_doc({
            "doctype": "Community Member",
            "community": community.name,
            "member": frappe.session.user,
            "community_owner": community_owner,
            "role": "Admin",
            "status": "Approved",
            "joined_on": frappe.utils.now_datetime()
        })

        member.insert(ignore_permissions=True)

        frappe.db.commit()

        return {
            "success": True,
            "message": "Community created successfully",
            "data": {
                "name": community.name,
                "community_name": community.community_name,
                "description": community.description,
                "community_type": community.community_type,
                "owner": community.community_owner,
                "status": community.status
            }
        }

    except Exception as e:
        frappe.log_error(
            frappe.get_traceback(),
            "Create Community API Error"
        )

        return {
            "success": False,
            "message": str(e)
        }

@frappe.whitelist(allow_guest=True)
def get_communities(user,user_type=None):
    try:
        data = frappe.request.get_json() or {}

        page = int(data.get("page", 1))
        page_size = int(data.get("page_size", 20))
        search = data.get("search")

        if page < 1:
            page = 1

        if page_size < 1:
            page_size = 20

        limit_start = (page - 1) * page_size

        filters = {
            "status": "Active"
        }
        if user_type:
            filters = {
                        "status": "Active",
                        "user_type": user_type
                    }

        # Get communities
        communities = frappe.get_all(
            "Community",
            filters=filters,
            fields=[
                "name",
                "community_name",
                "description",
                "community_type",
                "owner",
                "cover_image",
                "status",
                "created_on",
                "user_type"
            ],
            order_by="creation desc",
            limit_start=limit_start,
            limit_page_length=page_size
        )

        # Current logged-in user
        current_user = user

        # Get all communities joined by current user
        joined_communities = frappe.get_all(
            "Community Member",
            filters={
                "member": current_user,
                "status": "Approved"
            },
            pluck="community"
        )

        joined_communities = set(joined_communities)

        # Add member count + join/leave flag
        for community in communities:

            community["member_count"] = frappe.db.count(
                "Community Member",
                {
                    "community": community.name,
                    "status": "Approved"
                }
            )

            # Check whether current user joined
            if community.name in joined_communities:
                community["is_member"] = 1
                community["action"] = "leave"
            else:
                community["is_member"] = 0
                community["action"] = "join"

        # Total count
        total_count = frappe.db.count(
            "Community",
            filters=filters
        )

        return {
            "success": True,
            "data": communities,
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total_count": total_count,
                "total_pages": (
                    (total_count + page_size - 1)
                    // page_size
                )
            }
        }

    except Exception as e:

        frappe.log_error(
            frappe.get_traceback(),
            "Get Communities API Error"
        )

        return {
            "success": False,
            "message": str(e)
        }

@frappe.whitelist(allow_guest=True)
def get_community():
    try:
        data = frappe.request.get_json() or {}

        if not data:
            return {
                "success": False,
                "message": "Request body is required"
            }

        community_name = data.get("community")
        user = data.get("user")

        if not community_name:
            return {
                "success": False,
                "message": "Community is required"
            }

        # --------------------------------------------------
        # Get Community
        # --------------------------------------------------

        community = frappe.db.get_value(
            "Community",
            community_name,
            [
                "name",
                "community_name",
                "description",
                "community_type",
                "community_owner",
                "status",
                "created_on"
            ],
            as_dict=True
        )

        if not community:
            return {
                "success": False,
                "message": "Community not found"
            }

        # --------------------------------------------------
        # Get Community Members
        # --------------------------------------------------

        members = frappe.get_all(
            "Community Member",
            filters={
                "community": community_name,
                "status": "Approved"
            },
            fields=[
                "name",
                "member",
                "student",
                "role",
                "status",
                "joined_on"
            ],
            order_by="joined_on asc"
        )

        # --------------------------------------------------
        # Get Channel Categories
        # --------------------------------------------------

        categories = frappe.get_all(
            "Channel Category",
            filters={
                "parent_category": community_name
            },
            fields=[
                "name",
                "category_name"
            ],
            order_by="creation asc"
        )

        # --------------------------------------------------
        # Get Community Tags
        # --------------------------------------------------

        tags = frappe.get_all(
            "Community Tag",
            
            fields=[
                "name",
                "title"
            ],
            order_by="creation asc"
        )

        # --------------------------------------------------
        # Member Count
        # --------------------------------------------------

        community["member_count"] = len(members)

        # --------------------------------------------------
        # Check Current User Membership
        # --------------------------------------------------

        is_member = False
        user_membership = None

        if user:

            for member in members:

                if member.member == user:

                    is_member = True
                    user_membership = member

                    break

        community["is_member"] = is_member
        community["membership"] = user_membership

        # --------------------------------------------------
        # Add Members
        # --------------------------------------------------

        community["members"] = members

        # --------------------------------------------------
        # Add Categories
        # --------------------------------------------------

        community["categories"] = categories

        # --------------------------------------------------
        # Add Tags
        # --------------------------------------------------

        community["tags"] = tags

        # --------------------------------------------------
        # Response
        # --------------------------------------------------

        return {
            "success": True,
            "data": community
        }

    except Exception as e:

        frappe.log_error(
            frappe.get_traceback(),
            "Get Community API Error"
        )

        return {
            "success": False,
            "message": str(e)
        }


        
@frappe.whitelist(allow_guest=True)
def join_community():
    try:
        data = frappe.request.get_json()

        if not data:
            return {
                "success": False,
                "message": "Request body is required"
            }

        community_name = data.get("community")
        student = data.get("student")

        if not community_name:
            return {
                "success": False,
                "message": "Community is required"
            }

        community = frappe.db.get_value(
            "Community",
            community_name,
            [
                "name",
                "community_type",
                "status"
            ],
            as_dict=True
        )

        if not community:
            return {
                "success": False,
                "message": "Community not found"
            }

        if community.status != "Active":
            return {
                "success": False,
                "message": "Community is not active"
            }

        # Check existing membership
        existing = frappe.db.get_value(
            "Community Member",
            {
                "community": community_name,
                "member": frappe.session.user
            },
            [
                "name",
                "status"
            ],
            as_dict=True
        )

        if existing:

            if existing.status == "Approved":
                return {
                    "success": False,
                    "message": "Already a member"
                }

            if existing.status == "Pending":
                return {
                    "success": False,
                    "message": "Membership request is already pending"
                }

        if community.community_type == "Public":
            status = "Approved"
        else:
            status = "Pending"

        member = frappe.get_doc({
            "doctype": "Community Member",
            "community": community_name,
            "member": frappe.session.user,
            "student": student,
            "role": "Member",
            "status": status,
            "joined_on": frappe.utils.now_datetime()
        })

        member.insert(ignore_permissions=True)

        frappe.db.commit()

        return {
            "success": True,
            "message": (
                "Joined community successfully"
                if status == "Approved"
                else "Membership request sent"
            ),
            "data": {
                "name": member.name,
                "community": community_name,
                "member": frappe.session.user,
                "role": "Member",
                "status": status
            }
        }

    except Exception as e:

        frappe.log_error(
            frappe.get_traceback(),
            "Join Community API Error"
        )

        return {
            "success": False,
            "message": str(e)
        }


@frappe.whitelist(allow_guest=True)
def leave_community():
    try:
        data = frappe.request.get_json()

        if not data:
            return {
                "success": False,
                "message": "Request body is required"
            }

        community_name = data.get("community")

        if not community_name:
            return {
                "success": False,
                "message": "Community is required"
            }

        member = frappe.db.get_value(
            "Community Member",
            {
                "community": community_name,
                "member": frappe.session.user
            },
            [
                "name",
                "role"
            ],
            as_dict=True
        )

        if not member:
            return {
                "success": False,
                "message": "You are not a member of this community"
            }

        # Owner/Admin protection
        community_owner = frappe.db.get_value(
            "Community",
            community_name,
            "owner"
        )

        if community_owner == frappe.session.user:
            return {
                "success": False,
                "message": "Community owner cannot leave the community"
            }

        frappe.delete_doc(
            "Community Member",
            member.name,
            ignore_permissions=True
        )

        frappe.db.commit()

        return {
            "success": True,
            "message": "Left community successfully"
        }

    except Exception as e:

        frappe.log_error(
            frappe.get_traceback(),
            "Leave Community API Error"
        )

        return {
            "success": False,
            "message": str(e)
        }


@frappe.whitelist(allow_guest=True)
def create_tag(title):
    try:
        # Check if tag already exists
        existing = frappe.db.exists("Tag", {"title": title})
        if existing:
            return {
                "status": "error",
                "message": "Tag already exists",
                "name": existing
            }

        doc = frappe.get_doc({
            "doctype": "Community Tag",
            "title": title
        })

        doc.insert(ignore_permissions=True)
        frappe.db.commit()

        return {
            "status": "success",
            "message": "Tag created successfully",
            "name": doc.name
        }

    except DuplicateEntryError:
        frappe.throw("Tag already exists.")

    except Exception:
        frappe.log_error(frappe.get_traceback(), "Create Tag API")
        frappe.throw("Unable to create tag.")


@frappe.whitelist(allow_guest=True)
def get_post_detail():
    try:
        data = frappe.request.get_json()

        if not data:
            return {
                "success": False,
                "message": "Request body is required"
            }

        post_name = data.get("post")

        if not post_name:
            return {
                "success": False,
                "message": "Post is required"
            }

        # --------------------------------------------------
        # Get Post
        # --------------------------------------------------
        post = frappe.db.get_value(
            "Community Post",
            post_name,
            [
                "name",
                "community",
                "author",
                "student",
                "content",
                "post_type",
                "attachment",
                "status",
                "posted_on"
            ],
            as_dict=True
        )

        if not post:
            return {
                "success": False,
                "message": "Post not found"
            }

        if post.status != "Published":
            return {
                "success": False,
                "message": "Post is not available"
            }

        # --------------------------------------------------
        # Like Count
        # --------------------------------------------------
        post["like_count"] = frappe.db.count(
            "Community Post Like",
            {
                "post": post_name
            }
        )

        # --------------------------------------------------
        # Comment Count
        # --------------------------------------------------
        post["comment_count"] = frappe.db.count(
            "Community Post Comment",
            {
                "post": post_name,
                "status": "Active"
            }
        )

        # --------------------------------------------------
        # Current User Like
        # --------------------------------------------------
        post["is_liked"] = bool(
            frappe.db.exists(
                "Community Post Like",
                {
                    "post": post_name,
                    "user": frappe.session.user
                }
            )
        )

        # --------------------------------------------------
        # Get All Comments
        # --------------------------------------------------
        comments = frappe.get_all(
            "Community Post Comment",
            filters={
                "post": post_name,
                "status": "Active"
            },
            fields=[
                "name",
                "comment",
                "commented_by",
                "student",
                "posted_on",
                "creation",
                "parent_comment",
                "status"
            ],
            order_by="creation asc"
        )

        # --------------------------------------------------
        # Build Comment Tree
        # --------------------------------------------------
        comment_map = {}

        for comment in comments:

            comment_map[comment.name] = {
                "name": comment.name,
                "content": comment.comment,
                "comment_by": comment.commented_by,
                "student": comment.student,
                "creation": comment.creation,
                "posted_on": comment.posted_on,
                "like_count": frappe.db.count(
                    "Community Post Comment Like",
                    {
                        "comment": comment.name
                    }
                ),
                "is_pinned": 0,
                "replies": []
            }

        # --------------------------------------------------
        # Create Nested Replies
        # --------------------------------------------------
        root_comments = []

        for comment in comments:

            comment_data = comment_map[comment.name]

            if comment.parent_comment:
                parent = comment_map.get(comment.parent_comment)

                if parent:
                    parent["replies"].append(comment_data)

            else:
                root_comments.append(comment_data)

        # --------------------------------------------------
        # Add Comments To Post
        # --------------------------------------------------
        post["comments"] = root_comments

        return {
            "success": True,
            "data": post
        }

    except Exception as e:

        frappe.log_error(
            frappe.get_traceback(),
            "Get Post API Error"
        )

        return {
            "success": False,
            "message": str(e)
        }

@frappe.whitelist(allow_guest=True)
def get_posts():
    try:
        data = frappe.request.get_json() or {}

        community = data.get("community")
        category = data.get("category")
        page = int(data.get("page", 1))
        page_size = int(data.get("page_size", 20))

        if not community:
            return {
                "success": False,
                "message": "Community is required"
            }

        if page < 1:
            page = 1

        if page_size < 1:
            page_size = 20

        limit_start = (page - 1) * page_size

        # Check community
        if not frappe.db.exists(
            "Community",
            community
        ):
            return {
                "success": False,
                "message": "Community not found"
            }

        filters = {
            "community": community,
            "category":category,
            "status": "Published"
        }

        posts = frappe.get_all(
            "Community Post",
            filters=filters,
            fields=[
                "name",
                "community",
                "author",
                "student",
                "category",
                "content",
                "post_type",
                "attachment",
                "status",
                "posted_on"
            ],
            order_by="posted_on desc",
            limit_start=limit_start,
            limit_page_length=page_size
        )

        for post in posts:

            # Like count
            post["like_count"] = frappe.db.count(
                "Community Post Like",
                {
                    "post": post.name
                }
            )

            # Comment count
            post["comment_count"] = frappe.db.count(
                "Community Post Comment",
                {
                    "post": post.name,
                    "status": "Active"
                }
            )

            # Current user liked?
            post["is_liked"] = bool(
                frappe.db.exists(
                    "Community Post Like",
                    {
                        "post": post.name,
                        "user": frappe.session.user
                    }
                )
            )

        total_count = frappe.db.count(
            "Community Post",
            filters=filters
        )

        return {
            "success": True,
            "data": posts,
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total_count": total_count,
                "total_pages": (
                    (total_count + page_size - 1)
                    // page_size
                )
            }
        }

    except Exception as e:

        frappe.log_error(
            frappe.get_traceback(),
            "Get Posts API Error"
        )

        return {
            "success": False,
            "message": str(e)
        }

@frappe.whitelist(allow_guest=True)
def create_post():
    try:
        data = frappe.request.get_json()

        if not data:
            return {
                "success": False,
                "message": "Request body is required"
            }

        community = data.get("community")
        content = data.get("content")
        post_type = data.get("post_type", "Text")
        user = data.get("user")
        attachment = data.get("attachment")
        category = data.get("category")

        if not community and not category:
            return {
                "success": False,
                "message": "Community and category is required"
            }

        if not content and not attachment:
            return {
                "success": False,
                "message": "Content or attachment is required"
            }

        # Check community
        community_exists = frappe.db.exists(
            "Community",
            {
                "name": community,
                "status": "Active"
            }
        )

        if not community_exists:
            return {
                "success": False,
                "message": "Community not found or inactive"
            }

        # # Check membership
        # member = frappe.db.exists(
        #     "Community Member",
        #     {
        #         "community": community,
        #         "member": user,
        #         "status": "Approved"
        #     }
        # )

        # if not member:
        #     return {
        #         "success": False,
        #         "message": "You must join the community before creating a post"
        #     }

        if post_type not in [
            "Text",
            "Image",
            "Video",
            "Link"
        ]:
            return {
                "success": False,
                "message": "Invalid post type"
            }

        post = frappe.get_doc({
            "doctype": "Community Post",
            "community": community,
            "author": frappe.session.user,
            "user": user,
            "content": content,
            "category":category,
            "post_type": post_type,
            "attachment": attachment,
            "status": "Published",
            "posted_on": frappe.utils.now_datetime()
        })

        post.insert(ignore_permissions=True)

        frappe.db.commit()

        return {
            "success": True,
            "message": "Post created successfully",
            "data": {
                "name": post.name,
                "community": post.community,
                "author": post.author,
                "user": post.user,
                "content": post.content,
                "category":post.category,
                "post_type": post.post_type,
                "attachment": post.attachment,
                "status": post.status,
                "posted_on": post.posted_on
            }
        }

    except Exception as e:

        frappe.log_error(
            frappe.get_traceback(),
            "Create Post API Error"
        )

        return {
            "success": False,
            "message": str(e)
        }



@frappe.whitelist(allow_guest=True)
def toggle_comment_like():
    try:
        data = frappe.request.get_json()

        if not data:
            return {
                "success": False,
                "message": "Request body is required"
            }

        comment_name = data.get("comment")
        student = data.get("student")

        if not comment_name:
            return {
                "success": False,
                "message": "Comment is required"
            }

        # Check comment
        comment = frappe.db.get_value(
            "Community Post Comment",
            comment_name,
            ["name", "post", "status"],
            as_dict=True
        )

        if not comment:
            return {
                "success": False,
                "message": "Comment not found"
            }

        if comment.status != "Active":
            return {
                "success": False,
                "message": "Comment is not available"
            }

        user = frappe.session.user

        # Check existing like
        like_name = frappe.db.get_value(
            "Community Post Comment Like",
            {
                "comment": comment_name,
                "user": user
            },
            "name"
        )

        # -----------------------------------------
        # Unlike
        # -----------------------------------------
        if like_name:

            frappe.delete_doc(
                "Community Post Comment Like",
                like_name,
                ignore_permissions=True
            )

            action = "unliked"
            is_liked = False

        # -----------------------------------------
        # Like
        # -----------------------------------------
        else:

            like = frappe.new_doc(
                "Community Post Comment Like"
            )

            like.comment = comment_name
            like.user = user

            if student:
                like.student = student

            like.liked_on = frappe.utils.now_datetime()

            like.insert(ignore_permissions=True)

            action = "liked"
            is_liked = True

        frappe.db.commit()

        # Updated like count
        like_count = frappe.db.count(
            "Community Post Comment Like",
            {
                "comment": comment_name
            }
        )

        return {
            "success": True,
            "message": f"Comment {action} successfully",
            "data": {
                "comment": comment_name,
                "like_count": like_count,
                "is_liked": is_liked
            }
        }

    except Exception as e:

        frappe.log_error(
            frappe.get_traceback(),
            "Toggle Comment Like API Error"
        )

        return {
            "success": False,
            "message": str(e)
        }



@frappe.whitelist(allow_guest=True)
def post_comment():
    try:
        data = frappe.request.get_json()

        if not data:
            return {
                "success": False,
                "message": "Request body is required"
            }

        post_name = data.get("post")
        comment_text = data.get("comment")
        parent_comment = data.get("parent_comment")
        student = data.get("student")

        # -----------------------------------------
        # Validation
        # -----------------------------------------
        if not post_name:
            return {
                "success": False,
                "message": "Post is required"
            }

        if not comment_text:
            return {
                "success": False,
                "message": "Comment is required"
            }

        # -----------------------------------------
        # Check Post
        # -----------------------------------------
        post = frappe.db.get_value(
            "Community Post",
            post_name,
            ["name", "status"],
            as_dict=True
        )

        if not post:
            return {
                "success": False,
                "message": "Post not found"
            }

        if post.status != "Published":
            return {
                "success": False,
                "message": "Post is not available"
            }

        # -----------------------------------------
        # Check Parent Comment
        # -----------------------------------------
        if parent_comment:

            parent = frappe.db.get_value(
                "Community Post Comment",
                parent_comment,
                ["name", "post", "status"],
                as_dict=True
            )

            if not parent:
                return {
                    "success": False,
                    "message": "Parent comment not found"
                }

            if parent.post != post_name:
                return {
                    "success": False,
                    "message": "Parent comment does not belong to this post"
                }

            if parent.status != "Active":
                return {
                    "success": False,
                    "message": "Parent comment is not available"
                }

        # -----------------------------------------
        # Current User
        # -----------------------------------------
        user = frappe.session.user

        # -----------------------------------------
        # Create Comment
        # -----------------------------------------
        doc = frappe.new_doc("Community Post Comment")

        doc.post = post_name
        doc.commented_by = user
        doc.comment = comment_text
        doc.posted_on = frappe.utils.now_datetime()
        doc.status = "Active"

        if student:
            doc.student = student

        if parent_comment:
            doc.parent_comment = parent_comment

        doc.insert(ignore_permissions=True)

        frappe.db.commit()

        # -----------------------------------------
        # Response Data
        # -----------------------------------------
        comment_data = {
            "name": doc.name,
            "content": doc.comment,
            "comment_by": doc.commented_by,
            "student": doc.student,
            "creation": doc.creation,
            "posted_on": doc.posted_on,
            "like_count": 0,
            "is_liked": False,
            "is_pinned": 0,
            "replies": []
        }

        return {
            "success": True,
            "message": (
                "Reply posted successfully"
                if parent_comment
                else "Comment posted successfully"
            ),
            "data": comment_data
        }

    except Exception as e:

        frappe.log_error(
            frappe.get_traceback(),
            "Post Comment API Error"
        )

        return {
            "success": False,
            "message": str(e)
        }

@frappe.whitelist(allow_guest=True)
def create_category():
    try:
        data = frappe.request.get_json()

        if not data:
            return {
                "success": False,
                "message": "Request body is required"
            }

        # -----------------------------------------
        # Get Data
        # -----------------------------------------
        category_name = data.get("category_name")
        parent_category = data.get("parent_category")
        description = data.get("description")
        is_active = data.get("is_active", 1)
        display_order = data.get("display_order", 0)

        # -----------------------------------------
        # Validation
        # -----------------------------------------
        if not category_name:
            return {
                "success": False,
                "message": "Category name is required"
            }

        # -----------------------------------------
        # Check Duplicate Category
        # -----------------------------------------
        if frappe.db.exists(
            "Channel Category",
            {
                "category_name": category_name
            }
        ):
            return {
                "success": False,
                "message": "Category already exists"
            }

        # -----------------------------------------
        # Create Category
        # -----------------------------------------
        doc = frappe.new_doc("Channel Category")

        doc.category_name = category_name
        doc.description = description
        
        doc.is_active = is_active
        doc.display_order = display_order

        if parent_category:
            doc.parent_category = parent_category

        doc.insert(ignore_permissions=True)

        frappe.db.commit()

        # -----------------------------------------
        # Response
        # -----------------------------------------
        return {
            "success": True,
            "message": "Category created successfully",
            "data": {
                "name": doc.name,
                "category_name": doc.category_name,
                "parent_category": doc.parent_category,
                "description": doc.description,
                "is_active": doc.is_active,
                "display_order": doc.display_order,
                "creation": doc.creation
            }
        }

    except Exception as e:

        frappe.log_error(
            frappe.get_traceback(),
            "Create Category API Error"
        )

        return {
            "success": False,
            "message": str(e)
        }