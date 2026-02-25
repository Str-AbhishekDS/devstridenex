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
def signup():
    if frappe.request.method != "POST":
        frappe.throw("Only POST allowed", frappe.ValidationError)
    try:
        data = frappe.request.get_json()
        first_name = data.get("first_name")
        last_name = data.get("last_name")
        email = data.get("email")
        password = data.get("password")

        if not all([first_name, last_name, email, password]):
            return gen_response(400, "All fields are required")

        existing_user = frappe.get_all(
            "User",
            filters={"name": email},
            fields=["name"]
        )

        if existing_user:
            return gen_response(400, "User already exists")

        user = frappe.get_doc({
            "doctype": "User",
            "email": email,
            "first_name": first_name,
            "last_name": last_name,
            "enabled": 1,
            "new_password": password,
            "user_type": "Website User"
        })
        user.insert(ignore_permissions=True)

        return gen_response(200, "User created successfully")

    except Exception as e:
        return gen_response(500, "Something went wrong", str(e))


def generate_key(user):
    user_details = frappe.get_doc("User", user)
    api_secret = api_key = ""
    if not user_details.api_key and not user_details.api_secret:
        api_secret = frappe.generate_hash(length=15)
        api_key = frappe.generate_hash(length=15)
        user_details.api_key = api_key
        user_details.api_secret = api_secret
        user_details.save(ignore_permissions=True)
    else:
        api_secret = user_details.get_password("api_secret")
        api_key = user_details.get("api_key")
    return {"api_secret": api_secret, "api_key": api_key}


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
    expiry_time = add_to_date(now_datetime(), minutes=10)
    
    if frappe.db.exists("Validate Mobile OTP", mobile_no):
        doc = frappe.get_doc("Validate Mobile OTP", mobile_no)
        doc.otp = otp
        doc.expiry_time = expiry_time
        doc.save(ignore_permissions=True)
        frappe.db.commit()

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
        return gen_response(400, "Mobile number is required", {"success": False})

    if not otp:
        return gen_response(400, "OTP is required", {"success": False})

    if not frappe.db.exists("Validate Mobile OTP", mobile_no):
        return gen_response(400, "OTP not generated for this mobile number", {"success": False})

    doc = frappe.get_doc("Validate Mobile OTP", mobile_no)

    current_time = now_datetime()

    if current_time > doc.expiry_time:
        doc.delete(ignore_permissions=True)
        frappe.db.commit()
        return gen_response(400, "OTP has expired. Please request a new OTP.", {"success": False})

    if str(doc.otp) != str(otp):
        return gen_response(400, "Invalid OTP", {"success": False})

    return gen_response(200, "Mobile number verified successfully", {"success": True})


@frappe.whitelist(allow_guest=True)
def send_email_otp(email=None):
    try:
        if not email:
            return gen_response(500,"Email is required")

        # Validate email format
        if not frappe.utils.validate_email_address(email, throw=False):
            return gen_response(500,"Invalid Email Address")
            

        # Generate 6 digit OTP
        otp = str(random.randint(100000, 999999))
        expiry_time = add_to_date(now_datetime(), minutes=10)

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
        return gen_response(400, "Email is required" , {"success": False} )

    if not otp:
        return gen_response(400, "OTP is required", {"success": False})

    doc_name = frappe.db.get_value(
        "Validate Email OTP",
        {"email": email},
        "name"
    )

    if not doc_name:
        return gen_response(400, "OTP not generated for this email", {"success": False})

    doc = frappe.get_doc("Validate Email OTP", doc_name)


    if now_datetime() > doc.expiry_time:
        doc.delete(ignore_permissions=True)
        frappe.db.commit()
        return gen_response(400, "OTP has expired. Please request a new OTP.", {"success": False})

    
    if str(doc.otp) != str(otp):
        return gen_response(400, "Invalid OTP", {"success": False})

    return gen_response(200, "Email verified successfully", {"success": True})