# Copyright (c) 2026, QTPL and contributors
# For license information, please see license.txt

# import frappe
from frappe.model.document import Document
from stridenex_app.api_stridenex_app.app_utils import (
    gen_response,
    exception_handel
)



class StridenexPartner(Document):
	pass

import frappe
from frappe import _
import json
import string
import random


@frappe.whitelist(allow_guest=True)
def create_partner():
    try:
        # ---------------------------------------------------------
        # Get JSON request data
        # ---------------------------------------------------------
        data = frappe.local.form_dict
       

        # If request body contains JSON
        if frappe.request.data:
            try:
                body = json.loads(frappe.request.data)
                if isinstance(body, dict):
                    data.update(body)
            except Exception:
                pass

        first_name = (data.get("first_name") or "").strip()
        last_name = (data.get("last_name") or "").strip()
        email = (data.get("email") or "").strip().lower()
        phone_number = (data.get("phone_number") or "").strip()
        organisation = (data.get("organisation") or "").strip()
        job_title = (data.get("job_title") or "").strip()
        company_size = data.get("company_size")
        state = (data.get("state") or "").strip()
        password = data.get("password")
        username = data.get("username")

        # ---------------------------------------------------------
        # Validation
        # ---------------------------------------------------------
        if not first_name:
            frappe.throw(_("First Name is required"))

        if not email:
            frappe.throw(_("Email is required"))

        if not password:
            frappe.throw(_("Password is required"))

        # ---------------------------------------------------------
        # Check existing User by email
        # ---------------------------------------------------------
        existing_user = frappe.db.exists("User", email)

        if existing_user:
            frappe.throw(
                _("A User already exists with email {0}").format(email)
            )


        # ---------------------------------------------------------
        # Generate unique username
        # ---------------------------------------------------------
        base_username = email.split("@")[0]

        username = base_username

        counter = 1

        while frappe.db.exists("User", {"username": username}):
            username = f"{base_username}_{counter}"
            counter += 1


        # ---------------------------------------------------------
        # Check Partner role
        # ---------------------------------------------------------
        if not frappe.db.exists("Role", "Partner"):
            frappe.throw(
                _("Partner role does not exist. Please create the Partner role first.")
            )
 
        referral_code = generate_referral_code()
        # ---------------------------------------------------------
        # Create User
        # ---------------------------------------------------------
        user = frappe.new_doc("User")

        user.email = email
        user.first_name = first_name
        user.last_name = last_name
        user.username = username
        user.mobile_no = phone_number
        user.enabled = 1
        user.user_type = "Website User"
        user.send_welcome_email = 0
        user.referal_code=referral_code

        # Password
        user.new_password = password

        # Partner role
        user.append("roles", {
            "role": "Partner"
        })

        user.insert(ignore_permissions=True)
        

        # ---------------------------------------------------------
        # Create Partner
        # ---------------------------------------------------------
        partner = frappe.new_doc("Stridenex Partner")

        partner.first_name = first_name
        partner.last_name = last_name
        partner.email = email
        partner.phone_number = phone_number
        partner.organisation = organisation
        partner.job_title = job_title
        partner.company_size = company_size
        partner.state = state

        partner.insert(ignore_permissions=True)

        # ---------------------------------------------------------
        # Commit
        # ---------------------------------------------------------
        frappe.db.commit()

        return {
            "status": "success",
            "message": "Partner created successfully",
            "data": {
                "user": {
                    "name": user.name,
                    "email": user.email,
                    "first_name": user.first_name,
                    "last_name": user.last_name,
                    "mobile_no": user.mobile_no
                },
                "partner": {
                    "name": partner.name,
                    "first_name": partner.first_name,
                    "last_name": partner.last_name,
                    "email": partner.email,
                    "phone_number": partner.phone_number,
                    "organisation": partner.organisation,
                    "job_title": partner.job_title,
                    "company_size": partner.company_size,
                    "state": partner.state
                }
            }
        }

    except Exception as e:
        frappe.db.rollback()

        frappe.log_error(
            title="Create Partner API Error",
            message=frappe.get_traceback()
        )

        frappe.throw(str(e))

