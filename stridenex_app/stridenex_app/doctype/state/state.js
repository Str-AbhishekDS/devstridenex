// Copyright (c) 2026, QTPL and contributors
// For license information, please see license.txt

// frappe.ui.form.on("State", {
// 	refresh(frm) {

// 	},
// });
frappe.ui.form.on('State', {

    refresh: function(frm) {

        // Filter Country (optional if needed)
        frm.set_query('country', function() {
            return {
                filters: {}
            };
        });

    }

});