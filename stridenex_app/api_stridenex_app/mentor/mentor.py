import json

import frappe
from stridenex_app.api_stridenex_app.app_utils import (
    gen_response,
    exception_handel
)


import frappe
from stridenex_app.api_stridenex_app.app_utils import (
    gen_response,
    exception_handel
)


@frappe.whitelist(allow_guest=True)
def create_mentor():
    try:
        data = frappe.request.get_json()

        email = data.get("email_id")
        mobile = data.get("mobile_no")

        if not email:
            frappe.throw("Email is required")

        if not mobile:
            frappe.throw("Mobile number is required")

        existing_mentor = frappe.db.exists(
            "Mentor",
            {"email_id": email}
        )

        if existing_mentor:
            mentor = frappe.get_doc("Mentor", existing_mentor)

        else:
            mentor = frappe.get_doc({
                "doctype": "Mentor",
                "first_name": data.get("first_name"),
                "last_name": data.get("last_name"),
                "email_id": email,
                "mobile_no": mobile
            })

            mentor.insert(ignore_permissions=True)

        create_mentor_user(mentor)

        if frappe.db.exists("User", email):
            frappe.db.set_value(
                "User",
                email,
                "is_onboarded",
                1
            )

        frappe.db.commit()

        return gen_response(
            status=200,
            message="Mentor onboarding started successfully",
            data={
                "mentor": mentor.name,
                "onboarding_step": 1
            }
        )

    except Exception as e:
        return exception_handel(e)



@frappe.whitelist(allow_guest=True)
def update_mentor(email_id):

    try:
        data = frappe.request.get_json()

        if not data:
            return gen_response(
                400,
                "Invalid request data"
            )

        mentor_name = frappe.db.get_value(
            "Mentor",
            {"email_id": email_id},
            "name"
        )

        if not mentor_name:
            return gen_response(
                404,
                "Mentor not found"
            )

        mentor = frappe.get_doc(
            "Mentor",
            mentor_name
        )
        # return mentor

        mentor.flags.ignore_permissions = True

        mentor_skills = data.pop("skills", [])
        domains = data.pop("domains", [])
        mentor_platform_urls = data.pop(
            "mentor_platform_urls",
            []
        )

        ignore_fields = [
            "name",
            "doctype",
            "owner",
            "creation",
            "modified",
            "email_id",
            "mobile_no",
            "approved_status",
            "total_sessions",
            "total_hours",
            "total_earnings",
            "avg_rating"
        ]

        
        # Mentor Skills
        mentor.set("mentor_skills", [])

        for row in mentor_skills:

            mentor.append("mentor_skills", {
                "skill": row.get("skill"),
                "level": row.get("level")
            })

        # Domain
        mentor.set("domain", [])

        for row in domains:

            mentor.append("domain", {
                "domain": row.get("domain")
            })

        # Platform URLs
        for key, value in data.items():

            if key not in ignore_fields:
                mentor.set(key, value)

        mentor.set("mentor_platform_urls", [])

        if isinstance(mentor_platform_urls, list):

            for row in mentor_platform_urls:

                if isinstance(row, dict):

                    mentor.append(
                        "mentor_platform_urls",
                        {
                            "platform": row.get("platform"),
                            "url": row.get("url")
                        }
                    )

        mentor.save(ignore_permissions=True)


        # if mentor.email_id:

        #     frappe.db.set_value(
        #         "User",
        #         mentor.email_id,
        #         "is_onboarded",
        #         onboarding_status
        #     )

        frappe.db.commit()

        return gen_response(
            status=200,
            message="Mentor updated successfully",
            data={
                "mentor": mentor.name,
            }
        )

    except Exception as e:

        frappe.log_error(
            frappe.get_traceback(),
            "UPDATE MENTOR ERROR"
        )

        return exception_handel(e)


@frappe.whitelist()
def create_mentor_user(mentor=None):

    if not mentor:
        frappe.throw("Mentor data is required")

    if isinstance(mentor, str):
        mentor = frappe.parse_json(mentor)

    email = mentor.get("email_id")
    mobile = mentor.get("mobile_no")

    if not email:
        frappe.throw("Email is required")

    if frappe.db.exists("User", email):

        user = frappe.get_doc("User", email)

        existing_roles = [r.role for r in user.roles]

        if "Mentor" not in existing_roles:
            user.append("roles", {"role": "Mentor"})

        if "Instructor" not in existing_roles:
            user.append("roles", {"role": "Instructor"})

        user.save(ignore_permissions=True)

    else:

        user = frappe.get_doc({
            "doctype": "User",
            "email": email,
            "first_name": mentor.get("first_name"),
            "last_name": mentor.get("last_name"),
            "mobile_no": mobile,
            "enabled": 1,
            "send_welcome_email": 0,
            "roles": [
                {
                    "role": "Mentor"
                },
                {
                    "role": "Instructor"
                }
            ]
        })

        user.insert(ignore_permissions=True)

    mentor_doc = frappe.get_doc(
        "Mentor",
        {"email_id": email}
    )

    mentor_doc.user = email

    mentor_doc.save(ignore_permissions=True)

    return {
        "status": "success",
        "mentor": mentor_doc.name,
        "user": email
    }


