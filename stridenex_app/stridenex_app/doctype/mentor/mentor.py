import frappe
from frappe import _
from frappe.model.document import Document
from frappe.desk.doctype.notification_log.notification_log import (
    enqueue_create_notification,
)


class Mentor(Document):
    def on_save(self):
        if self.other_domain:
            if not frappe.db.exists("Domain", {"domain_name": self.other_domain}):
                frappe.get_doc(
                    {
                        "doctype": "Domain Request",
                        "domain_name": self.other_domain,
                        "mentor": self.name,
                        "requested_by": frappe.session.user,
                        "status": "Pending",
                    }
                ).insert(ignore_permissions=True)

    def on_update(self):
        if self.has_value_changed("approved_status"):
            self.notify_approval_status()

    def notify_approval_status(self):
        """Send email + system notification when approved_status changes."""
        if self.approved_status not in ("Approved", "Rejected"):
            return

        email_id = self.get("email_id") or self.get("email")
        mentor_user = self.get("user") or self.get("user_id")

        self.send_status_email(email_id)

        if mentor_user:
            self.send_status_notification(mentor_user)

    def send_status_email(self, email_id):
        if not email_id:
            frappe.log_error(
                title="Mentor Approval Mail",
                message=f"No email found for mentor {self.name}",
            )
            return

        mentor_name = self.get("mentor") or self.email_id

        if self.approved_status == "Approved":
            subject = _("🎉 Your Mentor Application Has Been Approved | StrideNex")
            message = f"""
			<div style="margin:0;padding:0;background:#f6f6f8;font-family:'Inter',-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;">
				<table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background:#f6f6f8;padding:30px 15px;">
					<tr>
						<td align="center">

							<table role="presentation" width="100%" cellspacing="0" cellpadding="0"
								style="max-width:600px;background:#ffffff;border:1px solid #e2e8f0;border-radius:16px;overflow:hidden;">

								<tr>
									<td style="background:#0f0fbd;padding:30px;text-align:center;">
										<h1 style="margin:0;color:#ffffff;font-size:26px;font-weight:700;">
											Mentor Application Approved
										</h1>
										<p style="margin:8px 0 0;color:#dbeafe;font-size:14px;">
											Welcome to the StrideNex Mentor Network
										</p>
									</td>
								</tr>

								<tr>
									<td style="padding:32px;">

										<p style="margin:0 0 20px;color:#1E293B;font-size:16px;line-height:1.8;">
											Dear <strong>{mentor_name}</strong>,
										</p>

										<div style="background:#f0fdf4;border-left:4px solid #10b981;padding:18px;border-radius:8px;margin-bottom:24px;">
											<p style="margin:0;color:#065f46;font-size:15px;line-height:1.8;">
												🎉 Congratulations! Your mentor application has been
												<strong>approved</strong>.
											</p>
										</div>

										<p style="margin:0 0 20px;color:#1E293B;font-size:15px;line-height:1.8;">
											You are now officially part of the StrideNex mentor community and can begin guiding students, sharing expertise, and helping learners achieve their career goals.
										</p>

									</td>
								</tr>

								<tr>
									<td style="background:#0F172A;padding:24px;text-align:center;">
										<p style="margin:0;color:#ffffff;font-size:15px;font-weight:600;">
											Thank you for joining StrideNex
										</p>
										<p style="margin:10px 0 0;color:#94a3b8;font-size:13px;">
											Empowering Careers Through Mentorship
										</p>
									</td>
								</tr>

							</table>

						</td>
					</tr>
				</table>
			</div>
			"""
        else:
            subject = _("Update on Your Mentor Application | StrideNex")
            message = f"""
			<div style="margin:0;padding:0;background:#f6f6f8;font-family:'Inter',-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;">
				<table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background:#f6f6f8;padding:30px 15px;">
					<tr>
						<td align="center">

							<table role="presentation" width="100%" cellspacing="0" cellpadding="0"
								style="max-width:600px;background:#ffffff;border:1px solid #e2e8f0;border-radius:16px;overflow:hidden;">

								<tr>
									<td style="background:#0f0fbd;padding:30px;text-align:center;">
										<h1 style="margin:0;color:#ffffff;font-size:26px;font-weight:700;">
											Mentor Application Update
										</h1>
										<p style="margin:8px 0 0;color:#dbeafe;font-size:14px;">
											Thank you for your interest in mentoring through StrideNex
										</p>
									</td>
								</tr>

								<tr>
									<td style="padding:32px;">

										<p style="margin:0 0 20px;color:#1E293B;font-size:16px;line-height:1.8;">
											Dear <strong>{mentor_name}</strong>,
										</p>

										<div style="background:#fef2f2;border-left:4px solid #ef4444;padding:18px;border-radius:8px;margin-bottom:24px;">
											<p style="margin:0;color:#991b1b;font-size:15px;line-height:1.8;">
												We appreciate your interest in becoming a mentor. After careful review, we are unable to approve your mentor application at this time.
											</p>
										</div>

										<p style="margin:0 0 20px;color:#64748B;font-size:15px;line-height:1.8;">
											This decision does not diminish your experience or achievements. Applications are evaluated based on current platform requirements and mentor availability across domains.
										</p>

										<div style="background:#fff7ed;border-left:4px solid #ff6b00;padding:18px;border-radius:8px;">
											<p style="margin:0;color:#9a3412;font-size:14px;line-height:1.8;">
												You may update your profile, enhance your expertise, and apply again in the future. We encourage you to stay connected with the StrideNex community.
											</p>
										</div>

									</td>
								</tr>

								<tr>
									<td style="background:#0F172A;padding:24px;text-align:center;">
										<p style="margin:0;color:#ffffff;font-size:15px;font-weight:600;">
											Thank you for your interest in StrideNex
										</p>
										<p style="margin:10px 0 0;color:#94a3b8;font-size:13px;">
											Connecting Mentors and Learners
										</p>
									</td>
								</tr>

							</table>

						</td>
					</tr>
				</table>
			</div>
			"""

        frappe.sendmail(
            recipients=[email_id],
            subject=subject,
            message=message,
            reference_doctype=self.doctype,
            reference_name=self.name,
        )

    def send_status_notification(self, mentor_user):
        notification_doc = frappe._dict(
            {
                "type": "Alert",
                "document_type": self.doctype,
                "document_name": self.name,
                "subject": _("Your mentor application was {0}").format(
                    self.approved_status.lower()
                ),
                "from_user": frappe.session.user,
                "email_content": _(
                    "Your mentor approval status has been updated to '{0}'."
                ).format(self.approved_status),
            }
        )

        enqueue_create_notification([mentor_user], notification_doc)