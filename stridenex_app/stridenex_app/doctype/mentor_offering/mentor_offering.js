// Copyright (c) 2026, QTPL and contributors
// For license information, please see license.txt

const APP = "stridenex_app";

frappe.ui.form.on("Mentor Offering", {

    refresh(frm) {
        // ── Status intro bar ──────────────────────────────────────────
        frm.set_intro(
            frm.doc.status === "Live"
                ? __("This offering is currently Live and visible to students.")
                : __("This offering is in Draft. Activate it to make it visible."),
            frm.doc.status === "Live" ? "green" : "yellow"
        );

        // ── Action buttons ────────────────────────────────────────────
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

        // ── LMS Batch button — Group Session only ─────────────────────
        if (frm.doc.offering_type === "Group Session" && !frm.is_new()) {
            _render_lms_batch_button(frm);
        }

        // ── Read-only computed fields ─────────────────────────────────
        frm.set_df_property("total_bookings", "read_only", 1);
        frm.set_df_property("average_rating",  "read_only", 1);
        frm.set_df_property("lms_batch",       "read_only", 1);
    },

    offering_type(frm) {
        const type = frm.doc.offering_type;
        frm.toggle_display("max_group_size",    type === "Group Session");
        frm.toggle_display("lms_batch",         type === "Group Session");
        frm.toggle_display("turnaround_hours",  type === "Async Review");
        frm.toggle_display("sessions_per_month",type === "1:1 Mentorship");
        frm.toggle_display("duration_minutes",  type !== "Async Review");
        frm.toggle_reqd("max_group_size",   type === "Group Session");
        frm.toggle_reqd("turnaround_hours", type === "Async Review");

        // Re-render the LMS button when type changes
        frm.refresh();
    },

    validate(frm) {
        if (frm.doc.price_per_session <= 0) {
            frappe.msgprint(__("Price must be greater than ₹0"));
            frappe.validated = false;
        }
    },

    lms_batch(frm) {
        // Auto-fill max_group_size from batch seat_count if batch is linked manually
        if (frm.doc.lms_batch) {
            frappe.db.get_value("LMS Batch", frm.doc.lms_batch, "seat_count", (r) => {
                if (r && r.seat_count && !frm.doc.max_group_size) {
                    frm.set_value("max_group_size", r.seat_count);
                }
            });
        }
    },
});


// ── Helpers ────────────────────────────────────────────────────────────────

function _render_lms_batch_button(frm) {
    // Remove old button first to avoid duplicates on refresh
    frm.remove_custom_button(__("🎓 Create LMS Batch"));
    frm.remove_custom_button(__("🎓 Open LMS Batch"));

    if (frm.doc.lms_batch) {
        // Batch already exists — show Open button
        frm.add_custom_button(__("🎓 Open LMS Batch"), () => {
            frappe.set_route("Form", "LMS Batch", frm.doc.lms_batch);
        });

    } else {
        // No batch yet — show Create button
        frm.add_custom_button(__("🎓 Create LMS Batch"), () => {
            // Validate required fields before calling API
            if (!frm.doc.title) {
                frappe.msgprint(__("Please enter an Offering Title before creating a batch."));
                return;
            }
            if (!frm.doc.mentor) {
                frappe.msgprint(__("Please select a Mentor before creating a batch."));
                return;
            }
            if (!frm.doc.max_group_size) {
                frappe.msgprint(__("Please set Max Group Size before creating a batch."));
                return;
            }

            // Must be saved first
            if (frm.is_dirty()) {
                frappe.msgprint(__("Please save the offering first, then create the batch."));
                return;
            }

            frappe.confirm(
                __('Create LMS Batch for "{0}"?', [frm.doc.title]),
                () => {
                    frappe.call({
                        method: `${APP}.${APP}.doctype.mentor_offering.mentor_offering.create_lms_batch_for_offering`,
                        args:   { offering_name: frm.doc.name },
                        freeze: true,
                        freeze_message: __("Creating LMS Batch…"),
                        callback({ message }) {
                            if (message.already_exists) {
                                frappe.show_alert({
                                    message:   __("Batch already exists."),
                                    indicator: "blue"
                                });
                            } else {
                                frappe.show_alert({
                                    message:   __("✅ LMS Batch created: {0}", [message.batch_name]),
                                    indicator: "green"
                                });
                                frm.reload_doc();
                            }
                            // Open the batch so mentor can set dates & publish
                            setTimeout(() => {
                                frappe.set_route("Form", "LMS Batch", message.batch_name);
                            }, 800);
                        },
                        error(err) {
                            frappe.msgprint({
                                title:   __("Error"),
                                message: err.message || __("Failed to create LMS Batch."),
                                indicator: "red"
                            });
                        }
                    });
                }
            );
        });
    }
}


function toggle_status(frm, action) {
    frappe.confirm(
        __("Are you sure you want to {0} this offering?", [action]),
        () => {
            frappe.call({
                method: `${APP}.${APP}.doctype.mentor_offering.mentor_offering.toggle_offering_status`,
                args:   { offering_name: frm.doc.name, action },
                callback(r) {
                    if (r.message) {
                        frappe.show_alert({
                            message:   __("Offering status updated to {0}", [r.message.status]),
                            indicator: "green"
                        });
                        frm.reload_doc();
                    }
                }
            });
        }
    );
}