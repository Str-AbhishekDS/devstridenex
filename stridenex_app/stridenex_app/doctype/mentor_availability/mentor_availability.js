// Copyright (c) 2026, QTPL and contributors
// For license information, please see license.txt

// frappe.ui.form.on("Mentor Availability", {
// 	refresh(frm) {

// 	},
// });
// Copyright (c) 2024, Your Company and contributors
// For license information, please see license.txt

frappe.ui.form.on("Mentor Availability", {
    // ----------------------------------------------------------------
    // Form Setup
    // ----------------------------------------------------------------
    setup(frm) {
        frm.set_query("mentor", () => ({}));
    },

    refresh(frm) {
        _set_time_field_constraints(frm);

        if (!frm.is_new()) {
            frm.add_custom_button(__("View Weekly Grid"), () => {
                _show_weekly_grid(frm.doc.mentor);
            });
        }
    },

    // ----------------------------------------------------------------
    // Field Events
    // ----------------------------------------------------------------
    mentor(frm) {
        // Clear stale slot info when the mentor changes
        frm.set_value("from_time", null);
        frm.set_value("to_time", null);
    },

    from_time(frm) {
        _validate_time_range(frm);
    },

    to_time(frm) {
        _validate_time_range(frm);
    },
});

// ----------------------------------------------------------------
// Private Helpers
// ----------------------------------------------------------------

/**
 * Show an inline warning if from_time >= to_time so the user
 * knows before hitting Save.
 */
function _validate_time_range(frm) {
    const { from_time, to_time } = frm.doc;
    if (from_time && to_time) {
        if (from_time >= to_time) {
            frappe.msgprint({
                title: __("Invalid Time Range"),
                message: __("From Time must be earlier than To Time."),
                indicator: "red",
            });
        }
    }
}

/**
 * Apply a read-only constraint to prevent selecting times outside
 * standard business hours (06:00 – 23:00).
 * Frappe Time fields don't natively clamp, so we show a warning instead.
 */
function _set_time_field_constraints(frm) {
    ["from_time", "to_time"].forEach((field) => {
        frm.fields_dict[field] && frm.fields_dict[field].$input &&
            frm.fields_dict[field].$input.on("change", function () {
                const val = $(this).val();
                if (val && (val < "06:00:00" || val > "23:00:00")) {
                    frappe.show_alert({
                        message: __("Please select a time between 06:00 and 23:00."),
                        indicator: "orange",
                    });
                }
            });
    });
}

/**
 * Open a dialog that displays the mentor's full weekly availability grid,
 * annotated with booked and blocked status for today.
 */
function _show_weekly_grid(mentor) {
    if (!mentor) return;

    const today = frappe.datetime.get_today();
    let dialog;

    frappe.call({
        method: "stridenex_app.stridenex_app.doctype.mentor_availability.mentor_availability.get_available_slots_for_date",
        args: { mentor, date: today },
        freeze: true,
        freeze_message: __("Loading availability…"),
        callback({ message: slots }) {
            const rows = (slots || [])
                .map((s) => {
                    const badge = s.is_booked
                        ? `<span class="badge badge-danger">${__("Booked")}</span>`
                        : s.is_blocked
                        ? `<span class="badge badge-warning">${__("Blocked")}</span>`
                        : `<span class="badge badge-success">${__("Available")}</span>`;
                    return `<tr>
                        <td>${s.from_time}</td>
                        <td>${s.to_time}</td>
                        <td>${badge}</td>
                    </tr>`;
                })
                .join("");

            dialog = new frappe.ui.Dialog({
                title: __("Availability for {0} on {1}", [mentor, today]),
                size: "large",
            });

            dialog.$body.html(`
                <table class="table table-bordered table-sm">
                    <thead>
                        <tr>
                            <th>${__("From")}</th>
                            <th>${__("To")}</th>
                            <th>${__("Status")}</th>
                        </tr>
                    </thead>
                    <tbody>${rows || `<tr><td colspan="3">${__("No slots found")}</td></tr>`}</tbody>
                </table>
            `);

            dialog.show();
        },
    });
}