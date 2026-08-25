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


@frappe.whitelist(allow_guest=True)
def signup():

    if frappe.request.method != "POST":
        return gen_response(400, "Only POST allowed", {"success": False})

    try:
        data = frappe.request.get_json()

        first_name = data.get("first_name")
        last_name = data.get("last_name")
        email = data.get("email")
        password = data.get("password")
        roles = data.get("role")

        if not roles:
            return gen_response(400, "Role selection required", {"success": False})

        if not all([first_name, last_name, email, password]):
            return gen_response(400, "All fields are required", {"success": False})

        if frappe.db.exists("User", email):
            return gen_response(400, "User already exists", {"success": False})

        # Detect selected role
        selected_role = None

        for role_item in roles:
            for key, value in role_item.items():
                if value == 1:
                    selected_role = key
                    break

        if not selected_role:
            return gen_response(400, "Role not selected", {"success": False})

        # Map UI role to system role
        role_map = {
            "student": "Student base",
            "college": "College base",
            "mentor": "Mentor",
            "industry": "Industry base"
        }

        frappe_role = role_map.get(selected_role)
        referral_code = generate_referral_code()

        # Create user
        user = frappe.get_doc({
            "doctype": "User",
            "email": email,
            "first_name": first_name,
            "last_name": last_name,
            "enabled": 1,
            "new_password": password,
            "user_type": "Website User",
            "referal_code": referral_code
        })

        user.flags.no_welcome_mail = True
        user.is_onboarded = False
        user.insert(ignore_permissions=True)

        update_password(user.name, password)

        # Assign role
        user.add_roles(frappe_role)

        frappe.db.commit()

        return gen_response(
            200,
            "User created successfully",
            {
                "success": True,
                "role": frappe_role
            }
        )

    except Exception:
        frappe.log_error(frappe.get_traceback(), "Signup Error")
        return gen_response(500, "Something went wrong", frappe.get_traceback())

def generate_referral_code(length=8):
    """Generate a unique 8-character alphanumeric referral code."""
    chars = string.ascii_uppercase + string.digits

    while True:
        code = "".join(random.choices(chars, k=length))

        if not frappe.db.exists("User", {"referral_code": code}):
            return code


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

            user = login_manager.user
          
            # Get user roles
            roles = frappe.get_roles(user)

            # Remove default roles if needed
            ignore_roles = ["All", "Guest"]
            roles = [r for r in roles if r not in ignore_roles]
            is_onboarded = frappe.db.get_value("User", user, "is_onboarded")
            user_image = frappe.db.get_value("User", user, "user_image")

            frappe.response["user"] = user
            frappe.response["roles"] = roles
            frappe.response["is_onboarded"] = is_onboarded
            frappe.response["user_image"] = user_image
            frappe.response["key_details"] = generate_key(user)

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
        return gen_response(
            400,
            "Mobile number is required"
        )

    # -----------------------------------
    # GENERATE OTP
    # -----------------------------------

    otp = str(random.randint(100000, 999999))

    expiry_time = add_to_date(
        now_datetime(),
        minutes=10
    )

    # -----------------------------------
    # SAVE OTP RECORD
    # -----------------------------------

    try:

        existing_doc = frappe.db.exists(
            "Validate Mobile OTP",
            {"mobile_no": mobile_no}
        )

        if existing_doc:

            otp_doc = frappe.get_doc(
                "Validate Mobile OTP",
                existing_doc
            )

            otp_doc.otp = otp
            otp_doc.expiry_time = expiry_time

            otp_doc.save(ignore_permissions=True)

        else:

            otp_doc = frappe.get_doc({
                "doctype": "Validate Mobile OTP",
                "mobile_no": mobile_no,
                "otp": otp,
                "expiry_time": expiry_time
            })

            otp_doc.insert(ignore_permissions=True)

        # IMPORTANT
        frappe.db.commit()

    except Exception as e:

        frappe.log_error(
            frappe.get_traceback(),
            "OTP Save Failed"
        )

        return gen_response(
            500,
            f"OTP save failed: {str(e)}"
        )

    # -----------------------------------
    # SEND SMS
    # -----------------------------------

    try:

        message = quote(
            f"Your Stridenex account verification OTP is {otp} "
            f".Valid for 10 minutes.Do not share this OTP."
        )

        sms_url = (
            "http://vas.mobilogi.com/api.php"
            f"?username=strdnx"
            f"&password=pass123"
            f"&route=1"
            f"&sender=STRDNX"
            f"&mobile[]={mobile_no}"
            f"&message[]={message}"
            f"&templateid=1007550961776829496"
        )

        response = requests.get(
            sms_url,
            timeout=15
        )

        response_text = response.text.strip()

    except Exception as e:

        frappe.log_error(
            frappe.get_traceback(),
            "OTP SMS Failed"
        )

        return gen_response(
            500,
            f"SMS failed: {str(e)}"
        )

    return gen_response(
        200,
        "OTP sent successfully",
        {
            "mobile_no": mobile_no,
            "sms_response": response_text
        }
    )
    
    

