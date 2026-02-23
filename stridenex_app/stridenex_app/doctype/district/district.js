// Copyright (c) 2026, QTPL and contributors
// For license information, please see license.txt

// frappe.ui.form.on("District", {
// 	refresh(frm) {

// 	},
// });
frappe.ui.form.on('District', {

    refresh: function(frm) {

        // Filter State based on Country
        frm.set_query('state', function() {
            return {
                filters: {
                    country: frm.doc.country
                }
            };
        });

    },

    country: function(frm) {
        frm.set_value('state', '');
    }

});