# Copyright (c) 2026, QTPL and contributors
# For license information, please see license.txt

# Copyright (c) 2026, QTPL and contributors
# For license information, please see license.txt
#
# PATH: mentor_offering/doctype/mentor_offering_review/mentor_offering_review.py
#
# This is a CHILD TABLE — it has no standalone API methods.
# It lives inside Mentor Session Booking under the "reviews" table field.
#
# When a review row is saved inside a booking, MentorSessionBooking.on_update()
# automatically calls _recalculate_offering_rating() which updates the
# average_rating on the parent Mentor Offering.
#
# Flow:
#   Student opens Mentor Session Booking (status=Completed)
#   → clicks Add Row in Reviews table
#   → fills rating + review_text + reviewed_by (their user id)
#   → saves the booking
#   → on_update() fires → Mentor Offering average_rating updates automatically

import frappe
from frappe.model.document import Document
from frappe import _


class MentorOfferingReview(Document):

    def validate(self):
        self.validate_rating()
        self.set_reviewed_on()

    def validate_rating(self):
        if self.rating is not None:
            if not (1 <= float(self.rating) <= 5):
                frappe.throw(_("Rating must be between 1 and 5."))

    def set_reviewed_on(self):
        """Auto-set reviewed_on to today if not filled."""
        if not self.reviewed_on:
            self.reviewed_on = frappe.utils.today()
