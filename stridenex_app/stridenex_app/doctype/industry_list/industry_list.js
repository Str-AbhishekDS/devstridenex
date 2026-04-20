// Copyright (c) 2026, QTPL and contributors
// For license information, please see license.txt

// frappe.ui.form.on("Industry list", {
// 	refresh(frm) {

// 	},
// });
frappe.ui.form.on('Industry list', {

    refresh: function(frm) {

        // State filter
        frm.set_query('state', function() {
            return {
                filters: {
                    country: frm.doc.country
                }
            };
        });

        // District filter
        frm.set_query('district', function() {
            return {
                filters: {
                    state: frm.doc.state
                }
            };
        });

        // tahsil filter
        frm.set_query('tahsil', function() {
            return {
                filters: {
                    district: frm.doc.district
                }
            };
        });

        // City filter
        frm.set_query('city', function() {
            return {
                filters: {
                    tahsil: frm.doc.tahsil
                }
            };
        });

    },

    country: function(frm) {
        frm.set_value('state', '');
        frm.set_value('district', '');
        frm.set_value('tahsil', '');
        frm.set_value('city', '');
    },

    state: function(frm) {
        frm.set_value('district', '');
        frm.set_value('tahsil', '');
        frm.set_value('city', '');
    },

    district: function(frm) {
        frm.set_value('tahsil', '');
        frm.set_value('city', '');
    },

    tahsil: function(frm) {
        frm.set_value('city', '');
    }

});