import frappe
import requests

def call_uat_api(method_name, params=None):
    """
    Authenticates with UAT site and calls a whitelisted API method.
    """
    settings = frappe.get_single("Billing Settings")
    if not settings.sys_url:
        frappe.throw("System URL (sys_url) is missing in Billing Settings")
        
    if not settings.billing_user or not settings.billing_user_password:
        frappe.throw("Billing User credentials missing in Billing Settings")
        
    remote_url = settings.sys_url.rstrip("/")
    login_url = f"{remote_url}/api/method/login"
    api_url = f"{remote_url}/api/method/{method_name}"
    
    session = requests.Session()
    
    # 1. Login
    login_payload = {
        "usr": settings.billing_user,
        "pwd": settings.billing_user_password
    }
    
    # Bypass certificate verification if local/self-signed certs are used
    try:
        login_res = session.post(login_url, data=login_payload, timeout=15, verify=False)
        if login_res.status_code != 200:
            frappe.throw(f"Failed to authenticate with UAT: {login_res.text}")
            
        # 2. Call Method
        res = session.post(api_url, json=params or {}, headers={"Content-Type": "application/json"}, timeout=30, verify=False)
        if res.status_code != 200:
            frappe.throw(f"UAT API Call to {method_name} failed: {res.text}")
            
        data = res.json()
        if "message" in data:
            return data["message"]
        return data
        
    except requests.exceptions.RequestException as e:
        frappe.throw(f"Communication error with UAT: {str(e)}")
