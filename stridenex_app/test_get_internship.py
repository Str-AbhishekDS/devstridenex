import frappe
from stridenex_app.stridenex_app.doctype.internship.internship import get_internship_list

def run():
    res = get_internship_list(student="stu2@gmail.com")
    import json
    print(json.dumps(res))
