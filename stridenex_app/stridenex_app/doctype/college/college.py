# Copyright (c) 2026, QTPL and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class College(Document):

    def on_update_after_submit(self):

        # Check if status changed to Approved
        if self.approved == "Approved" and self.get_doc_before_save().approved != "Approved":

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
