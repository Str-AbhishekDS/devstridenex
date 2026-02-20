// Copyright (c) 2026, QTPL and contributors
// For license information, please see license.txt

// frappe.ui.form.on("Tahsil", {
// 	refresh(frm) {

// 	},
// });
frappe.ui.form.on('tahsil', {

    refresh: function(frm) {

        // Filter State based on Country
        frm.set_query('state', function() {
            return {
                filters: {
                    country: frm.doc.country
                }
            };
        });

        // Filter District based on State
        frm.set_query('district', function() {
            return {
                filters: {
                    state: frm.doc.state
                }
            };
        });

    },

    country: function(frm) {
        frm.set_value('state', '');
        frm.set_value('district', '');
    },

    state: function(frm) {
        frm.set_value('district', '');
    }

});