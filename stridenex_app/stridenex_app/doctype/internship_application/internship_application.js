// Copyright (c) 2026, QTPL and contributors
// For license information, please see license.txt

// frappe.ui.form.on("Internship Application", {
// 	refresh(frm) {

// 	},
// });
frappe.ui.form.on('Internship Application', {

    refresh(frm) {

        if (!frm.is_new()) {

            // Open Internship Button
            frm.add_custom_button('View Internship', () => {
                frappe.set_route('Form', 'Internship', frm.doc.internship);
            });
        }
    },

    student(frm) {
        calculate_match(frm);
    },

    internship(frm) {
        calculate_match(frm);
    }
});



function calculate_match(frm) {

    if (!frm.doc.student || !frm.doc.internship) return;

    frappe.call({
        method: "stridenex_app.stridenex_app.doctype.internship_application.internship_application.get_match_score",
        args: {
            student: frm.doc.student,
            internship: frm.doc.internship
        },
        callback: function (r) {
            if (r.message !== undefined) {
                frm.set_value("match_score", r.message);
            }
        }
    });
}

frappe.ui.form.on('Internship Application', {
    internship: function (frm) {
        console.log("Internship changed:", frm.doc.internship);

        if (frm.doc.internship) {
            frappe.db.get_value('Internship', frm.doc.internship, 'industry')
                .then(r => {
                    console.log("Response:", r);

                    if (r.message && r.message.industry) {
                        frm.set_value('industry', r.message.industry);
                    } else {
                        frm.set_value('industry', '');
                    }
                });
        } else {
            frm.set_value('industry', '');
        }
    }
});