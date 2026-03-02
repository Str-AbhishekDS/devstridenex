import frappe
from stridenex_app.api_stridenex_app.app_utils import (
    gen_response, 
    generate_key, 
    exception_handel
    ) 


"""List of all state"""

@frappe.whitelist(allow_guest=True)
def get_state():
    states = frappe.get_all("State", fields=["state_name"])
    if states:
        gen_response(200, "State list retrieved successfully", states)
    else:
        gen_response(400, "No data found", {"success": False})

"""List of all district as per state"""

@frappe.whitelist(allow_guest=True)
def get_district(state=None):
    if not state:
        return gen_response(400, "State is required", {"success": False})

    districts = frappe.get_all(
        "District", filters={"state": state}, fields=["district_name"]
    )
    if districts:
        return gen_response(200, "District list retrieved successfully", districts)
    else:
        return gen_response(404, "No data found", [])


"""list of tehsil as per district"""

@frappe.whitelist(allow_guest=True)
def get_tahsil(district=None):
    state_names = frappe.get_all(
    "Tahsil", filters={"district": district}, fields=["tahsil_name"]
    )
    if state_names:
        gen_response(200, "Tahsil list retrieved successfully", state_names)
    else:
        gen_response(400, "No data found", {"success": False})

@frappe.whitelist(allow_guest=True)
def get_city(district=None, tahsil=None):
    state_names = frappe.get_all(
    "City", filters={"district": district, "tahsil": tahsil}, fields=["city_name"]
    )
    if state_names:
        gen_response(200, "City list retrieved successfully", state_names)
    else:
        gen_response(400, "No data found", {"success": False})