@frappe.whitelist(allow_guest=True)
def validate_mobile_otp(mobile_no=None, otp=None,email=None):
    if not mobile_no:
        return gen_response(400, "Mobile number is required",{"success": False})

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
    
    user = frappe.db.get_value("User", {"email": email}, "name")
    if user:
        frappe.db.set_value("User", user, "is_onboarded", 1)  
        frappe.db.commit()

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

        # Clean HTML body without indentation issues
        html_message = f"""
        <html>
        <body style="font-family: Arial, sans-serif; color: #333;">
            <p>Hello,</p>

            <p>Your One-Time Password (OTP) for Stridenex login is:</p>

            <div style="
                font-size: 28px;
                font-weight: bold;
                letter-spacing: 4px;
                margin: 20px 0;
            ">
                {otp}
            </div>

            <p>This OTP will expire in 5 minutes.</p>

            <p>If you did not request this OTP, please ignore this email.</p>

            <hr>

            <p>
                Regards,<br>
                Stridenex Team
            </p>
        </body>
        </html>
        """

        frappe.sendmail(
            recipients=[email],
            subject="Stridenex Verification",
            message=html_message,
            now=True,
            header=["Stridenex Verification", "green"]
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
    
    # user = frappe.db.get_value("User", {"email": email}, "name")
    # if user:
    #     frappe.db.set_value("User", user, "is_onboarded", 1) 
    #     frappe.db.commit()

    return gen_response(200, "Email verified successfully", {"success": True})


@frappe.whitelist()
def upload_profile_picture():
    """
    Upload a profile picture for the currently authenticated user.
    Mirrors how Frappe Desk handles user profile image uploads:
    - Saves the file to private/files/
    - Links it to the User doctype
    - Sets user_image on the User doc
    Returns the file URL on success.
    """
    try:
        if frappe.request.method != "POST":
            return gen_response(400, "Only POST allowed")

        if "file" not in frappe.request.files:
            return gen_response(400, "No file provided")

        file_obj = frappe.request.files["file"]
        content = file_obj.read()

        # Validate file size (max 5 MB)
        if len(content) > 5 * 1024 * 1024:
            return gen_response(400, "File size exceeds 5 MB limit")

        # Validate file type — images only
        import mimetypes
        mime_type, _ = mimetypes.guess_type(file_obj.filename or "")
        if not mime_type or not mime_type.startswith("image/"):
            return gen_response(400, "Only image files are allowed (JPEG, PNG, GIF, WebP)")

        current_user = frappe.session.user
        if not current_user or current_user == "Guest":
            return gen_response(401, "Authentication required")

        # Build a clean file name scoped to the user
        import os
        ext = os.path.splitext(file_obj.filename or "profile")[1] or ".jpg"
        safe_name = current_user.replace("@", "_at_").replace(".", "_")
        fname = f"profile_{safe_name}{ext}"

        # Use Frappe's standard file save — stores in public files/
        file_doc = frappe.get_doc({
            "doctype": "File",
            "file_name": fname,
            "attached_to_doctype": "User",
            "attached_to_name": current_user,
            "attached_to_field": "user_image",
            "is_private": 0,
            "content": content,
        })
        file_doc.save(ignore_permissions=True)

        # Update user_image on the User doc (same as Frappe Desk does)
        frappe.db.set_value("User", current_user, "user_image", file_doc.file_url)
        frappe.db.commit()

        return gen_response(200, "Profile picture updated successfully", {
            "file_url": file_doc.file_url,
            "file_name": file_doc.file_name,
        })

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Upload Profile Picture Error")
        return gen_response(500, str(e))


@frappe.whitelist()
def get_profile_picture():
    """
    Returns the user_image URL for the currently authenticated user.
    """
    try:
        current_user = frappe.session.user
        if not current_user or current_user == "Guest":
            return gen_response(401, "Authentication required")

        user_image = frappe.db.get_value("User", current_user, "user_image")
        return gen_response(200, "Profile picture fetched", {
            "user_image": user_image or None,
        })

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Get Profile Picture Error")
        return gen_response(500, str(e))


@frappe.whitelist()
def raise_support_ticket(subject=None, description=None, ticket_type=None, priority=None):
    """
    Creates a new support ticket in Frappe Helpdesk.
    """
    try:
        current_user = frappe.session.user
        if not current_user or current_user == "Guest":
            return gen_response(401, "Authentication required")

        if not subject or not description:
            return gen_response(400, "Subject and Description are required")

        # Resolve status (Default to Open or first status)
        default_status = frappe.db.get_value("HD Ticket Status", {"name": "Open"}, "name")
        if not default_status:
            # Fallback to any active status
            default_status = frappe.db.get_value("HD Ticket Status", {}, "name")

        # Resolve priority
        if priority and not frappe.db.exists("HD Ticket Priority", priority):
            priority = None

        # Resolve ticket type
        if ticket_type and not frappe.db.exists("HD Ticket Type", ticket_type):
            ticket_type = None

        ticket = frappe.get_doc({
            "doctype": "HD Ticket",
            "subject": subject,
            "description": description,
            "raised_by": current_user,
            "status": default_status,
            "priority": priority,
            "ticket_type": ticket_type,
            "via_customer_portal": 1
        })
        
        ticket.insert(ignore_permissions=True)
        frappe.db.commit()

        return gen_response(200, "Support ticket created successfully", {
            "name": ticket.name,
            "subject": ticket.subject,
            "status": ticket.status,
            "priority": ticket.priority,
            "creation": ticket.creation
        })

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Raise Support Ticket Error")
        return gen_response(500, str(e))

import os
import mimetypes

import os
import mimetypes

@frappe.whitelist(allow_guest=True)
def upload_file_api():
    """
    Generic file upload endpoint (used here for resumes).
    Saves the file (private or public) and optionally links it to any doctype/docname/field.

    Form-data params expected:
      - file       : the file itself (required)
      - doctype    : target doctype to attach to (optional)
      - docname    : target document name to attach to (optional)
      - fieldname  : target fieldname to attach to, e.g. "resume" (optional)
      - is_private : "1" or "0" (optional, default "1")

    Returns file_url on success.
    """
    try:
        if frappe.request.method != "POST":
            return gen_response(400, "Only POST allowed")

        if "file" not in frappe.request.files:
            return gen_response(400, "No file provided")

        current_user = frappe.session.user  # will be "Guest" for unauthenticated calls
        # if not current_user or current_user == "Guest":
        #     return gen_response(401, "Authentication required")

        file_obj = frappe.request.files["file"]
        content = file_obj.read()

        # Validate file size (max 5 MB)
        if len(content) > 5 * 1024 * 1024:
            return gen_response(400, "File size exceeds 5 MB limit")

        # Validate file type — allow resumes (pdf/doc/docx) + images
        mime_type, _ = mimetypes.guess_type(file_obj.filename or "")
        allowed_mime_types = (
            "application/pdf",
            "application/msword",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "image/jpeg",
            "image/png",
        )
        if not mime_type or mime_type not in allowed_mime_types:
            return gen_response(
                400,
                "Only PDF, DOC, DOCX, JPG, or PNG files are allowed"
            )

        # Optional linking params
        target_doctype = frappe.form_dict.get("doctype")
        target_docname = frappe.form_dict.get("docname")
        target_fieldname = frappe.form_dict.get("fieldname")
        is_private = frappe.form_dict.get("is_private", "1")

        # ---- Permission check if linking to a target document ----
        # if target_doctype and target_docname:
        #     if not frappe.has_permission(
        #         target_doctype,
        #         ptype="write",
        #         doc=target_docname,
        #         user=current_user
        #     ):
        #         return gen_response(
        #             403,
        #             f"You do not have permission to update {target_doctype} {target_docname}"
        #         )

        # Build a clean file name, preserving the real extension
        ext = os.path.splitext(file_obj.filename or "")[1]
        if not ext:
            ext = mimetypes.guess_extension(mime_type) or ".bin"
        safe_name = current_user.replace("@", "_at_").replace(".", "_")
        fname = f"{safe_name}_{frappe.generate_hash(length=6)}{ext}"

        file_doc = frappe.get_doc({
            "doctype": "File",
            "file_name": fname,
            "attached_to_doctype": target_doctype,
            "attached_to_name": target_docname,
            "attached_to_field": target_fieldname,
            "is_private": 1 if str(is_private) == "1" else 0,
            "content": content,
        })
        file_doc.insert(ignore_permissions=True)

        # If a target doctype/docname/fieldname was given, set the field value too
        if target_doctype and target_docname and target_fieldname:
            frappe.db.set_value(
                target_doctype, target_docname, target_fieldname, file_doc.file_url
            )
            frappe.db.commit()

        return gen_response(200, "File uploaded successfully", {
            "file_url": file_doc.file_url,
            "file_name": file_doc.file_name,
            "is_private": file_doc.is_private,
        })

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Upload File Error")
        return gen_response(500, str(e))
    

@frappe.whitelist(allow_guest=True)
def get_file_api(doctype=None, docname=None, fieldname=None):
    """
    Fetch file(s) attached to a specific doctype/docname (optionally filtered by fieldname).

    Query params expected:
      - doctype   : target doctype the file is attached to (required)
      - docname   : target document name (required)
      - fieldname : specific field, e.g. "resume" (optional — omit to get all files on that doc)
    """
    try:
        current_user = frappe.session.user
        # if not current_user or current_user == "Guest":
        #     return gen_response(401, "Authentication required")

        if not doctype or not docname:
            return gen_response(400, "doctype and docname are required")

        if not frappe.has_permission(
            doctype, ptype="read", doc=docname, user=current_user
        ):
            return gen_response(
                403, f"You do not have permission to read {doctype} {docname}"
            )

        filters = {
            "attached_to_doctype": doctype,
            "attached_to_name": docname,
        }
        if fieldname:
            filters["attached_to_field"] = fieldname

        files = frappe.get_all(
            "File",
            filters=filters,
            fields=[
                "name", "file_name", "file_url", "is_private",
                "attached_to_field", "creation"
            ],
            order_by="creation desc"
        )

        return gen_response(200, "Files fetched successfully", {"files": files})

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Get File Error")
        return gen_response(500, str(e))
    
@frappe.whitelist()
def get_support_tickets(status=None):
    """
    Fetches the support tickets raised by the current logged-in user.
    """
    try:
        current_user = frappe.session.user
        if not current_user or current_user == "Guest":
            return gen_response(401, "Authentication required")

        filters = {"raised_by": current_user}
        if status:
            filters["status"] = status

        tickets = frappe.get_all(
            "HD Ticket",
            filters=filters,
            fields=["name", "subject", "status", "priority", "ticket_type", "creation", "modified"],
            order_by="creation desc"
        )

        return gen_response(200, "Support tickets fetched successfully", tickets)

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Get Support Tickets Error")
        return gen_response(500, str(e))




# @frappe.whitelist(allow_guest=True)
# def get_offer_letter(student, offer_type, name, template):
#     if not student:
#         frappe.throw("Student is required")

#     if not template:
#         frappe.throw("Template is required")

#     if not name:
#         frappe.throw("Name is required")

#     if not frappe.db.exists("Student", student):
#         frappe.throw("Student not found", frappe.DoesNotExistError)

#     doc = frappe.get_doc("Student", student)

#     template_map = {
#         "Internship": "stridenex_app/templates/offer_letter/internship_offer.html",
#         "Job": "stridenex_app/templates/offer_letter/job_offer.html",
#         "Project": "stridenex_app/templates/offer_letter/project_offer.html",
#     }

#     doctype_map = {
#         "Internship": "Internship",
#         "Job": "Industry Job Profile",
#         "Project": "Industry Project",
#     }

#     template_path = template_map.get(offer_type)
#     doctype_name = doctype_map.get(offer_type)

#     if not template_path or not doctype_name:
#         frappe.throw(f"Invalid offer_type: {offer_type}")

#     if not frappe.db.exists(doctype_name, name):
#         frappe.throw(f"{doctype_name} '{name}' not found", frappe.DoesNotExistError)

#     record = frappe.get_doc(doctype_name, name)

#     # path to the bundled static logo, as a file:// URI so wkhtmltopdf can read it directly
#     static_logo_path = frappe.get_app_path(
#         "stridenex_app", "templates", "static", "Stridenex Logo png.png"
#     )
#     static_logo_url = f"file://{static_logo_path}"

#     context = {
#         "doc": doc,
#         "static_logo_url": static_logo_url,
#     }

#     # pass the record under the variable name each template expects
#     context_key_map = {
#         "Internship": "internship",
#         "Job": "job",
#         "Project": "project",
#     }
#     context[context_key_map[offer_type]] = record

#     html = frappe.render_template(template_path, context)

#     pdf = get_pdf(html)

#     frappe.local.response.filename = f"{doc.first_name}_{doc.last_name}_Offer_Letter.pdf"
#     frappe.local.response.filecontent = pdf
#     frappe.local.response.type = "download"

# import frappe
# from frappe.utils.pdf import get_pdf

@frappe.whitelist(allow_guest=True)
def get_offer_letter(student, offer_type, name, template):
    if not student:
        frappe.throw("Student is required")

    if not template:
        frappe.throw("Template is required")

    if not name:
        frappe.throw("Name is required")

    if not frappe.db.exists("Student", student):
        frappe.throw("Student not found", frappe.DoesNotExistError)

    doc = frappe.get_doc("Student", student)

    template_map = {
    "Internship": "stridenex_app/templates/offer_letter/internship_offer.html",
    "Job": "stridenex_app/templates/offer_letter/job_offer.html",
    "Project": "stridenex_app/templates/offer_letter/project_offer.html",
        }

    doctype_map = {
    "Internship": "Internship",
    "Job": "Industry Job Profile",
    "Project": "Industry Project",
        }

    template_path = template_map.get(offer_type)
    doctype_name = doctype_map.get(offer_type)

    if not template_path or not doctype_name:
        frappe.throw(f"Invalid offer_type: {offer_type}")

    if not frappe.db.exists(doctype_name, name):
        frappe.throw(f"{doctype_name} '{name}' not found", frappe.DoesNotExistError)

    record = frappe.get_doc(doctype_name, name)

    # path to the bundled static logo, as a file:// URI so wkhtmltopdf can read it directly
    static_logo_path = frappe.get_app_path(
    "stridenex_app", "templates", "static", "Stridenex Logo png.png"
        )
    static_logo_url = f"file://{static_logo_path}"

    context = {
    "doc": doc,
    "static_logo_url": static_logo_url,
        }

    # pass the record under the variable name each template expects
    context_key_map = {
    "Internship": "internship",
    "Job": "job",
    "Project": "project",
        }
    context[context_key_map[offer_type]] = record

    html = frappe.render_template(template_path, context)

    pdf = get_pdf(html)

    frappe.local.response.filename = f"{doc.first_name}_{doc.last_name}_Offer_Letter.pdf"
    frappe.local.response.filecontent = pdf
    frappe.local.response.type = "download"   