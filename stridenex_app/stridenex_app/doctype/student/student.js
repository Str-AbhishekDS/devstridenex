// Copyright (c) 2026, QTPL and contributors
// For license information, please see license.txt

frappe.ui.form.on("Student", {
	date_of_birth(frm) {
		if (frm.doc.date_of_birth) {
			let dob = moment(frm.doc.date_of_birth);
			let today = moment();
			
			if (dob.isSameOrAfter(today, "day")) {
				frappe.msgprint(__("Date of Birth cannot be today or in the future."));
				frm.set_value("date_of_birth", "");
			} else {
				let age = today.diff(dob, "years");
				if (age < 15) {
					frappe.msgprint(__("Student must be at least 15 years old. Please enter a valid Date of Birth."));
					frm.set_value("date_of_birth", "");
				}
			}
		}
	},
	validate(frm) {
		if (frm.doc.date_of_birth) {
			let dob = moment(frm.doc.date_of_birth);
			let today = moment();
			
			if (dob.isSameOrAfter(today, "day")) {
				frappe.msgprint(__("Date of Birth cannot be today or in the future."));
				frappe.validated = false;
			} else {
				let age = today.diff(dob, "years");
				if (age < 15) {
					frappe.msgprint(__("Student must be at least 15 years old. Please enter a valid Date of Birth."));
					frappe.validated = false;
				}
			}
		}
	}
});
