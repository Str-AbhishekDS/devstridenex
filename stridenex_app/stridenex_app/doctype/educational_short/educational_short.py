# Copyright (c) 2026, QTPL and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class EducationalShort(Document):
	pass


@frappe.whitelist(allow_guest=True)
def get_gap_recommendations(user=None, limit=5):
    user = user or frappe.session.user

    gaps = frappe.get_list("Learning Gap",
        filters={"user": user},
        fields=["topic", "weakness_score"],
        order_by="weakness_score desc", limit_page_length=3)

    if not gaps:
        return {"curated_for": [], "recommendations": []}

    topics = [g["topic"] for g in gaps]

    # naive text match; swap for embedding cosine-similarity for better quality
    shorts = frappe.get_list("Educational Short",
        filters={"status": "Published"},
        fields=["name", "title", "duration_seconds", "subject"])

    scored = []
    for s in shorts:
        overlap = sum(1 for t in topics if t.lower() in s["title"].lower())
        if overlap:
            match_pct = min(99, 70 + overlap * 15)  # simple heuristic
            scored.append({
                "name": s["name"],
                "title": s["title"],
                "duration_display": f"{s['duration_seconds']}s",
                "match_pct": match_pct
            })

    scored.sort(key=lambda x: x["match_pct"], reverse=True)
    return {
        "curated_for": topics,
        "recommendations": scored[:limit]
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



def format_views(n):
    if n >= 1_000_000: return f"{n/1_000_000:.1f}M"
    if n >= 1_000: return f"{int(n/1000)}K"
    return str(n)

@frappe.whitelist()
def get_saved_shorts(user=None, limit=10):
    user = user or frappe.session.user

    return frappe.get_list(
        "Saved Short",
        filters={"user": user},
        fields=["*"],
        limit_page_length=int(limit)
    )
@frappe.whitelist()
def get_shorts_feed(user=None,limit=10,skill=None):
    filters = {"status": "Published"}
    if skill:
        filters["skill"] = skill

    shorts = frappe.get_list(
        "Educational Short",
        filters=filters,
        fields=["name", "title", "thumbnail", "cover_gradient",
                "duration_seconds", "view_count", "subject","video","skill"],
        order_by="published_on desc",
        limit_page_length=limit
    )
    saved_shorts = frappe.get_all(
        "Saved Short",
        filters={"user": user},
        pluck="short"
    )
    saved_shorts = set(saved_shorts)
    for s in shorts:
        s["views_display"] = format_views(s["view_count"] or 0)
        s["duration_display"] = f"{s['duration_seconds']} sec"
        s["is_saved"] = s["name"] in saved_shorts
    return shorts