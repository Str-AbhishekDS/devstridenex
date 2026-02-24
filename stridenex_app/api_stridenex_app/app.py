import frappe 
from frappe.auth import LoginManager
import random
from frappe.utils import now_datetime, add_to_date
from stridenex_app.api_stridenex_app.app_utils import (
    gen_response, 
    generate_key, 
    exception_handel
    )


@frappe.whitelist(allow_guest=True)
def login(usr, pwd):
    try:
        login_manager = LoginManager()
        login_manager.authenticate(usr, pwd)
        login_manager.post_login()
        if frappe.response["message"] == "Logged In":    
            frappe.response["user"] = login_manager.user
            frappe.response["key_details"] = generate_key(login_manager.user)
            
        gen_response(200, frappe.response["message"])
    except frappe.AuthenticationError:
        gen_response(500, frappe.response["message"])
    except Exception as e:
        return exception_handel(e)


@frappe.whitelist()
def logout():
    try:
        frappe.local.login_manager.logout()
        return gen_response(200, "Logged out successfully.")
    except Exception as e:
        return exception_handel(e)


@frappe.whitelist(allow_guest=True)
def send_mobile_otp(mobile_no=None):
    if not mobile_no:
        return gen_response(400, "Mobile number is required")

    otp = str(random.randint(100000, 999999))
    
    expiry_time = add_to_date(now_datetime(), minutes=5)
    
    if frappe.db.exists("Validate Mobile OTP", mobile_no):
        doc = frappe.get_doc("Validate Mobile OTP", mobile_no)
        doc.otp = otp
        doc.expiry_time = expiry_time
        doc.save(ignore_permissions=True)

    else:
        doc = frappe.get_doc({
            "doctype": "Validate Mobile OTP",
            "mobile_no": mobile_no,
            "otp": otp,
            "expiry_time": expiry_time
        })
        doc.insert(ignore_permissions=True)
        frappe.db.commit()

    return gen_response(200, "OTP sent successfully", otp)


@frappe.whitelist(allow_guest=True)
def validate_mobile_otp(mobile_no=None, otp=None):

    if not mobile_no:
        return gen_response(400, "Mobile number is required")

    if not otp:
        return gen_response(400, "OTP is required")

    if not frappe.db.exists("Validate Mobile OTP", mobile_no):
        return gen_response(400, "OTP not generated for this mobile number")

    doc = frappe.get_doc("Validate Mobile OTP", mobile_no)

    if int(doc.otp) != int(otp):
        return gen_response(400, "Invalid OTP")

    doc.delete(ignore_permissions=True)

    return gen_response(200, "Mobile number verified successfully")


@frappe.whitelist(allow_guest=True)
def send_email_otp(email=None):
    try:
        if not email:
            frappe.throw(_("Email is required"))

        # Validate email format
        if not frappe.utils.validate_email_address(email, throw=False):
            frappe.throw(_("Invalid Email Address"))

        # Generate 6 digit OTP
        otp = str(random.randint(100000, 999999))
        expiry_time = add_to_date(now_datetime(), minutes=5)

        # Check if OTP already exists for this email
        existing_doc = frappe.db.get_value(
            "Validate Email OTP",
            {"email": email},
            "name"
        )

        if existing_doc:
            doc = frappe.get_doc("Validate Email OTP", existing_doc)
            doc.otp = otp
            doc.expiry_time = expiry_time
            doc.save(ignore_permissions=True)
        else:
            doc = frappe.get_doc({
                "doctype": "Validate Email OTP",
                "email": email,
                "otp": otp,
                "expiry_time": expiry_time
            })
            doc.insert(ignore_permissions=True)

        # Send OTP email
        frappe.sendmail(
            recipients=[email],
            subject="Your Login OTP",
            message=f"""
                <p>Hello,</p>
                <p>Your OTP for login is:</p>
                <h2>{otp}</h2>
                <p>This OTP is valid for 5 minutes.</p>
                <br>
                <p>Regards,<br>Your Company</p>
            """,
            now = True
        )
        frappe.db.commit()

        return {
            "status": "success",
            "message": "OTP sent successfully"
        }

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Send Email OTP Error")
        return {
            "status": "error",
            "message": str(e)
        }

@frappe.whitelist(allow_guest=True)
def validate_email_otp(email=None, otp=None):

    if not email:
        return gen_response(400, "Email is required")

    if not otp:
        return gen_response(400, "OTP is required")

    if not frappe.db.exists("Validate Email OTP", email):
        return gen_response(400, "OTP not generated for this email")

    doc = frappe.get_doc("Validate Email OTP", email)

    # Check expiry
    # if now_datetime() > doc.expiry_time:
    #     doc.delete(ignore_permissions=True)
    #     return gen_response(400, "OTP expired")

    if str(doc.otp) != str(otp):
        return gen_response(400, "Invalid OTP")

    # Success → delete OTP
    doc.delete(ignore_permissions=True)

    return gen_response(200, "Email verified successfully")