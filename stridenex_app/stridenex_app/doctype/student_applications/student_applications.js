// Copyright (c) 2026, QTPL and contributors
// For license information, please see license.txt

// frappe.ui.form.on("Student Applications", {
// 	refresh(frm) {

// 	},
// });
// student_applications.js
frappe.ui.form.on('Student Applications', {
    opportunity_type: function (frm) {
        // clear the other two link fields and industry whenever type changes
        if (frm.doc.opportunity_type !== 'Project') frm.set_value('project', '');
        if (frm.doc.opportunity_type !== 'Internship') frm.set_value('internship', '');
        if (frm.doc.opportunity_type !== 'Job') frm.set_value('job_profile', '');
        frm.set_value('industry', '');
    },

    project: function (frm) {
        fetch_industry(frm, 'Industry Project', frm.doc.project);
    },

    internship: function (frm) {
        fetch_industry(frm, 'Internship', frm.doc.internship);
    },

    job_profile: function (frm) {
        fetch_industry(frm, 'Industry Job Profile', frm.doc.job_profile);
    }
});

function fetch_industry(frm, doctype, name) {
    if (!name) {
        frm.set_value('industry', '');
        return;
    }
    frappe.db.get_value(doctype, name, 'industry', (r) => {
        if (r && r.industry) {
            frm.set_value('industry', r.industry);
        }
    });
}