def generate_referral_code(length=8):
    """Generate a unique 8-character alphanumeric referral code."""
    chars = string.ascii_uppercase + string.digits

    while True:
        code = "".join(random.choices(chars, k=length))

        if not frappe.db.exists("User", {"referral_code": code}):
            return code

@frappe.whitelist(allow_guest=True)
def get_partner(email=None):
    try:
        # ---------------------------------------------------------
        # Get email
        # ---------------------------------------------------------
        email = email or frappe.form_dict.get("email")

        if not email:
            frappe.throw(_("Email is required"))

        email = email.strip().lower()

        # ---------------------------------------------------------
        # Get User
        # ---------------------------------------------------------
        user = frappe.db.get_value(
            "User",
            email,
            [
                "name",
                "email",
                "first_name",
                "last_name",
                "mobile_no",
                "enabled",
                "user_type",
                "referal_code"
            ],
            as_dict=True
        )

        if not user:
            frappe.throw(
                _("User not found for {0}").format(email)
            )

        # ---------------------------------------------------------
        # Get Partner
        # ---------------------------------------------------------
        partner = frappe.db.get_value(
            "Stridenex Partner",
            {
                "email": email
            },
            [
                "name",
                "first_name",
                "last_name",
                "email",
                "phone_number",
                "organisation",
                "job_title",
                "company_size",
                "state",
                "creation",
                "modified"
            ],
            as_dict=True
        )

        if not partner:
            frappe.throw(
                _("Partner profile not found for {0}").format(email)
            )

        # ---------------------------------------------------------
        # Return combined information
        # ---------------------------------------------------------
        return {
            "status": "success",
            "data": {
                "user": user,
                "partner": partner
            }
        }

    except Exception as e:
        frappe.log_error(
            title="Get Partner API Error",
            message=frappe.get_traceback()
        )

        frappe.throw(str(e))


@frappe.whitelist(allow_guest=True)
def edit_stridenex_partner():
    try:
        if frappe.request.method != "PUT":
            return gen_response(
                400,
                "Only PUT method is allowed",
                {"success": False}
            )

        data = frappe.request.get_json()

        partner_name = data.get("name")

        if not partner_name:
            return gen_response(
                400,
                "Partner name is required",
                {"success": False}
            )

        # Check if partner exists
        if not frappe.db.exists("Stridenex Partner", partner_name):
            return gen_response(
                404,
                "Stridenex Partner not found",
                {"success": False}
            )

        partner = frappe.get_doc("Stridenex Partner", partner_name)

        # Update only fields supplied in request
        fields = [
            "first_name",
            "last_name",
            "email",
            "phone_number",
            "organisation",
            "job_title",
            "company_size",
            "state"
        ]

        for field in fields:
            if field in data:
                partner.set(field, data.get(field))

        partner.save(ignore_permissions=True)

        frappe.db.commit()

        return gen_response(
            200,
            "Partner updated successfully",
            {
                "success": True,
                "data": {
                    "name": partner.name,
                    "first_name": partner.first_name,
                    "last_name": partner.last_name,
                    "email": partner.email,
                    "phone_number": partner.phone_number,
                    "organisation": partner.organisation,
                    "job_title": partner.job_title,
                    "company_size": partner.company_size,
                    "state": partner.state
                }
            }
        )

    except Exception as e:
        frappe.log_error(
            frappe.get_traceback(),
            "Edit Stridenex Partner API Error"
        )

        return gen_response(
            500,
            str(e),
            {"success": False}
        )

import frappe

import frappe
import os
import re