@frappe.whitelist(allow_guest=True)
def get_mentor_by_email(email_id):

    try:

        if not email_id:

            return {
                "status": 400,
                "message": "Email is required"
            }


        mentor_name = frappe.db.get_value(
            "Mentor",
            {"email_id": email_id},
            "name"
        )

        if not mentor_name:

            return {
                "status": 404,
                "message": "No mentor found"
            }


        doc = frappe.get_doc(
            "Mentor",
            mentor_name
        )


        data = {

            "name": doc.name,

            "first_name": doc.first_name,
            "last_name": doc.last_name,

            "email_id": doc.email_id,
            "mobile_no": doc.mobile_no,

            "type": doc.type,

            "country": doc.country,
            "state": doc.state,
            "district": doc.district,
            "tahsil": doc.tahsil,
            "city": doc.city,

            "travelling_possible": doc.travelling_possible,

            "profile_description": doc.profile_description,

            "bank_name": doc.bank_name,
            "account_number": doc.account_number,
            "ifsc_code": doc.ifsc_code,

            "approved_status": doc.approved_status,
            "is_active": doc.is_active,

            "total_sessions": doc.total_sessions,
            "total_hours": doc.total_hours,
            "total_earnings": doc.total_earnings,
            "avg_rating": doc.avg_rating,
            "role":doc.role,
            "experience":doc.experience,

            # "terms_accepted": doc.terms_accepted,


            # "skills": [

            #     {
            #         "name": row.name,
            #         "skill": row.skill,
            #         "level": row.level
            #     }

            #     for row in doc.skills
            # ],


            # "domains": [

            #     {
            #         "name": row.name,
            #         "domain": row.domain
            #     }

            #     for row in doc.domains
            # ],

            "mentor_platform_urls": [

                {
                    "name": row.name,
                    "platform": row.platform,
                    "url": row.url
                }

                for row in doc.mentor_platform_urls
            ],
            "mentor_verification": [

                {
                    "verification": row.verification,
                    "status": row.status,
                   
                }

                for row in doc.mentor_verification
            ]
        }

        return {
            "status": 200,
            "message": "Mentor fetched successfully",
            "data": data
        }

    except Exception as e:

        frappe.log_error(
            frappe.get_traceback(),
            "GET MENTOR ERROR"
        )

        return {
            "status": 500,
            "message": str(e)
        }




# @frappe.whitelist(allow_guest=True)
# def create_mentor():
#     try:
#         data = frappe.request.get_json()
#         email = data.get("email")

#         mentor = frappe.get_doc({
#             "doctype": "Mentor",
#             **data
#         })

#         mentor.insert(ignore_permissions=True)

#         create_mentor_user(mentor)
#         if email and frappe.db.exists("User", email):
#             frappe.db.set_value("User", email, "is_onboarded", 1)
#             frappe.db.commit()

#         return gen_response(
#             status=200,
#             message="Mentor registered successfully",
#             data={"name": mentor.first_name}
#         )

#     except Exception as e:
#         return exception_handel(e)


# @frappe.whitelist()
# def create_mentor_user(mentor=None):
#     if not mentor:
#         frappe.throw("Mentor data is required")

#     if isinstance(mentor, str):
#         mentor = frappe.parse_json(mentor)

#     email = mentor.get("email_id")
#     mobile = mentor.get("mobile_no")

#     if not email:
#         frappe.throw("Email is required")

#     if not mobile:
#         frappe.throw("Mobile number is required")

#     if frappe.db.exists("Mentor", email):
#         mentor_doc = frappe.get_doc("Mentor", email)
#     else:
#         mentor_doc = frappe.get_doc({
#             "doctype": "Mentor",
#             "email_id": email,
#             "first_name": mentor.get("first_name"),
#             "last_name": mentor.get("last_name"),
#             "mobile_no": mobile
#         })
#         mentor_doc.insert(ignore_permissions=True)

#     if frappe.db.exists("User", email):
#         user = frappe.get_doc("User", email)
#         roles = [r.role for r in user.roles]

#         if "Mentor" not in roles:
#             user.append("roles", {"role": "Mentor"})

#         if "Instructor" not in roles:
#             user.append("roles", {"role": "Instructor"})

#         user.save(ignore_permissions=True)

#     else:
#         user = frappe.get_doc({
#             "doctype": "User",
#             "email": email,
#             "first_name": mentor.get("first_name"),
#             "last_name": mentor.get("last_name"),
#             "enabled": 1,
#             "send_welcome_email": 0,
#             "roles": [
#                 {"role": "Mentor"},
#                 {"role": "Instructor"}
#             ]
#         })
#         user.insert(ignore_permissions=True)

#     mentor_doc.user = email
#     mentor_doc.save(ignore_permissions=True)

#     return {
#         "status": "success",
#         "mentor": mentor_doc.name,
#         "user": email
#     }
