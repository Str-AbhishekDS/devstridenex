// Copyright (c) 2026, QTPL and contributors
// For license information, please see license.txt

// frappe.ui.form.on("Internship", {
// 	refresh(frm) {

// 	},
// });
frappe.ui.form.on('Internship', {

    refresh(frm) {

        if (!frm.is_new()) {

            // Button: View Applications
            frm.add_custom_button('View Applications', () => {
                frappe.set_route('List', 'Internship Application', {
                    internship: frm.doc.name
                });
            });
        }
    },

    deadline(frm) {
        if (frm.doc.deadline) {
            let today = frappe.datetime.get_today();

            if (frm.doc.deadline < today) {
                frappe.msgprint("Deadline is in the past");
            }
        }
    }
});