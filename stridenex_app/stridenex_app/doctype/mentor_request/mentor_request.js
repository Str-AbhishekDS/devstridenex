// Copyright (c) 2026, QTPL and contributors
// For license information, please see license.txt

// frappe.ui.form.on("Mentor Request", {
// 	refresh(frm) {

// 	},
// });
function acceptRequest(requestId) {
    let selected_datetime = prompt("Enter datetime (YYYY-MM-DD HH:MM:SS)");

    frappe.call({
        method: "stridenex_app.stridenex_app.doctype.mentor_request.accept_and_schedule",
        args: {
            request_id: requestId,
            session_datetime: selected_datetime
        },
        callback: function(r) {
            frappe.msgprint(r.message.message);
            location.reload();
        }
    });
}

function suggestTime(requestId) {
    let date = prompt("Enter date (YYYY-MM-DD)");
    let time = prompt("Enter time (HH:MM)");

    frappe.call({
        method: "stridenex_app.stridenex_app.doctype.mentor_request.suggest_time",
        args: {
            request_id: requestId,
            date: date,
            time: time
        },
        callback: function(r) {
            frappe.msgprint(r.message.message);
        }
    });
}

function declineRequest(requestId) {
    frappe.call({
        method: "stridenex_app.stridenex_app.doctype.mentor_request.decline_request",
        args: {
            request_id: requestId
        },
        callback: function(r) {
            frappe.msgprint(r.message.message);
            location.reload();
        }
    });
}