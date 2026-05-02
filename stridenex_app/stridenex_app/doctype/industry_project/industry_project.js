// Copyright (c) 2026, QTPL and contributors
// For license information, please see license.txt

// frappe.ui.form.on("Industry Project", {
// 	refresh(frm) {

// 	},
// });
frappe.ui.form.on('Student Project Enrollment', {
    project: function (frm) {

        if (!frm.doc.project) {
            return frm.set_value('industry', '');
        }

        // ✅ Split value
        let parts = frm.doc.project.split("-");
        let project_code = parts.pop(); // CB-001
        let project_name = parts.join("-"); // Cyber Security

        console.log("Name:", project_name);
        console.log("Code:", project_code);

        frappe.db.get_value(
            'Industry Project',
            {
                project_name: project_name,
                project_code: project_code
            },
            'industry'
        ).then(r => {
            console.log("Response:", r);

            frm.set_value('industry', r.message?.industry || '');
        });
    }
});