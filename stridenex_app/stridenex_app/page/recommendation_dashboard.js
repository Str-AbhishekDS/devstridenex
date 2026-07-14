frappe.pages['recommendation-dashboard'].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: 'Recommendation Dashboard',
		single_column: true,
	});

	new RecommendationDashboard(page);
};

class RecommendationDashboard {
	constructor(page) {
		this.page = page;
		this.make_filters();
		this.make_body();
	}

	make_filters() {
		this.student_field = this.page.add_field({
			fieldtype: 'Link',
			options: 'Student',
			fieldname: 'student',
			label: 'Student',
			change: () => this.load(),
		});

		this.page.set_primary_action('Refresh', () => this.load(), 'refresh');
	}

	make_body() {
		this.body = $(
			'<div class="recommendation-dashboard-body" style="margin-top: 20px;"></div>'
		).appendTo(this.page.main);
		this.body.html(
			'<p class="text-muted">Select a student to view their recommendation history.</p>'
		);
	}

	load() {
		const student = this.student_field.get_value();
		if (!student) {
			this.body.html(
				'<p class="text-muted">Select a student to view their recommendation history.</p>'
			);
			return;
		}
		this.body.html('<p class="text-muted">Loading…</p>');
		frappe.call({
			method:
				'stridenex_app.stridenex_app.page.recommendation_dashboard.get_recommendation_history',
			args: { student },
			callback: (r) => this.render(r.message || []),
			error: () => {
				this.body.html('<p class="text-danger">Could not load history.</p>');
			},
		});
	}

	render(logs) {
		if (!logs.length) {
			this.body.html(
				'<p class="text-muted">No recommendations generated yet for this student.</p>'
			);
			return;
		}
		const cards = logs.map((log) => this.render_card(log)).join('');
		this.body.html(`<div class="recommendation-list">${cards}</div>`);
	}

	render_card(log) {
		const date = frappe.datetime.str_to_user(log.creation);
		const type_color = log.top_pick_type === 'internship' ? 'blue' : 'orange';
		const alts = (log.alternatives || [])
			.map(
				(a) => `
				<li>
					${frappe.utils.escape_html(a.title || '')}
					<span class="text-muted">
						(${frappe.utils.escape_html(a.type || '')}, fit ${a.fit_score != null ? a.fit_score : '-'})
					</span>
				</li>`
			)
			.join('');

		return `
			<div class="recommendation-card" style="border:1px solid var(--border-color); border-radius:8px; padding:16px; margin-bottom:14px;">
				<div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:8px;">
					<h5 style="margin:0;">
						${frappe.utils.escape_html(log.top_pick_title || '(untitled)')}
						<span class="indicator-pill ${type_color}" style="margin-left:8px;">${frappe.utils.escape_html(log.top_pick_type || '')}</span>
					</h5>
					<span class="text-muted">${date}</span>
				</div>
				<div style="margin:10px 0 6px;">
					<strong>Fit score:</strong> ${log.fit_score != null ? log.fit_score : '-'} / 100
				</div>
				<p style="margin-bottom:8px;">${frappe.utils.escape_html(log.reasoning || '')}</p>
				${alts ? `<div><strong>Alternatives considered:</strong><ul style="margin-top:6px;">${alts}</ul></div>` : ''}
			</div>
		`;
	}
}