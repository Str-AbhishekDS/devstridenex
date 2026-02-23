// Copyright (c) 2026, QTPL and contributors
// For license information, please see license.txt

// frappe.ui.form.on("Str Program", {
// 	refresh(frm) {

// 	},
// });
frappe.ui.form.on('Str Program', {

    university: function (frm) {

        // Filter College based on selected University
        frm.set_query('college', function () {
            return {
                filters: {
                    university: frm.doc.university
                }
            };
        });

        // Clear college if university changes
        frm.set_value('college', null);
    }
});