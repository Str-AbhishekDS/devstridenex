// Copyright (c) 2026, QTPL and contributors
// For license information, please see license.txt

// frappe.ui.form.on("Mentor Session Booking", {
// 	refresh(frm) {

// 	},
// });
// Copyright (c) 2024, Your Company and contributors
// For license information, please see license.txt

frappe.ui.form.on("Mentor Session Booking", {
    // ----------------------------------------------------------------
    // Form Setup
    // ----------------------------------------------------------------
    setup(frm) {
        frm.set_query("mentor", () => ({  }));
        frm.set_query("student", () => ({  }));
    },

    refresh(frm) {
        _set_status_indicator(frm);
        _render_action_buttons(frm);
        _toggle_meeting_link_section(frm);
    },

    // ----------------------------------------------------------------
    // Field Events
    // ----------------------------------------------------------------
    mentor(frm) {
        // Reset slots when mentor changes
        if (frm.doc.session_date) {
            _load_available_slots(frm);
        }
    },

    session_date(frm) {
        const today = frappe.datetime.get_today();
        if (frm.doc.session_date && frm.doc.session_date < today) {
            frappe.show_alert({ message: __("Session date cannot be in the past."), indicator: "red" });
            frm.set_value("session_date", null);
            return;
        }
        if (frm.doc.mentor && frm.doc.session_date) {
            _load_available_slots(frm);
        }
    },

    from_time(frm) {
        _validate_time_range(frm);
        _auto_calculate_duration(frm);
    },

    to_time(frm) {
        _validate_time_range(frm);
        _auto_calculate_duration(frm);
    },

    status(frm) {
        _set_status_indicator(frm);
    },
});

// ----------------------------------------------------------------
// Private Helpers
// ----------------------------------------------------------------

/**
 * Colour-code the status badge in the form header.
 */
function _set_status_indicator(frm) {
    const map = {
        Scheduled: "blue",
        Completed: "green",
        Cancelled: "red",
    };
    const colour = map[frm.doc.status] || "grey";
    frm.set_indicator_formatter
        ? frm.set_indicator_formatter("status", () => colour)
        : null;
}

/**
 * Show action buttons (Reschedule, Cancel, Mark Completed) based on current status.
 */
function _render_action_buttons(frm) {
    frm.remove_custom_button(__("Reschedule"));
    frm.remove_custom_button(__("Cancel Session"));
    frm.remove_custom_button(__("Mark as Completed"));

    if (frm.is_new() || !frm.doc.name) return;

    if (frm.doc.status === "Scheduled") {
        frm.add_custom_button(__("Reschedule"), () => _open_reschedule_dialog(frm), __("Actions"));
        frm.add_custom_button(__("Cancel Session"), () => _cancel_session(frm), __("Actions"));
        frm.add_custom_button(__("Mark as Completed"), () => _mark_completed(frm), __("Actions"));
    }

    if (frm.doc.status === "Scheduled") {
        frm.add_custom_button(__("Load Available Slots"), () => _load_available_slots(frm));
    }
}

/**
 * Hide/show the meeting link row based on whether a link is present.
 */
function _toggle_meeting_link_section(frm) {
    frm.set_df_property("meeting_link", "hidden", !frm.doc.meeting_link);
}

/**
 * Warn user if from_time >= to_time.
 */
function _validate_time_range(frm) {
    const { from_time, to_time } = frm.doc;
    if (from_time && to_time && from_time >= to_time) {
        frappe.show_alert({ message: __("From Time must be earlier than To Time."), indicator: "red" });
    }
}

/**
 * Auto-populate the duration field from the time range.
 */
function _auto_calculate_duration(frm) {
    const { from_time, to_time } = frm.doc;
    if (!from_time || !to_time) return;

    const toMins = (t) => {
        const [h, m] = t.split(":").map(Number);
        return h * 60 + m;
    };

    const diff = toMins(to_time) - toMins(from_time);
    if (diff > 0) {
        frm.set_value("duration", diff);
    }
}

