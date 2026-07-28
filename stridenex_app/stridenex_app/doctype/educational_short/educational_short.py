# Copyright (c) 2026, QTPL and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class EducationalShort(Document):
	pass


@frappe.whitelist()
def get_recommendations(limit=5):
    user = frappe.session.user
    user == "Guest"
    limit = int(limit)

    # Skills the user has engaged with, via likes + saves
    liked_skills = frappe.get_all(
        "Liked Short",
        filters={"user": user},
        pluck="short"
    )
    saved_skills = frappe.get_all(
        "Saved Short",
        filters={"user": user},
        pluck="short"
    )
    engaged_short_names = list(set(liked_skills + saved_skills))

    interacted_skills = []
    if engaged_short_names:
        interacted_skills = frappe.get_all(
            "Educational Short",
            filters={"name": ["in", engaged_short_names]},
            pluck="skill"
        )
        interacted_skills = [s for s in interacted_skills if s]

    if interacted_skills:
        # weight skills by how often the user engaged with them
        from collections import Counter
        skill_weight = Counter(interacted_skills)
        top_skills = [s for s, _ in skill_weight.most_common(5)]

        shorts = frappe.get_list(
            "Educational Short",
            filters={
                "status": "Published",
                "skill": ["in", top_skills],
                "name": ["not in", engaged_short_names]  # don't recommend what they already liked/saved
            },
            fields=["name", "title", "duration_seconds", "subject", "skill", "view_count", "like_count"],
            limit_page_length=200
        )

        scored = []
        for s in shorts:
            weight = skill_weight.get(s["skill"], 0)
            match_pct = min(99, 70 + weight * 8)
            scored.append({
                "name": s["name"],
                "title": s["title"],
                "duration_display": f"{s['duration_seconds']} sec",
                "skill": s["skill"],
                "match_pct": match_pct
            })

        scored.sort(key=lambda x: (x["match_pct"], x["name"]), reverse=True)
        curated_for = top_skills
        recommendations = scored[:limit]

    else:
        # No history yet -> fall back to trending (most viewed)
        shorts = frappe.get_list(
            "Educational Short",
            filters={"status": "Published"},
            fields=["name", "title", "duration_seconds", "subject", "skill", "view_count"],
            order_by="view_count desc",
            limit_page_length=limit
        )
        recommendations = [{
            "name": s["name"],
            "title": s["title"],
            "duration_display": f"{s['duration_seconds']} sec",
            "skill": s["skill"],
            "match_pct": None
        } for s in shorts]
        curated_for = []

    return {
        "curated_for": curated_for,
        "recommendations": recommendations
    }


@frappe.whitelist()
def save_short(short_name, user=None):
    try:
        user = user or frappe.session.user

        if frappe.db.exists("Saved Short", {"user": user, "short": short_name}):
            return {"status": "already_saved"}

        doc = frappe.get_doc({
            "doctype": "Saved Short",
            "user": user,
            "short": short_name
        })

        doc.insert(ignore_permissions=True)
        frappe.db.commit()

        return {
            "status": "success",
            "name": doc.name
        }

    except Exception:
        frappe.log_error(frappe.get_traceback(), "Saved Short Error")
        raise



@frappe.whitelist()
def unsave_short(short_name, user=None):
    try:
        user = user or frappe.session.user

        frappe.db.delete(
            "Saved Short",
            {
                "user": user,
                "short": short_name
            }
        )
        frappe.db.commit()

        return {"status": "success"}

    except Exception:
        frappe.log_error(frappe.get_traceback(), "Unsave Short Error")
        raise

def format_views(n):
    if n >= 1_000_000: return f"{n/1_000_000:.1f}M"
    if n >= 1_000: return f"{int(n/1000)}K"
    return str(n)

@frappe.whitelist(allow_guest=True)
def get_saved_shorts(user=None, limit=10):
    user = user or frappe.session.user

    return frappe.get_list(
        "Saved Short",
        filters={"user": user},
        fields=["*"],
        limit_page_length=int(limit)
    )

@frappe.whitelist()
def get_shorts_feed(user=None, limit=10, skill=None):
    user = user or frappe.session.user
    filters = {"status": "Published"}
    if skill:
        filters["skill"] = skill

    shorts = frappe.get_list(
        "Educational Short",
        filters=filters,
        fields=["name", "title", "thumbnail",
               "view_count", "subject", "video", "skill","description","tags","like_count"],
        order_by="published_on desc",
        limit_page_length=limit
    )

    saved_shorts = set(
    str(x) for x in frappe.get_all(
        "Saved Short",
        filters={"user": user},
        pluck="short"
    )

)
    liked_shorts = {str(x) for x in frappe.get_all(
        "Liked Shorts", filters={"user": user}, pluck="short")}
    

    for s in shorts:
        s["views_display"] = format_views(s["view_count"] or 0)
        
        s["is_saved"] = str(s["name"]) in saved_shorts
        s["is_liked"] = str(s["name"]) in liked_shorts

    return shorts


@frappe.whitelist()
def toggle_like(short):
    user = frappe.session.user
    if user == "Guest":
        frappe.throw("Login required", frappe.PermissionError)

    existing = frappe.db.exists("Liked Shorts", {"user": user, "short": short})

    if existing:
        frappe.delete_doc("Liked Shorts", existing, ignore_permissions=True)
        frappe.db.set_value("Educational Short", short, "like_count",
                             frappe.db.count("Liked Shorts", {"short": short}))
        liked = False
    else:
        doc = frappe.get_doc({
            "doctype": "Liked Shorts",
            "user": user,
            "short": short
        })
        doc.insert(ignore_permissions=True)
        frappe.db.set_value("Educational Short", short, "like_count",
                             frappe.db.count("Liked Shorts", {"short": short}))
        liked = True

    frappe.db.commit()

    return {
        "liked": liked,
        "like_count": frappe.db.get_value("Educational Short", short, "like_count")
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
            "doctype": "Stridenex Tag",
            "title": title
        })

        doc.insert(ignore_permissions=True)
        frappe.db.commit()

        return {
            "status": "success",
            "message": "Tag created successfully",
            "name": doc.name
        }

    except Exception:
        frappe.log_error(frappe.get_traceback(), "Create Tag API")
        frappe.throw("Unable to create tag.")


@frappe.whitelist(allow_guest=True)
def get_tags():
    tags = frappe.get_all(
        "Stridenex Tag",
        fields=["name", "title"],
        order_by="creation desc"
    )
   

    return {
        "status": "success",
        "data": tags
    }