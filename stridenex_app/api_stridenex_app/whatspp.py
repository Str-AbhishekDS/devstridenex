import frappe
import requests
import secrets
from datetime import datetime, timedelta


@frappe.whitelist(allow_guest=True)
def send_verification_otp(mobile_no):

    if not mobile_no:
        return {
            "status": 400,
            "message": "Mobile number is required",
            "data": {}
        }

    try:

        # Remove spaces, +, -, etc.
        mobile_no = (
            str(mobile_no)
            .replace("+", "")
            .replace(" ", "")
            .replace("-", "")
            .replace("(", "")
            .replace(")", "")
        )

        # Basic validation
        if not mobile_no.isdigit():
            return {
                "status": 400,
                "message": "Invalid mobile number",
                "data": {}
            }

        # Generate 6 digit OTP
        otp = str(secrets.randbelow(900000) + 100000)

        # OTP expiry
        expiry_time = datetime.now() + timedelta(minutes=10)

        # Delete previous OTPs for this mobile
        frappe.db.delete(
            "Validate Mobile OTP",
            {
                "mobile_no": mobile_no
            }
        )

        # Save OTP
        otp_doc = frappe.get_doc({
            "doctype": "Validate Mobile OTP",
            "mobile_no": mobile_no,
            "otp": otp,
            "expiry_time": expiry_time
        })

        otp_doc.insert(ignore_permissions=True)

        # WhatsApp credentials
        phone_number_id = frappe.conf.get("whatsapp_phone_number_id")
        access_token = frappe.conf.get("whatsapp_access_token")

        if not phone_number_id:
            frappe.throw("WhatsApp Phone Number ID is not configured")

        if not access_token:
            frappe.throw("WhatsApp access token is not configured")

        # Meta API
        url = (
            f"https://graph.facebook.com/v25.0/"
            f"{phone_number_id}/messages"
        )

        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }

        payload = {
    "messaging_product": "whatsapp",
    "recipient_type": "individual",
    "to": mobile_no,
    "type": "template",
    "template": {
        "name": "verification",
        "language": {
            "code": "en_US"
        },
        "components": [
            {
                "type": "body",
                "parameters": [
                    {
                        "type": "text",
                        "text": otp
                    }
                ]
            },
            {
                "type": "button",
                "sub_type": "url",
                "index": "0",
                "parameters": [
                    {
                        "type": "text",
                        "text": otp
                    }
                ]
            }
        ]
    }
}

        response = requests.post(
            url,
            json=payload,
            headers=headers,
            timeout=30
        )

        result = response.json()

        if response.status_code >= 400:

            frappe.log_error(
                title="WhatsApp OTP Failed",
                message=frappe.as_json({
                    "request": payload,
                    "response": result
                })
            )

            # Remove OTP if WhatsApp failed
            frappe.delete_doc(
                "Validate Mobile OTP",
                otp_doc.name,
                ignore_permissions=True
            )

            return {
                "status": response.status_code,
                "message": "Failed to send WhatsApp OTP",
                "data": result
            }

        return {
            "status": 200,
            "message": "OTP sent successfully",
            "data": {
                "mobile_no": mobile_no,
                "expires_in": 600
            }
        }

    except Exception as e:

        frappe.log_error(
            title="WhatsApp OTP Exception",
            message=frappe.get_traceback()
        )

        return {
            "status": 500,
            "message": str(e),
            "data": {}
        }


@frappe.whitelist(allow_guest=True)
def verify_verification_otp(mobile_no, otp):

    if not mobile_no:
        return {
            "status": 400,
            "message": "Mobile number is required",
            "data": {}
        }

    if not otp:
        return {
            "status": 400,
            "message": "OTP is required",
            "data": {}
        }

    mobile_no = (
        str(mobile_no)
        .replace("+", "")
        .replace(" ", "")
        .replace("-", "")
        .replace("(", "")
        .replace(")", "")
    )

    record = frappe.db.get_value(
        "Validate Mobile OTP",
        {
            "mobile_no": mobile_no
        },
        [
            "name",
            "otp",
            "expiry_time"
        ],
        as_dict=True
    )

    if not record:
        return {
            "status": 404,
            "message": "OTP not found or already used",
            "data": {}
        }

    # Check expiry
    if datetime.now() > record.expiry_time:

        frappe.delete_doc(
            "Validate Mobile OTP",
            record.name,
            ignore_permissions=True
        )

        return {
            "status": 400,
            "message": "OTP has expired",
            "data": {}
        }

    # Check OTP
    if str(record.otp) != str(otp):

        return {
            "status": 400,
            "message": "Invalid OTP",
            "data": {}
        }

    # OTP successful
    frappe.delete_doc(
        "Validate Mobile OTP",
        record.name,
        ignore_permissions=True
    )

    return {
        "status": 200,
        "message": "OTP verified successfully",
        "data": {
            "mobile_no": mobile_no,
            "verified": True
        }
    }