"""
Discourse DiscourseConnect (SSO) provider endpoint for Frappe.

SETUP
-----
1. Drop this file into any installed Frappe app, e.g.:
       apps/your_app/your_app/discourse_sso.py

2. Add the shared secret to site_config.json (don't hardcode it in code):
       bench --site yoursite.erp set-config discourse_sso_secret "a-long-random-string"

3. In Discourse: Admin > Settings > Login, set:
       enable_discourse_connect  = true
       discourse_connect_url     = https://yoursite.erp/api/method/your_app.discourse_sso.sso
       discourse_connect_secret  = the same string you put in site_config.json

4. Test it: log out of Discourse, click "Log In". You'll land on this
   endpoint, get bounced to Frappe's login page if you're not signed in
   yet, then land back on Discourse already logged in as that user.
"""

import base64
import hashlib
import hmac
from urllib.parse import parse_qs, quote, urlencode

import frappe


def _secret():
    secret = frappe.conf.get("discourse_sso_secret")
    if not secret:
        frappe.throw("discourse_sso_secret is not set in site_config.json")
    return secret


def _sign(payload_b64: str) -> str:
    return hmac.new(
        _secret().encode("utf-8"),
        payload_b64.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


@frappe.whitelist(allow_guest=True, methods=["GET"])
def sso():
    sso_payload = frappe.form_dict.get("sso")
    sig = frappe.form_dict.get("sig")

    if not sso_payload or not sig:
        frappe.throw("Missing sso/sig parameters")

    # 1. Verify this request really came from your Discourse instance
    if not hmac.compare_digest(_sign(sso_payload), sig):
        frappe.throw("Invalid SSO signature", frappe.PermissionError)

    # 2. Make sure someone is actually logged into Frappe first.
    #    If not, bounce to login and come straight back here afterwards.
    if frappe.session.user == "Guest":
        here = frappe.utils.get_url(frappe.request.full_path)
        frappe.local.response["type"] = "redirect"
        frappe.local.response["location"] = f"/login?redirect-to={quote(here)}"
        return

    # 3. Recover nonce + return_sso_url from Discourse's incoming payload
    decoded = base64.b64decode(sso_payload).decode("utf-8")
    parsed = parse_qs(decoded)
    nonce = parsed["nonce"][0]
    return_sso_url = parsed["return_sso_url"][0]

    # 4. Build the response payload from the logged-in Frappe user
    user = frappe.get_doc("User", frappe.session.user)

    out = {
        "nonce": nonce,
        "email": user.email,
        "external_id": user.name,  # Frappe's stable, unique user id
        "username": user.username or user.email.split("@")[0],
        "name": user.full_name,
    }
    if user.user_image:
        out["avatar_url"] = frappe.utils.get_url(user.user_image)

    out_b64 = base64.b64encode(urlencode(out).encode("utf-8")).decode("utf-8")
    out_sig = _sign(out_b64)

    frappe.local.response["type"] = "redirect"
    frappe.local.response["location"] = (
        f"{return_sso_url}?{urlencode({'sso': out_b64, 'sig': out_sig})}"
    )