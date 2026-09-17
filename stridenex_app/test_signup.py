import frappe

def test():
    frappe.set_user("Administrator")
    email = "teststudentbase12@example.com"
    if frappe.db.exists("User", email):
        frappe.delete_doc("User", email, force=1)

    user = frappe.get_doc({
        "doctype": "User",
        "email": email,
        "first_name": "Test",
        "enabled": 1,
        "new_password": "password",
        "user_type": "Website User",
    })
    user.insert(ignore_permissions=True)
    user.add_roles("Student base")
    frappe.db.commit()

    user.reload()
    print("--- Results for Student base ---")
    print("User Type with Student base:", user.user_type)
    print("Desk Access for User:", user.has_desk_access())
    print("Roles of User:", [r.role for r in user.roles])

    email2 = "teststudent12@example.com"
    if frappe.db.exists("User", email2):
        frappe.delete_doc("User", email2, force=1)

    user2 = frappe.get_doc({
        "doctype": "User",
        "email": email2,
        "first_name": "Test",
        "enabled": 1,
        "new_password": "password",
        "user_type": "Website User",
    })
    user2.insert(ignore_permissions=True)
    user2.add_roles("Student")
    frappe.db.commit()

    user2.reload()
    print("--- Results for Student ---")
    print("User Type with Student:", user2.user_type)
    print("Desk Access for User2:", user2.has_desk_access())
    print("Roles of User2:", [r.role for r in user2.roles])

