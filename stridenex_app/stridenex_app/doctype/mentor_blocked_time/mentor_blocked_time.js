// Copyright (c) 2026, QTPL and contributors
// For license information, please see license.txt

// frappe.ui.form.on("Mentor Blocked Time", {
// 	refresh(frm) {

// 	},
// });


frappe.ui.form.on("Mentor Blocked Time", {
    // ----------------------------------------------------------------
    // Form Setup
    // ----------------------------------------------------------------
    setup(frm) {
        frm.set_query("mentor", () => ({
            filters: { enabled: 1 },
        }));
    },

    refresh(frm) {
        // Restrict date picker to today and future
        frm.fields_dict.date.df.options = {
            minDate: frappe.datetime.get_today(),
        };

        if (!frm.is_new()) {
            frm.add_custom_button(__("Check Conflicting Sessions"), () => {
                _check_conflicting_sessions(frm);
            });
        }
    },

    // ----------------------------------------------------------------
    // Field Events
    // ----------------------------------------------------------------
    mentor(frm) {
        frm.set_value("date", null);
        frm.set_value("from_time", null);
        frm.set_value("to_time", null);
    },

    date(frm) {
        // Warn immediately if a past date is selected
        const today = frappe.datetime.get_today();
        if (frm.doc.date && frm.doc.date < today) {
            frappe.show_alert({
                message: __("Cannot block time for a past date."),
                indicator: "red",
            });
            frm.set_value("date", null);
        }
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
 * Client-side validation of the time range (mirrors server validation).
 */
function _validate_time_range(frm) {
    const { from_time, to_time } = frm.doc;
    if (from_time && to_time && from_time >= to_time) {
        frappe.show_alert({
            message: __("From Time must be earlier than To Time."),
            indicator: "red",
        });
    }
}

/**
 * Query the server for any Scheduled sessions that conflict with the
 * current blocked-time window and display them in a dialog.
 */
function _check_conflicting_sessions(frm) {
    const { mentor, date, from_time, to_time } = frm.doc;

    if (!mentor || !date || !from_time || !to_time) {
        frappe.msgprint(__("Please fill in Mentor, Date, From Time, and To Time first."));
        return;
    }

    frappe.call({
        method: "frappe.client.get_list",
        args: {
            doctype: "Mentor Session Booking",
            filters: {
                mentor,
                session_date: date,
                status: "Scheduled",
            },
            fields: ["name", "student", "topic", "from_time", "to_time"],
        },
        callback({ message: sessions }) {
            // Filter client-side for overlap
            const conflicting = (sessions || []).filter(
                (s) => s.from_time < to_time && from_time < s.to_time
            );

            if (!conflicting.length) {
                frappe.show_alert({
                    message: __("No conflicting sessions found."),
                    indicator: "green",
                });
                return;
            }

            const rows = conflicting
                .map(
                    (s) =>
                        `<tr>
                            <td><a href="/app/mentor-session-booking/${s.name}">${s.name}</a></td>
                            <td>${s.student}</td>
                            <td>${s.topic}</td>
                            <td>${s.from_time} – ${s.to_time}</td>
                        </tr>`
                )
                .join("");

            const d = new frappe.ui.Dialog({
                title: __("Conflicting Sessions"),
                size: "large",
            });

            d.$body.html(`
                <p class="text-muted">
                    ${__("The following sessions overlap with the blocked time window and may need to be rescheduled or cancelled.")}
                </p>
                <table class="table table-bordered table-sm">
                    <thead>
                        <tr>
                            <th>${__("Session")}</th>
                            <th>${__("Student")}</th>
                            <th>${__("Topic")}</th>
                            <th>${__("Time")}</th>
                        </tr>
                    </thead>
                    <tbody>${rows}</tbody>
                </table>
            `);

            d.show();
        },
    });
}