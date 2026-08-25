# Copyright (c) 2026, QTPL and contributors
# For license information, please see license.txt

# import frappe
from frappe.model.document import Document


class PlaylistShorts(Document):
	pass


import frappe
from frappe import _

@frappe.whitelist(allow_guest=True)
def create_playlist():
    try:
        data = frappe.request.get_json()

        student = data.get("student")
        playlist_name = data.get("playlist_name")

        if not student:
            frappe.throw(_("Student is required."))

        if not playlist_name:
            frappe.throw(_("Playlist Name is required."))

        if not frappe.db.exists("Student", student):
            frappe.throw(_("Student not found."))

        if frappe.db.exists(
            "Student Short Playlist",
            {
                "student": student,
                "playlist_name": playlist_name
            }
        ):
            frappe.throw(_("Playlist already exists."))

        playlist = frappe.get_doc({
            "doctype": "Student Short Playlist",
            "student": student,
            "playlist_name": playlist_name
        })

        playlist.insert(ignore_permissions=True)
        frappe.db.commit()

        return {
            "status": True,
            "message": "Playlist created successfully.",
            "data": playlist
        }

    except Exception:
        frappe.db.rollback()
        frappe.log_error(frappe.get_traceback(), "Create Playlist")
        return {
            "status": False,
            "message": str(frappe.get_exception())
        }


@frappe.whitelist(allow_guest=True)
def save_short_to_playlist():
    try:
        data = frappe.request.get_json()

        playlist = data.get("playlist")
        shorts = data.get("shorts")

        if not playlist:
            frappe.throw(_("Playlist is required."))

        if not shorts:
            frappe.throw(_("Short is required."))

        if not frappe.db.exists("Student Short Playlist", playlist):
            frappe.throw(_("Playlist not found."))

        if not frappe.db.exists("Educational Short", shorts):
            frappe.throw(_("Educational Short not found."))

        if frappe.db.exists(
            "Playlist Shorts",
            {
                "playlist": playlist,
                "shorts": shorts
            }
        ):
            return {
                "status": True,
                "message": "Short already saved."
            }

        doc = frappe.get_doc({
            "doctype": "Playlist Shorts",
            "playlist": playlist,
            "shorts": shorts
        })

        doc.insert(ignore_permissions=True)
        frappe.db.commit()

        return {
            "status": True,
            "message": "Short saved successfully.",
            "data": doc
        }

    except Exception:
        frappe.db.rollback()
        frappe.log_error(frappe.get_traceback(), "Save Short")
        return {
            "status": False,
            "message": str(frappe.get_exception())
        }

@frappe.whitelist(allow_guest=True)
def get_student_playlists(student):
    try:

        if not student:
            frappe.throw(_("Student is required."))

        playlists = frappe.get_all(
            "Student Short Playlist",
            filters={
                "student": student
            },
            fields=[
                "name",
                "playlist_name"
            ],
            order_by="creation desc"
        )

        result = []

        for playlist in playlists:

            shorts = frappe.get_all(
                "Playlist Shorts",
                filters={
                    "playlist": playlist.name
                },
                fields=[
                    "shorts"
                ]
            )

            short_list = []

            for row in shorts:

                short_doc = frappe.db.get_value(
					"Educational Short",
					row.shorts,
					[
						"name",
						"title",
						"video",
						"thumbnail",
						"description",
						"skill",
						"view_count",
						"like_count"
					],
					as_dict=True
				)

                if short_doc:
                    short_list.append(short_doc)

            result.append({
                "playlist_id": playlist.name,
                "playlist_name": playlist.playlist_name,
                "total_shorts": len(short_list),
                "shorts": short_list
            })

        return {
            "status": True,
            "data": result
        }

    except Exception:
        frappe.log_error(frappe.get_traceback(), "Get Playlists")
        return {
            "status": False,
            "message": str(frappe.get_exception())
        }