REFERENCE_TEMPLATES = {

    "student": {
        "title": "STUDENT",
        "background": "#EFF6FF",
        "circle": "#DBEAFE",
        "accent": "#2563EB",
        "text": "#1E3A8A",
        "border": "#BFDBFE",

        "icon": """
        <!-- BOOKS / EDUCATION -->
        <rect x="62" y="95" width="55" height="10"
              rx="3" fill="#2563EB"/>

        <rect x="58" y="108" width="63" height="10"
              rx="3" fill="#3B82F6"/>

        <rect x="62" y="121" width="55" height="10"
              rx="3" fill="#60A5FA"/>

        <rect x="70" y="138" width="40" height="5"
              rx="2" fill="#1D4ED8"/>

        <path d="M68 88 L95 75 L122 88 L95 101 Z"
              fill="#1D4ED8"/>

        <line x1="95" y1="101"
              x2="95" y2="108"
              stroke="#1D4ED8"
              stroke-width="3"/>
        """
    },

    "mentor": {
        "title": "MENTOR",
        "background": "#ECFDF5",
        "circle": "#D1FAE5",
        "accent": "#059669",
        "text": "#065F46",
        "border": "#A7F3D0",

        "icon": """
        <!-- MENTOR / GUIDE -->
        <circle cx="95" cy="94"
                r="17"
                fill="#059669"/>

        <path d="M67 137
                 C67 115 78 106 95 106
                 C112 106 123 115 123 137
                 Z"
              fill="#059669"/>

        <!-- GUIDE CONNECTION -->
        <circle cx="72" cy="91"
                r="8"
                fill="#34D399"/>

        <circle cx="118" cy="91"
                r="8"
                fill="#34D399"/>

        <line x1="79" y1="94"
              x2="86" y2="99"
              stroke="#059669"
              stroke-width="4"/>

        <line x1="111" y1="99"
              x2="118" y2="94"
              stroke="#059669"
              stroke-width="4"/>

        <!-- STAR -->
        <path d="M95 72
                 L98 79
                 L106 80
                 L100 85
                 L102 93
                 L95 89
                 L88 93
                 L90 85
                 L84 80
                 L92 79 Z"
              fill="#FBBF24"/>
        """
    },

    "college": {
        "title": "COLLEGE",
        "background": "#F5F3FF",
        "circle": "#EDE9FE",
        "accent": "#7C3AED",
        "text": "#5B21B6",
        "border": "#DDD6FE",

        "icon": """
        <!-- COLLEGE / GRADUATION -->
        <path d="M60 92
                 L95 75
                 L130 92
                 L95 109 Z"
              fill="#7C3AED"/>

        <path d="M75 101
                 L75 119
                 C75 130 115 130 115 119
                 L115 101
                 L95 111 Z"
              fill="#8B5CF6"/>

        <line x1="122" y1="95"
              x2="122" y2="123"
              stroke="#5B21B6"
              stroke-width="4"/>

        <circle cx="122"
                cy="127"
                r="4"
                fill="#F59E0B"/>
        """
    },

    "industry": {
        "title": "INDUSTRY",
        "background": "#FFF7ED",
        "circle": "#FFEDD5",
        "accent": "#EA580C",
        "text": "#9A3412",
        "border": "#FED7AA",

        "icon": """
        <!-- INDUSTRY / BUILDING -->
        <rect x="62" y="92"
              width="25" height="48"
              rx="2"
              fill="#EA580C"/>

        <rect x="89" y="78"
              width="28" height="62"
              rx="2"
              fill="#F97316"/>

        <rect x="119" y="98"
              width="15" height="42"
              rx="2"
              fill="#FB923C"/>

        <rect x="68" y="100"
              width="7" height="7"
              fill="#FFF7ED"/>

        <rect x="68" y="113"
              width="7" height="7"
              fill="#FFF7ED"/>

        <rect x="95" y="88"
              width="7" height="7"
              fill="#FFF7ED"/>

        <rect x="106" y="88"
              width="7" height="7"
              fill="#FFF7ED"/>

        <rect x="95" y="102"
              width="7" height="7"
              fill="#FFF7ED"/>

        <rect x="106" y="102"
              width="7" height="7"
              fill="#FFF7ED"/>

        <rect x="95" y="116"
              width="7" height="7"
              fill="#FFF7ED"/>

        <rect x="106" y="116"
              width="7" height="7"
              fill="#FFF7ED"/>
        """
    },

    "partner": {
        "title": "PARTNER",
        "background": "#FEF2F2",
        "circle": "#FEE2E2",
        "accent": "#DC2626",
        "text": "#991B1B",
        "border": "#FECACA",

        "icon": """
        <!-- PARTNER / HANDSHAKE -->
        <path d="M62 102
                 L78 89
                 L92 97
                 L105 86
                 L128 101
                 L116 114
                 L101 105
                 L90 115
                 L76 106
                 Z"
              fill="#DC2626"/>

        <path d="M82 111
                 L93 121
                 L103 111"
              fill="none"
              stroke="#991B1B"
              stroke-width="6"
              stroke-linecap="round"/>

        <circle cx="68"
                cy="102"
                r="7"
                fill="#F87171"/>

        <circle cx="123"
                cy="102"
                r="7"
                fill="#F87171"/>
        """
    }
}

