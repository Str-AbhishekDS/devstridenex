# Copyright (c) 2026, QTPL and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class College(Document):

    def on_update_after_submit(self):

        old_doc = self.get_doc_before_save()

        # Check if status changed to Approved
        if (
            self.approved_status_workflow == "Approved"
            and old_doc
            and old_doc.approved_status_workflow != "Approved"
        ):

            frappe.sendmail(
                recipients=[self.email],
                subject="Welcome to Our Platform",
                message=f"""
                Dear {self.college_name},

                Congratulations!

                Your college registration has been approved.

                Welcome to our platform.

                Regards,
                Team
                """
            )