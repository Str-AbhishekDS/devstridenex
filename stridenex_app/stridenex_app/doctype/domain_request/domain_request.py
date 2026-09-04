# Copyright (c) 2026, QTPL and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe import _


class DomainRequest(Document):

    def before_insert(self):
        """Stamp the requesting user and mentor email on creation."""
        if not self.requested_by:
            self.requested_by = frappe.session.user

        if self.mentor and not self.mentor_email:
            self.mentor_email = frappe.db.get_value(
                "Mentor", self.mentor, "email_id"
            )

    def on_update(self):
        """When status changes to Approved, auto-create the Domain master record."""
        if self.has_value_changed("status"):
            if self.status == "Approved":
                self._auto_create_domain()
                # Stamp who approved and when (use db_set to avoid triggering on_update again)
                frappe.db.set_value(
                    "Domain Request",
                    self.name,
                    {
                        "approved_by": frappe.session.user,
                        "approved_on": frappe.utils.now(),
                    },
                )

    def _auto_create_domain(self):
        """Insert the domain into the Domain master if it does not already exist."""
        domain_name = (self.domain_name or "").strip()
        if not domain_name:
            return

        exists = frappe.db.exists("Domain", {"domain": domain_name})
        if not exists:
            try:
                frappe.get_doc(
                    {
                        "doctype": "Domain",
                        "domain": domain_name,
                    }
                ).insert(ignore_permissions=True)
                frappe.db.commit()
            except Exception:
                frappe.log_error(
                    frappe.get_traceback(),
                    f"Domain Request: Failed to create Domain master for '{domain_name}'",
                )
