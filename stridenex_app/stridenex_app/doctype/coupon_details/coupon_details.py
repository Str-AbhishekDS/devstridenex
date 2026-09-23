# Copyright (c) 2026, QTPL and contributors
# For license information, please see license.txt

# import frappe
from frappe.model.document import Document


class CouponDetails(Document):
	pass


# Copyright (c) 2026, QTPL and contributors
# For license information, please see license.txt

import frappe



@frappe.whitelist(allow_guest=True)
def get_coupon(coupon_code=None):
    

    if not coupon_code:
        frappe.throw("Coupon code is required")
  

    # Get coupon
    coupon_name = frappe.db.get_value(
        "Coupon Details",
        {"coupon_code": coupon_code},
        "name"
    )

    if not coupon_name:
        frappe.throw("Coupon not found")

    coupon = frappe.get_doc("Coupon", coupon_name)

    # Check whether coupon is public
    if not coupon.is_public:
        frappe.throw("This coupon is not public")

    # Check status
    if coupon.status in ["Disabled", "Expired"]:
        frappe.throw("This coupon is no longer available")

    # Get partner name
    partner_name = None

    if coupon.partner:
        partner_name = frappe.db.get_value(
            "User",
            coupon.partner,
            "full_name"
        )

    # Convert document to dict
    coupon_data = coupon.as_dict()

    # Add partner name for template
    coupon_data["partner_name"] = partner_name or coupon.partner

    # Render HTML
    html = frappe.render_template(
        "stridenex_app/templates/coupon/coupon_card.html",
        {
            "coupon": coupon_data
        }
    )

    return {
        "success": True,
        "coupon": coupon_data,
        "html": html
    }

