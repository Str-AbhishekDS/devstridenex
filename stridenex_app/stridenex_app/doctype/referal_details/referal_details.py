# Copyright (c) 2026, QTPL and contributors
# For license information, please see license.txt

# import frappe
from frappe.model.document import Document
import frappe 
from frappe.auth import LoginManager
from frappe.utils.password import update_password
import random
import requests
from urllib.parse import quote
from frappe.utils import now_datetime, add_to_date
from stridenex_app.api_stridenex_app.app_utils import (
    gen_response, 
    generate_key, 
    exception_handel
    )

import string
from frappe.utils.pdf import get_pdf
import random
from urllib.parse import quote

import frappe
from frappe import _
from frappe.utils import nowdate,formatdate
from frappe.utils.pdf import get_pdf



class ReferalDetails(Document):
	pass



@frappe.whitelist(allow_guest=True)
def get_referral_module_count():

    try:
        referral_code = frappe.form_dict.get("referral_code")

        if not referral_code:
            return gen_response(
                400,
                "Referral code is required",
                {
                    "success": False
                }
            )

        # Check whether referral code exists
        referrer = frappe.db.get_value(
            "User",
            {"referal_code": referral_code},
            ["name", "full_name"],
            as_dict=True
        )

        if not referrer:
            return gen_response(
                404,
                "Invalid referral code",
                {
                    "success": False
                }
            )

        # Count module-wise referrals
        module_counts = {
            "Student": 0,
            "College": 0,
            "Mentor": 0,
            "Industry": 0
        }

        rows = frappe.db.sql(
            """
            SELECT
                module,
                COUNT(name) AS count
            FROM `tabReferal Details`
            WHERE referral_code = %s
            GROUP BY module
            """,
            (referral_code,),
            as_dict=True
        )

        for row in rows:
            if row.module in module_counts:
                module_counts[row.module] = int(row.count)

        total = sum(module_counts.values())

        return gen_response(
            200,
            "Referral module count fetched successfully",
            {
                "success": True,
                "referral_code": referral_code,
                "referrer": referrer.name,
                "referrer_name": referrer.full_name,
                "counts": module_counts,
                "total": total
            }
        )

    except Exception:
        frappe.log_error(
            frappe.get_traceback(),
            "Referral Module Count Error"
        )

        return gen_response(
            500,
            "Something went wrong",
            {
                "success": False
            }
        )