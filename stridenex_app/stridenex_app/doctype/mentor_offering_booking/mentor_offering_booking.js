// Copyright (c) 2026, QTPL and contributors
// For license information, please see license.txt

// frappe.ui.form.on("Mentor Offering Booking", {
// 	refresh(frm) {

// 	},
// });


// mentor_offering/doctype/mentor_offering_booking/mentor_offering_booking.js

frappe.ui.form.on("Mentor Offering Booking", {

    refresh(frm) {

        if (frm.doc.docstatus === 1) {

            if (frm.doc.status !== "Completed") {
                frm.add_custom_button(__("Mark as Completed"), () => {
                    update_booking_status(frm, "Completed");
                }, __("Actions"));
            }

            if (frm.doc.status !== "Cancelled") {
                frm.add_custom_button(__("Cancel Booking"), () => {
                    update_booking_status(frm, "Cancelled");
                }, __("Actions"));
            }
        }


        // Show review button only for completed, submitted bookings
        if (frm.doc.status === "Completed" && frm.doc.docstatus === 1 && !frm.doc.rating) {
            frm.add_custom_button(__("Submit Review"), () => {
                submit_review_dialog(frm);
            });
        }

        frm.set_df_property("mentor", "read_only", 1);
    },

    offering(frm) {
        if (frm.doc.offering) {
            frappe.db.get_value("Mentor Offering", frm.doc.offering, 
                ["price_per_session", "mentor"], (r) => {
                if (r) {
                    frm.set_value("amount_paid", r.price_per_session);
                    frm.set_value("mentor", r.mentor);
                }
            });
        }
    },
    
});

function submit_review_dialog(frm) {
    const d = new frappe.ui.Dialog({
        title: __("Submit Review"),
        fields: [
            {
                fieldtype: "Float",
                fieldname: "rating",
                label: __("Rating (1-5)"),
                reqd: 1
            },
            {
                fieldtype: "Small Text",
                fieldname: "review_text",
                label: __("Review"),
                reqd: 1
            }
        ],
        primary_action_label: __("Submit"),
        primary_action(values) {
            frappe.call({
                method: "stridenex_app.stridenex_app.doctype.mentor_offering_booking.mentor_offering_booking.submit_review",
                args: {
                    booking_name: frm.doc.name,
                    rating: values.rating,
                    review_text: values.review_text
                },
                callback(r) {
                    if (r.message && r.message.success) {
                        frappe.show_alert({ message: __("Review submitted!"), indicator: "green" });
                        frm.reload_doc();
                        d.hide();
                    }
                }
            });
        }
    });
    d.show();
}

function update_booking_status(frm, status) {
    frappe.call({
        method: "stridenex_app.stridenex_app.doctype.mentor_offering_booking.mentor_offering_booking.update_status",
        args: {
            booking_name: frm.doc.name,
            status: status
        },
        callback(r) {
            if (r.message) {
                frappe.show_alert({
                    message: __("Status updated to " + status),
                    indicator: "green"
                });
                frm.reload_doc();
            }
        }
    });
}