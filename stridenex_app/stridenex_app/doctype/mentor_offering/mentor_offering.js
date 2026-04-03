// Copyright (c) 2026, QTPL and contributors
// For license information, please see license.txt

// frappe.ui.form.on("Mentor Offering", {
// 	refresh(frm) {

// 	},
// });


// mentor_offering/doctype/mentor_offering/mentor_offering.js

frappe.ui.form.on("Mentor Offering", {

    refresh(frm) {
        frm.set_intro(
            frm.doc.status === "Live"
                ? __("This offering is currently Live and visible to students.")
                : __("This offering is in Draft. Activate it to make it visible."),
            frm.doc.status === "Live" ? "green" : "yellow"
        );

        // Pause / Activate / Archive buttons
        if (!frm.is_new()) {
            if (frm.doc.status === "Live") {
                frm.add_custom_button(__("Pause Offering"), () => {
                    toggle_status(frm, "pause");
                }, __("Actions"));
            }
            if (frm.doc.status === "Paused" || frm.doc.status === "Draft") {
                frm.add_custom_button(__("Activate Offering"), () => {
                    toggle_status(frm, "activate");
                }, __("Actions"));
            }
            frm.add_custom_button(__("Archive"), () => {
                toggle_status(frm, "archive");
            }, __("Actions"));
        }

        // Read-only computed fields
        frm.set_df_property("total_bookings", "read_only", 1);
        frm.set_df_property("average_rating", "read_only", 1);
    },

    offering_type(frm) {
        const type = frm.doc.offering_type;

        // Show/hide conditional fields based on offering type
        frm.toggle_display("max_group_size", type === "Group Session");
        frm.toggle_display("turnaround_hours", type === "Async Review");
        frm.toggle_display("sessions_per_month", type === "1:1 Mentorship");
        frm.toggle_display("duration_minutes", type !== "Async Review");

        frm.toggle_reqd("max_group_size", type === "Group Session");
        frm.toggle_reqd("turnaround_hours", type === "Async Review");
    },

    validate(frm) {
        if (frm.doc.price_per_session <= 0) {
            frappe.msgprint(__("Price must be greater than ₹0"));
            frappe.validated = false;
        }
        if (frm.doc.average_rating && (frm.doc.average_rating < 0 || frm.doc.average_rating > 5)) {
            frappe.msgprint(__("Rating must be between 0 and 5"));
            frappe.validated = false;
        }
    }
});

function toggle_status(frm, action) {
    frappe.confirm(
        __(`Are you sure you want to ${action} this offering?`),
        () => {
            frappe.call({
                method: "stridenex_app.stridenex_app.doctype.mentor_offering.mentor_offering.toggle_offering_status",
                args: { offering_name: frm.doc.name, action },
                callback(r) {
                    if (r.message) {
                        frappe.show_alert({
                            message: __(`Offering status updated to ${r.message.status}`),
                            indicator: "green"
                        });
                        frm.reload_doc();
                    }
                }
            });
        }
    );
}