logo_svg = f"""
<image
    href="{frappe.get_url()}/assets/stridenex_app/images/logo.png"
    x="235"
    y="15"
    width="120"
    height="45"
    preserveAspectRatio="xMidYMid meet"
/>
"""


@frappe.whitelist(allow_guest=True)
def get_reference_card(reference_code=None, module=None):

    try:

        if not reference_code:
            return {
                "status": 400,
                "message": "Reference code is required",
                "data": {}
            }

        if not module:
            return {
                "status": 400,
                "message": "Module is required",
                "data": {}
            }

        module = module.strip().lower()

        template = REFERENCE_TEMPLATES.get(module)

        if not template:
            return {
                "status": 400,
                "message": "Invalid module. Use student, mentor, college, industry or partner",
                "data": {}
            }

        # Safe filename
        safe_reference = re.sub(
            r"[^a-zA-Z0-9_-]",
            "",
            reference_code
        )

        filename = f"{module}_{safe_reference}.svg"

        # Public files directory
        files_dir = frappe.get_site_path(
            "public",
            "files",
            "reference_cards"
        )

        os.makedirs(files_dir, exist_ok=True)

        file_path = os.path.join(
            files_dir,
            filename
        )

        svg = f"""<svg width="600" height="240"
viewBox="0 0 600 240"
xmlns="http://www.w3.org/2000/svg">

    <!-- CARD BACKGROUND -->
    <rect
        x="5"
        y="5"
        width="590"
        height="230"
        rx="28"
        fill="{template['background']}"
        stroke="{template['border']}"
        stroke-width="2"
    />

    <!-- LEFT ACCENT -->
    <rect
        x="5"
        y="5"
        width="12"
        height="230"
        rx="6"
        fill="{template['accent']}"
    />

    <!-- STRIDENEX LOGO - TOP RIGHT -->
    <image
        href="{frappe.get_url()}/assets/stridenex_app/images/logo.png"
        x="455"
        y="20"
        width="115"
        height="45"
        preserveAspectRatio="xMidYMid meet"
    />

    <!-- ICON CIRCLE -->
    <circle
        cx="95"
        cy="120"
        r="58"
        fill="{template['circle']}"
    />

    <!-- ICON -->
    {template['icon']}

    <!-- MODULE -->
    <text
        x="175"
        y="82"
        font-family="Arial, Helvetica, sans-serif"
        font-size="20"
        font-weight="700"
        letter-spacing="2"
        fill="{template['text']}"
    >
        {template['title']}
    </text>

    <!-- SMALL LABEL -->
    <text
        x="175"
        y="118"
        font-family="Arial, Helvetica, sans-serif"
        font-size="12"
        font-weight="500"
        letter-spacing="1"
        fill="#64748B"
    >
        REFERENCE CODE
    </text>

    <!-- REFERENCE CODE -->
    <text
        x="175"
        y="153"
        font-family="Arial, Helvetica, sans-serif"
        font-size="24"
        font-weight="700"
        letter-spacing="1"
        fill="{template['accent']}"
    >
        {reference_code}
    </text>

    <!-- BOTTOM LINE -->
    <rect
        x="175"
        y="177"
        width="340"
        height="1"
        fill="{template['border']}"
    />

    <!-- FOOTER -->
    <text
        x="175"
        y="202"
        font-family="Arial, Helvetica, sans-serif"
        font-size="11"
        fill="#94A3B8"
    >
        StrideNEX • Digital Reference Card
    </text>

</svg>"""
        # Save actual SVG file
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(svg)

        # Public URL
        image_url = (
            frappe.utils.get_url()
            + f"/files/reference_cards/{filename}"
        )

        return {
            "status": 200,
            "message": "Reference card generated successfully",
            "data": {
                "module": module,
                "reference_code": reference_code,
                "image_url": image_url
            }
        }

    except Exception as e:

        frappe.log_error(
            frappe.get_traceback(),
            "Reference Card API Error"
        )

        return {
            "status": 500,
            "message": str(e),
            "data": {}
        }