/**
 * Fetch available (not blocked, not booked) slots for the selected mentor + date
 * and show them in a dialog so the user can pick one quickly.
 */
function _load_available_slots(frm) {
    const { mentor, session_date } = frm.doc;
    if (!mentor || !session_date) {
        frappe.msgprint(__("Please select a Mentor and Session Date first."));
        return;
    }

    frappe.call({
        method: "stridenex_app.stridenex_app.doctype.mentor_availability.mentor_availability.get_available_slots_for_date",
        args: { mentor, date: session_date },
        freeze: true,
        freeze_message: __("Fetching available slots…"),
        callback({ message: slots }) {
            const available = (slots || []).filter((s) => s.available);

            if (!available.length) {
                frappe.msgprint({
                    title: __("No Available Slots"),
                    message: __("There are no available slots for {0} on {1}.", [mentor, session_date]),
                    indicator: "orange",
                });
                return;
            }

            const d = new frappe.ui.Dialog({
                title: __("Available Slots for {0}", [session_date]),
                size: "small",
            });

            const btns = available
                .map(
                    (s) =>
                        `<button class="btn btn-sm btn-default slot-btn m-1"
                            data-from="${s.from_time}" data-to="${s.to_time}">
                            ${s.from_time.slice(0, 5)} – ${s.to_time.slice(0, 5)}
                        </button>`
                )
                .join("");

            d.$body.html(
                `<p class="text-muted">${__("Click a slot to apply it to the form.")}</p>
                 <div>${btns}</div>`
            );

            d.$body.on("click", ".slot-btn", function () {
                frm.set_value("from_time", $(this).data("from"));
                frm.set_value("to_time", $(this).data("to"));
                d.hide();
            });

            d.show();
        },
    });
}

/**
 * Open a dialog to reschedule the session to a new date/time.
 */
function _open_reschedule_dialog(frm) {
    const d = new frappe.ui.Dialog({
        title: __("Reschedule Session"),
        fields: [
            {
                label: __("New Date"),
                fieldname: "new_date",
                fieldtype: "Date",
                reqd: 1,
                options: { minDate: frappe.datetime.get_today() },
            },
            {
                label: __("New From Time"),
                fieldname: "new_from_time",
                fieldtype: "Time",
                reqd: 1,
            },
            {
                label: __("New To Time"),
                fieldname: "new_to_time",
                fieldtype: "Time",
                reqd: 1,
            },
        ],
        primary_action_label: __("Reschedule"),
        primary_action({ new_date, new_from_time, new_to_time }) {
            frappe.call({
                method: "stridenex_app.stridenex_app.doctype.mentor_session_booking.mentor_session_booking.reschedule_session",
                args: {
                    session_name: frm.doc.name,
                    new_date,
                    new_from_time,
                    new_to_time,
                },
                callback({ message }) {
                    frappe.show_alert({ message, indicator: "green" });
                    frm.reload_doc();
                    d.hide();
                },
            });
        },
    });
    d.show();
}

/**
 * Cancel the session after confirmation.
 */
function _cancel_session(frm) {
    frappe.confirm(
        __("Are you sure you want to cancel session {0}?", [frm.doc.name]),
        () => {
            frappe.call({
                method: "stridenex_app.stridenex_app.doctype.mentor_session_booking.mentor_session_booking.cancel_session",
                args: { session_name: frm.doc.name },
                callback({ message }) {
                    frappe.show_alert({ message, indicator: "green" });
                    frm.reload_doc();
                },
            });
        }
    );
}

/**
 * Mark the session as Completed after confirmation.
 */
function _mark_completed(frm) {
    frappe.confirm(
        __("Mark session {0} as Completed?", [frm.doc.name]),
        () => {
            frappe.call({
                method: "stridenex_app.stridenex_app.doctype.mentor_session_booking.mentor_session_booking.mark_session_completed",
                args: { session_name: frm.doc.name },
                callback({ message }) {
                    frappe.show_alert({ message, indicator: "green" });
                    frm.reload_doc();
                },
            });
        }
    );
}