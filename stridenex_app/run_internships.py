import frappe
def run():
    from stridenex_app.stridenex_app.doctype.internship.internship import get_internship_list
    try:
        res = get_internship_list(student="stu2@gmail.com")
        if res.get("status") != 200:
            print("ERROR", res)
            return
        internships = res.get("data", {}).get("internships", [])
        print("RESULT_START", len(internships), "RESULT_END")
    except Exception as e:
        print("ERROR_START", str(e), "ERROR_END")
