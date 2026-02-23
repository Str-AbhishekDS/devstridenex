// Copyright (c) 2026, QTPL and contributors
// For license information, please see license.txt

// frappe.ui.form.on("City", {
// 	refresh(frm) {

// 	},
// });
frappe.ui.form.on('City', {

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

        // Filter tahsil based on District
        frm.set_query('tahsil', function() {
            return {
                filters: {
                    district: frm.doc.district
                }
            };
        });

    },

    country: function(frm) {
        frm.set_value('state', '');
        frm.set_value('district', '');
        frm.set_value('tahsil', '');
    },

    state: function(frm) {
        frm.set_value('district', '');
        frm.set_value('tahsil', '');
    },

    district: function(frm) {
        frm.set_value('tahsil', '');
    }

});