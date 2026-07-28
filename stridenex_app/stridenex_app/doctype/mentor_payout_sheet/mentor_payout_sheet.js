frappe.ui.form.on('Mentor Payout Sheet', {
	onload(frm) {
		// Set date defaults if empty
		if (!frm.doc.start_date || !frm.doc.end_date) {
			frappe.db.get_single_value('Mentor Payout Settings', 'last_payout_date').then(val => {
				if (val) {
					frm.set_value('start_date', frappe.datetime.add_days(val, 1));
					frm.set_value('end_date', frappe.datetime.add_days(val, 7));
				}
			});
		}
	},
	min_payout_filter(frm) {
		let min_payout = flt(frm.doc.min_payout_filter);
		(frm.doc.mentors || []).forEach(row => {
			if (row.net_payout >= min_payout) {
				row.released = 1;
			} else {
				row.released = 0;
			}
		});
		(frm.doc.summary || []).forEach(row => {
			if (row.net_payout >= min_payout) {
				row.released = 1;
			} else {
				row.released = 0;
			}
		});
		frm.refresh_field('mentors');
		frm.refresh_field('summary');
	},
	session_mentor_filter(frm) {
		filter_sessions_table(frm);
	},
	session_type_filter(frm) {
		filter_sessions_table(frm);
	},
	penalty_mentor_filter(frm) {
		filter_penalties_table(frm);
	}
});

function filter_sessions_table(frm) {
	let mentor = frm.doc.session_mentor_filter;
	let session_type = frm.doc.session_type_filter;
	
	if (frm.fields_dict.sessions && frm.fields_dict.sessions.grid) {
		frm.fields_dict.sessions.grid.filter_rows(row => {
			let match = true;
			if (mentor && row.mentor !== mentor) match = false;
			if (session_type && row.offering_type !== session_type) match = false;
			return match;
		});
	}
}

function filter_penalties_table(frm) {
	let mentor = frm.doc.penalty_mentor_filter;
	
	if (frm.fields_dict.penalties && frm.fields_dict.penalties.grid) {
		frm.fields_dict.penalties.grid.filter_rows(row => {
			let match = true;
			if (mentor && row.mentor !== mentor) match = false;
			return match;
		});
	}
}
