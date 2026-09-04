// Copyright (c) 2026, QTPL and contributors
// For license information, please see license.txt

frappe.ui.form.on("Domain Request", {
	refresh(frm) {
		frm.set_df_property("approved_by", "read_only", 1);
		frm.set_df_property("approved_on", "read_only", 1);

		// Only show action buttons when the request is still Pending
		if (frm.doc.status === "Pending" && !frm.is_new()) {
			// ── Approve ────────────────────────────────────────────────────
			frm.add_custom_button(__("Approve"), () => {
				frappe.confirm(
					__("Are you sure you want to approve the domain request for <strong>{0}</strong>?", [frm.doc.domain_name]),
					() => {
						frappe.call({
							method: "stridenex_app.api_stridenex_app.mentor.mentor.approve_domain_request",
							args: { name: frm.doc.name },
							freeze: true,
							freeze_message: __("Approving…"),
							callback(r) {
								if (r.message && r.message.success) {
									frappe.show_alert({ message: r.message.message, indicator: "green" });
									frm.reload_doc();
								} else {
									frappe.msgprint({
										title: __("Error"),
										indicator: "red",
										message: (r.message && r.message.message) || __("Could not approve request."),
									});
								}
							},
						});
					}
				);
			}, __("Actions"));

			// ── Reject ─────────────────────────────────────────────────────
			frm.add_custom_button(__("Reject"), () => {
				const d = new frappe.ui.Dialog({
					title: __("Reject Domain Request"),
					fields: [
						{
							label: __("Rejection Reason"),
							fieldname: "reason",
							fieldtype: "Small Text",
							reqd: 1,
						},
					],
					primary_action_label: __("Reject"),
					primary_action(values) {
						frappe.call({
							method: "stridenex_app.api_stridenex_app.mentor.mentor.reject_domain_request",
							args: { name: frm.doc.name, reason: values.reason },
							freeze: true,
							freeze_message: __("Rejecting…"),
							callback(r) {
								d.hide();
								if (r.message && r.message.success) {
									frappe.show_alert({ message: r.message.message, indicator: "orange" });
									frm.reload_doc();
								} else {
									frappe.msgprint({
										title: __("Error"),
										indicator: "red",
										message: (r.message && r.message.message) || __("Could not reject request."),
									});
								}
							},
						});
					},
				});
				d.show();
			}, __("Actions"));

			// Style buttons via CSS class after render
			frm.page.btn_secondary.find(".btn[data-label='Approve']").addClass("btn-success text-white");
			frm.page.btn_secondary.find(".btn[data-label='Reject']").addClass("btn-danger text-white");
		}
	},
});
