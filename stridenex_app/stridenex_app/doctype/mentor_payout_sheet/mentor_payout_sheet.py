import frappe
from frappe.model.document import Document
from frappe.utils import getdate, add_days

class MentorPayoutSheet(Document):
	def validate(self):
		# 1. Set Title
		self.title = f"Payout Sheet: {self.start_date} to {self.end_date} ({self.payout_cycle})"
		
		# 2. Preserve user selections (released checkbox)
		released_map = {}
		for row in self.get("mentors") or []:
			if row.mentor:
				released_map[row.mentor] = bool(row.released)

		# 3. Fetch default settings
		settings = frappe.get_single("Mentor Payout Settings")
		
		# Retrieve commission tiers
		tiers = []
		for tier in settings.get("commission_tiers") or []:
			tiers.append({
				"threshold": float(tier.threshold or 0),
				"rate": float(tier.commission_rate or 0) / 100.0
			})
		if not tiers:
			tiers = [
				{"threshold": 0.0, "rate": 0.15},
				{"threshold": 50000.0, "rate": 0.12},
				{"threshold": 100000.0, "rate": 0.10}
			]
		tiers = sorted(tiers, key=lambda x: x["threshold"])

		# Retrieve penalty rates
		penalty_rates = {
			"1:1 Mentorship": float(getattr(settings, "one_on_one_penalty", 15.0) or 15.0),
			"Group Session": float(getattr(settings, "group_session_penalty", 15.0) or 15.0),
			"Async Review": float(getattr(settings, "async_review_penalty", 15.0) or 15.0),
			"Workshop": float(getattr(settings, "workshop_penalty", 15.0) or 15.0)
		}

		# 4. Query eligible bookings in date range (Completed or Missed/Absent, and currently Unpaid)
		bookings = frappe.get_all(
			"Mentor Session Booking",
			filters={
				"session_date": ["between", [self.start_date, self.end_date]],
				"payout_status": "Unpaid"
			},
			fields=["name", "mentor", "student", "session_date", "offering_type", "amount_paid", "status", "mentor_absent"]
		)

		# 5. Populate intermediate lists & calculate
		sessions_rows = []
		penalties_rows = []
		
		# Mentor calculations map
		mentor_data = {}

		for b in bookings:
			mentor = b.mentor
			if not mentor:
				continue

			if mentor not in mentor_data:
				mentor_data[mentor] = {
					"sessions_count": 0,
					"gross_amount": 0.0,
					"penalty_amount": 0.0,
					"commission_rate": 15.0,
					"commission_amount": 0.0,
					"net_payout": 0.0
				}

			amount = float(b.amount_paid or 0)

			# Case A: Missed/Absent session -> Penalty applies
			if b.mentor_absent:
				# Find penalty rate based on type
				rate = penalty_rates.get(b.offering_type, 15.0)
				penalty_val = (rate / 100.0) * amount
				
				penalties_rows.append({
					"mentor": mentor,
					"booking": b.name,
					"offering_type": b.offering_type,
					"penalty_rate": rate,
					"penalty_amount": penalty_val
				})
				
				mentor_data[mentor]["penalty_amount"] += penalty_val

			# Case B: Completed session -> Earns Gross
			elif b.status == "Completed":
				sessions_rows.append({
					"booking": b.name,
					"mentor": mentor,
					"student": b.student,
					"session_date": b.session_date,
					"offering_type": b.offering_type,
					"amount_paid": amount,
					"status": b.status
				})
				
				mentor_data[mentor]["gross_amount"] += amount
				mentor_data[mentor]["sessions_count"] += 1

		# Group and calculate commission & net payouts for each mentor
		mentors_rows = []
		summary_rows = []

		for mentor, data in mentor_data.items():
			# Apply tiered commission rate based on Gross
			comm_rate = 15.0 # fallback default
			for tier in tiers:
				if data["gross_amount"] >= tier["threshold"]:
					comm_rate = tier["rate"] * 100.0
			
			data["commission_rate"] = comm_rate
			data["commission_amount"] = (comm_rate / 100.0) * data["gross_amount"]
			
			# Net = Gross - Commission - Penalties
			data["net_payout"] = data["gross_amount"] - data["commission_amount"] - data["penalty_amount"]
			
			# Check if released was previously selected by the user
			is_released = released_map.get(mentor, False)

			row_dict = {
				"released": 1 if is_released else 0,
				"mentor": mentor,
				"total_sessions": data["sessions_count"],
				"gross_amount": data["gross_amount"],
				"penalty_amount": data["penalty_amount"],
				"commission_rate": data["commission_rate"],
				"commission_amount": data["commission_amount"],
				"net_payout": data["net_payout"],
				"status": "Draft"
			}
			mentors_rows.append(row_dict)

			summary_dict = {
				"released": 1 if is_released else 0,
				"mentor": mentor,
				"gross_amount": data["gross_amount"],
				"total_penalties": data["penalty_amount"],
				"commission_amount": data["commission_amount"],
				"net_payout": data["net_payout"],
				"status": "Draft"
			}
			summary_rows.append(summary_dict)

		# 6. Set child tables
		self.set("mentors", [])
		self.set("sessions", [])
		self.set("penalties", [])
		self.set("summary", [])

		for row in mentors_rows:
			self.append("mentors", row)
		for row in sessions_rows:
			self.append("sessions", row)
		for row in penalties_rows:
			self.append("penalties", row)
		for row in summary_rows:
			self.append("summary", row)

	def on_submit(self):
		# Create dynamic supplier creation/linking and generate Purchase Invoices for released mentors
		company = frappe.defaults.get_global_default("company") or "Stridenex"
		
		# Find standard expense and payable accounts
		expense_account = frappe.db.get_value("Account", {"account_type": "Expense", "company": company}, "name")
		if not expense_account:
			expense_account = frappe.db.get_value("Account", {"company": company, "is_group": 0, "root_type": "Expense"}, "name")
		
		credit_to = frappe.db.get_value("Account", {"account_type": "Payable", "company": company}, "name")
		if not credit_to:
			credit_to = frappe.db.get_value("Account", {"company": company, "is_group": 0, "root_type": "Liability"}, "name")

		released_mentors = set()
		for row in self.mentors:
			if row.released:
				released_mentors.add(row.mentor)
				row.status = "Approved"

		for row in self.summary:
			if row.mentor in released_mentors:
				row.status = "Approved"
				row.released = 1

		# Update Booking Statuses for released mentors
		# Fetch bookings included in this period
		bookings = frappe.get_all(
			"Mentor Session Booking",
			filters={
				"session_date": ["between", [self.start_date, self.end_date]],
				"payout_status": "Unpaid",
				"mentor": ["in", list(released_mentors)]
			},
			fields=["name", "mentor"]
		)

		for b in bookings:
			frappe.db.set_value("Mentor Session Booking", b.name, {
				"payout_status": "Processing",
				"payout_reference": self.name
			})

		# Generate Purchase Invoices for released payouts
		for row in self.summary:
			if not row.released or row.net_payout <= 0:
				continue
			
			supplier = get_or_create_supplier(row.mentor)
			
			pi = frappe.get_doc({
				"doctype": "Purchase Invoice",
				"supplier": supplier,
				"company": company,
				"posting_date": frappe.utils.today(),
				"credit_to": credit_to,
				"items": [{
					"item_name": f"Mentorship Payout - {self.name}",
					"qty": 1,
					"rate": row.net_payout,
					"amount": row.net_payout,
					"expense_account": expense_account
				}]
			})
			pi.insert(ignore_permissions=True)
			# Standard practice: we keep it as Draft for finance team to review/submit
			# We log the purchase invoice in the summary row or mentors row status
			frappe.msgprint(f"Generated Purchase Invoice {pi.name} for mentor {row.mentor}")

def get_or_create_supplier(mentor_email):
	supplier_name = frappe.db.get_value("Supplier", {"email_id": mentor_email}, "name")
	if not supplier_name:
		supplier_name = frappe.db.get_value("Supplier", {"supplier_name": mentor_email}, "name")
	if not supplier_name:
		s = frappe.get_doc({
			"doctype": "Supplier",
			"supplier_name": mentor_email,
			"supplier_group": "All Supplier Groups",
			"email_id": mentor_email
		})
		s.insert(ignore_permissions=True)
		supplier_name = s.name
	return supplier_name
