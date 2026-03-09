# Copyright (c) 2026, QTPL and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class Mentor(Document):
	def on_submit(self):

		if self.other_domain:

			if not frappe.db.exists("Domain", {"domain_name": self.other_domain}):

				frappe.get_doc({
					"doctype": "Domain Request",
					"domain_name": self.other_domain,
					"mentor": self.name,
					"requested_by": frappe.session.user,
					"status": "Pending"
				}).insert(ignore_permissions=True)
